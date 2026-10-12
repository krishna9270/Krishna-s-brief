# The Krishna Brief

A personal daily newsletter that installs to your phone's home screen (a PWA).

## Files
- `app.html` – the app (page content). `index.html` is generated from it by `sh make_index.sh`.
- `feeds.json` – your topics, the RSS feeds behind each one, and `skipWords` (crime/gossip words filtered out of the India and TN sections).
- `build_digest.py` – fetches the feeds and writes `digest.json` (Python 3, no extra packages).
- `digest.json` – today's stories, read by the app.
- `sw.js`, `manifest.webmanifest`, `icons/` – what makes it installable and work offline.
- `.github/workflows/daily.yml` – rebuilds the digest every morning and publishes to GitHub Pages.

## Run it locally
    python3 build_digest.py
    sh make_index.sh
    python3 -m http.server 8000   # then open http://localhost:8000

## Put it on your phone
Host the folder on any static host (GitHub Pages works with the included workflow), open the
link on your phone, then:
- iPhone (Safari): Share → Add to Home Screen
- Android (Chrome): tap Install in the app, or ⋮ → Add to Home screen

## Personalisation
Every story you open is counted on your phone (local storage, never uploaded). After 5 opens the Brief
reorders topics by how often you read them, gives topics you read more stories (up to 12) and topics you
skip fewer (down to 3), sorts stories by the words you click most, and adds a "For you" section. "Show less like this" pushes similar stories down. Open Topics to see
what it has learned, or wipe it.

## Discover
Topics marked `"core": false` in feeds.json (science, space, health, cricket, startups, personal finance,
climate, Tamil cinema, curiosities) start out as one story each in a rotating Discover section. Open two
stories from one of them and it becomes a full section, sized by how much you read it.
