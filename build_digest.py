#!/usr/bin/env python3
"""Fetch the RSS/Atom feeds listed in feeds.json and write digest.json.

Standard library only. Run it once a day (the GitHub Action does this):
    python3 build_digest.py
"""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).parent
ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"

# Friendly publisher names; feed titles are often long ("X – Breaking News, World News…").
SOURCES = {
    "aljazeera.com": "Al Jazeera", "npr.org": "NPR", "thediplomat.com": "The Diplomat",
    "foreignpolicy.com": "Foreign Policy", "business-standard.com": "Business Standard",
    "indiatimes.com": "Economic Times", "indianexpress.com": "Indian Express", "thehindu.com": "The Hindu", "dtnext.in": "DT Next",
    "techcrunch.com": "TechCrunch", "hnrss.org": "Hacker News", "sciencedaily.com": "ScienceDaily",
    "newscientist.com": "New Scientist", "space.com": "Space.com", "nasa.gov": "NASA",
    "espncricinfo.com": "ESPNcricinfo", "livemint.com": "Mint", "theguardian.com": "The Guardian",
    "grist.org": "Grist", "atlasobscura.com": "Atlas Obscura",
}
UA = "Mozilla/5.0 (personal newsletter digest)"


def clean(text, limit=220):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def parse_date(value):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def source_name(feed_url, channel_title):
    host = urlparse(feed_url).netloc.replace("www.", "")
    for domain, name in SOURCES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return clean(channel_title, 30) if channel_title else host


def image_of(el, raw_html=""):
    for tag in (f"{MEDIA}content", f"{MEDIA}thumbnail"):
        for m in el.iter(tag):
            url = m.get("url", "")
            if url.startswith("http") and m.get("medium", "image") == "image":
                return url
    enc = el.find("enclosure")
    if enc is not None and enc.get("type", "").startswith("image"):
        return enc.get("url")
    match = re.search(r'<img[^>]+src="(https?://[^"]+)"', raw_html or "")
    return match.group(1) if match else None


def tidy_summary(summary, title):
    if not summary or summary.lower().startswith(("article url:", "comments")) or summary.rstrip("…") in title:
        return ""
    return summary


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parse_feed(url):
    root = ET.fromstring(fetch(url))
    items = []
    channel = root.find("channel")
    if channel is not None:  # RSS 2.0
        source = source_name(url, channel.findtext("title"))
        for it in channel.findall("item"):
            title = clean(it.findtext("title"), 200)
            items.append({
                "title": title,
                "link": (it.findtext("link") or "").strip(),
                "summary": tidy_summary(clean(it.findtext("description")), title),
                "image": image_of(it, it.findtext("description")),
                "date": parse_date(it.findtext("pubDate")),
                "source": source,
            })
    else:  # Atom
        source = source_name(url, root.findtext(f"{ATOM}title"))
        for it in root.findall(f"{ATOM}entry"):
            link = it.find(f"{ATOM}link")
            title = clean(it.findtext(f"{ATOM}title"), 200)
            raw = it.findtext(f"{ATOM}summary") or it.findtext(f"{ATOM}content")
            items.append({
                "title": title,
                "link": link.get("href") if link is not None else "",
                "summary": tidy_summary(clean(raw), title),
                "image": image_of(it, raw),
                "date": parse_date(it.findtext(f"{ATOM}updated") or it.findtext(f"{ATOM}published")),
                "source": source,
            })
    return [i for i in items if i["title"] and i["link"]]


def is_crime(item, words):
    text = f"{item['title']} {item['summary']}".lower()
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


OG_IMAGE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]*content=["\']([^"\']+)'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)',
    re.I,
)


def page_image(url):
    """The share image an article page advertises (og:image), or None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as resp:
            head = resp.read(300_000).decode("utf-8", "ignore")
    except Exception:
        return None
    m = OG_IMAGE.search(head)
    found = m and (m.group(1) or m.group(2))
    return html.unescape(found) if found and found.startswith("http") else None


def fill_images(sections):
    missing = [i for s in sections for i in s["items"] if not i.get("image")]
    with ThreadPoolExecutor(max_workers=16) as pool:
        for item, image in zip(missing, pool.map(lambda i: page_image(i["link"]), missing)):
            item["image"] = image
    print(f"found photos for {sum(1 for i in missing if i['image'])} of {len(missing)} stories without one")


def main():
    config = json.loads((HERE / "feeds.json").read_text())
    per_section = config.get("itemsPerSection", 5)
    skip_words = [w.lower() for w in config.get("skipWords", [])]
    sections = []
    for section in config["sections"]:
        items, seen = [], set()
        for feed in section["feeds"]:
            # A feed is a URL, or {"url": ..., "match": regex on the story link}.
            url, match = (feed, None) if isinstance(feed, str) else (feed["url"], feed.get("match"))
            try:
                found = parse_feed(url)
            except Exception as exc:  # one broken feed shouldn't sink the issue
                print(f"skipped {url}: {exc}", file=sys.stderr)
                continue
            if match:
                found = [i for i in found if re.search(match, i["link"])]
            items.extend(found)
        if section.get("filterCrime"):
            items = [i for i in items if not is_crime(i, skip_words)]
        items.sort(key=lambda i: i["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        picked = []
        for item in items:
            if item["link"] in seen:
                continue
            seen.add(item["link"])
            item["date"] = item["date"].isoformat() if item["date"] else None
            picked.append(item)
            if len(picked) == per_section:
                break
        sections.append({k: section[k] for k in ("id", "name", "blurb")} | {"core": section.get("core", True), "items": picked})

    fill_images(sections)
    digest = {
        "title": config.get("title", "My Daily Brief"),
        "reader": config.get("reader", ""),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sections": sections,
    }
    (HERE / "digest.json").write_text(json.dumps(digest, indent=2, ensure_ascii=False))
    print(f"wrote digest.json with {sum(len(s['items']) for s in sections)} stories")


if __name__ == "__main__":
    main()
