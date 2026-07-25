"""Generate NetEase Cloud Music weekly top songs SVG card."""

import json
import os
import sys
import urllib.parse
import urllib.request

THEME_BG = "#1a1b27"
THEME_FG = "#c0caf5"
THEME_ACCENT = "#7aa2f7"
THEME_MUTED = "#565f89"


def fetch(cookie: str) -> tuple[str, list[dict]]:
    headers = {
        "Cookie": f"MUSIC_U={cookie}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Referer": "https://music.163.com/",
    }

    account_url = "https://music.163.com/api/nuser/account/get"
    req = urllib.request.Request(account_url, headers=headers)
    account = json.loads(urllib.request.urlopen(req, timeout=15).read())
    uid = account["account"]["id"]
    nickname = account["profile"]["nickname"]

    week_url = "https://music.163.com/api/v1/play/record/week"
    data = urllib.parse.urlencode({"uid": uid, "type": "1"}).encode()
    req = urllib.request.Request(week_url, data=data, headers=headers)
    week = json.loads(urllib.request.urlopen(req, timeout=15).read())
    songs = [
        {
            "name": item["song"]["name"],
            "artists": "/".join(a["name"] for a in item["song"]["artists"]),
            "score": item["score"],
        }
        for item in week.get("weekData", [])
    ][:10]

    return nickname, songs


def build_svg(nickname: str, songs: list[dict]) -> str:
    width = 480
    row_height = 28
    header = 56
    footer = 18
    height = header + row_height * max(len(songs), 1) + footer

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="-apple-system, Segoe UI, Roboto, sans-serif">',
        f'<rect width="100%" height="100%" fill="{THEME_BG}" rx="10"/>',
        f'<text x="20" y="32" fill="{THEME_ACCENT}" font-size="16" font-weight="600">'
        f'🎵 {nickname} · Weekly Top</text>',
        f'<text x="20" y="48" fill="{THEME_MUTED}" font-size="11">Top {len(songs)} songs on NetEase Cloud Music</text>',
    ]

    for i, song in enumerate(songs):
        y = header + i * row_height + 18
        rank = f"{i + 1:>2}."
        title = song["name"]
        artist = song["artists"]
        lines.append(
            f'<text x="20" y="{y}" fill="{THEME_FG}" font-size="12">'
            f'<tspan fill="{THEME_MUTED}">{rank}</tspan> '
            f'<tspan>{escape(title)} · </tspan>'
            f'<tspan fill="{THEME_MUTED}">{escape(artist)}</tspan>'
            f'</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def main() -> int:
    cookie = os.environ.get("MUSIC_U", "").strip()
    if not cookie:
        print("MUSIC_U env var not set; writing placeholder card.")
        svg = build_svg(
            "Kevin",
            [{"name": "Set MUSIC_U secret to enable", "artists": "—", "score": 0}],
        )
        with open("musicCard.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        return 0

    try:
        nickname, songs = fetch(cookie)
    except Exception as exc:
        print(f"Fetch failed: {exc}", file=sys.stderr)
        svg = build_svg(
            "Kevin",
            [{"name": "Cookie expired — please update", "artists": str(exc)[:60], "score": 0}],
        )
        with open("musicCard.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        return 0

    if not songs:
        songs = [{"name": "No plays this week", "artists": "—", "score": 0}]

    svg = build_svg(nickname, songs)
    with open("musicCard.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote musicCard.svg with {len(songs)} songs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())