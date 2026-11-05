"""Set the all-time baseline from a Spotify streaming history export.

Usage:
    python scripts/parse_history.py "path/to/Spotify Extended Streaming History"

Reads Streaming_History_Audio_*.json (extended export) and, if present,
StreamingHistory_music_*.json (basic export) anywhere under the path.
Prints total minutes, minutes by year and top 5 artists, then saves
baseline_ms and last_played_at_ms to data/state.json.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "state.json"


def to_ms(dt):
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def read_plays(export_dir):
    """Return a list of (end_time_ms, ms_played, artist) tuples."""
    export_dir = Path(export_dir)
    plays = []
    for path in sorted(export_dir.rglob("Streaming_History_Audio_*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            ts = datetime.strptime(row["ts"], "%Y-%m-%dT%H:%M:%SZ")
            plays.append((to_ms(ts), int(row.get("ms_played") or 0),
                          row.get("master_metadata_album_artist_name")))
    for path in sorted(export_dir.rglob("StreamingHistory_music_*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            ts = datetime.strptime(row["endTime"], "%Y-%m-%d %H:%M")
            plays.append((to_ms(ts), int(row.get("msPlayed") or 0),
                          row.get("artistName")))
    return plays


def summarize(plays):
    total_ms = sum(ms for _, ms, _ in plays)
    by_year = Counter()
    by_artist = Counter()
    for ts, ms, artist in plays:
        by_year[datetime.fromtimestamp(ts / 1000, timezone.utc).year] += ms
        if artist:
            by_artist[artist] += ms
    last_ms = max((ts for ts, _, _ in plays), default=0)
    return total_ms, by_year, by_artist.most_common(5), last_ms


def apply_baseline(state, baseline_ms, export_last_ms):
    """Return a new state with the export as the baseline.

    Plays tracked before the export arrived are dropped if the export
    already covers them, so nothing is counted twice.
    """
    kept = [p for p in state.get("tracked_plays", []) if p[0] > export_last_ms]
    return {
        **state,
        "baseline_ms": baseline_ms,
        "tracked_ms": sum(d for _, d in kept),
        "tracked_plays": kept,
        "last_played_at_ms": max(export_last_ms, state.get("last_played_at_ms", 0)),
    }


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    plays = read_plays(sys.argv[1])
    if not plays:
        sys.exit("No Streaming_History_Audio_*.json or "
                 "StreamingHistory_music_*.json files found under that path.")
    total_ms, by_year, top_artists, last_ms = summarize(plays)

    print(f"Total: {total_ms // 60000:,} minutes ({len(plays):,} plays)")
    print("\nBy year:")
    for year in sorted(by_year):
        print(f"  {year}: {by_year[year] // 60000:,}")
    print("\nTop 5 artists:")
    for i, (artist, ms) in enumerate(top_artists, 1):
        print(f"  {i}. {artist}: {ms // 60000:,} minutes")

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    state = apply_baseline(state, total_ms, last_ms)
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    last = datetime.fromtimestamp(last_ms / 1000, timezone.utc)
    print(f"\nSaved {STATE_PATH} (latest play {last:%Y-%m-%d %H:%M} UTC)")


if __name__ == "__main__":
    main()
