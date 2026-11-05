"""Add new Spotify plays to the running total and refresh the README badge.

Needs SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET and SPOTIFY_REFRESH_TOKEN in
the environment. Run by .github/workflows/spotify.yml every hour.
"""

import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "state.json"
README_PATH = ROOT / "README.md"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1/me/player/recently-played"
START = "<!-- SPOTIFY:START -->"
END = "<!-- SPOTIFY:END -->"
MAX_PAGES = 10


def parse_played_at(value):
    """Spotify ISO time, e.g. 2024-05-01T12:34:56.789Z, to unix ms."""
    value = value.replace("Z", "+00:00")
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def merge_plays(state, items):
    """Pure: return a new state with plays newer than the cursor added.

    items are recently-played objects ({"played_at": ..., "track":
    {"duration_ms": ...}}). Plays at or before last_played_at_ms are
    skipped, and duplicates within items are counted once.
    """
    cursor = state.get("last_played_at_ms", 0)
    seen = set()
    new = []
    for item in items:
        ts = parse_played_at(item["played_at"])
        if ts <= cursor or ts in seen:
            continue
        seen.add(ts)
        new.append([ts, int(item["track"]["duration_ms"])])
    new.sort()
    return {
        **state,
        "tracked_ms": state.get("tracked_ms", 0) + sum(d for _, d in new),
        "tracked_plays": state.get("tracked_plays", []) + new,
        "last_played_at_ms": max([cursor] + [ts for ts, _ in new]),
    }


def total_minutes(state):
    return (state.get("baseline_ms", 0) + state.get("tracked_ms", 0)) // 60000


def badge_html(minutes, now):
    message = f"{minutes:,} minutes listened"
    path = urllib.parse.quote(message.replace("-", "--").replace("_", "__"))
    src = (f"https://img.shields.io/badge/Spotify-{path}-1DB954"
           "?style=for-the-badge&logo=spotify&logoColor=white")
    return (f'<img src="{src}" alt="Spotify: {message}">\n'
            f"<br><sub>Last updated {now:%Y-%m-%d %H:%M} UTC</sub>")


def replace_block(readme, block):
    """Pure: put block between the markers. Raises if markers are missing."""
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(readme):
        raise ValueError("SPOTIFY markers not found in README")
    return pattern.sub(lambda _: f"{START}\n{block}\n{END}", readme, count=1)


def current_minutes(readme):
    match = re.search(r"Spotify-([\d%2C]+)%20minutes", readme)
    if not match:
        return None
    return int(urllib.parse.unquote(match.group(1)).replace(",", ""))


def http_json(req):
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def get_access_token(client_id, client_secret, refresh_token):
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()
    body = http_json(urllib.request.Request(TOKEN_URL, data=data, headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }))
    if body.get("refresh_token") and body["refresh_token"] != refresh_token:
        print("Note: Spotify returned a new refresh token. The old one still "
              "works for now; rerun get_refresh_token.py if it stops working.")
    return body["access_token"]


def fetch_recent(access_token, after_ms):
    url = f"{API_URL}?limit=50&after={after_ms}"
    items = []
    for _ in range(MAX_PAGES):
        body = http_json(urllib.request.Request(
            url, headers={"Authorization": f"Bearer {access_token}"}))
        items.extend(body.get("items", []))
        url = body.get("next")
        if not url or not body.get("items"):
            break
    return items


def main():
    try:
        client_id = os.environ["SPOTIFY_CLIENT_ID"]
        client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
        refresh_token = os.environ["SPOTIFY_REFRESH_TOKEN"]
    except KeyError as missing:
        sys.exit(f"Missing environment variable {missing}")

    state = json.loads(STATE_PATH.read_text())
    token = get_access_token(client_id, client_secret, refresh_token)
    items = fetch_recent(token, state.get("last_played_at_ms", 0))
    new_state = merge_plays(state, items)
    added = len(new_state["tracked_plays"]) - len(state.get("tracked_plays", []))
    print(f"{len(items)} plays returned, {added} new")

    if new_state != state:
        STATE_PATH.write_text(json.dumps(new_state, indent=2) + "\n")

    readme = README_PATH.read_text(encoding="utf-8")
    minutes = total_minutes(new_state)
    # Only rewrite when the number changes, so quiet hours make no commit.
    if current_minutes(readme) != minutes:
        block = badge_html(minutes, datetime.now(timezone.utc))
        README_PATH.write_text(replace_block(readme, block), encoding="utf-8")
        print(f"README updated: {minutes:,} minutes")
    else:
        print(f"README unchanged: {minutes:,} minutes")


if __name__ == "__main__":
    main()
