#!/bin/sh
# Wraps app.html in a full HTML document so it can be hosted as a normal site.
cd "$(dirname "$0")"
{
  printf '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
  cat app.html
} > index.html
