"""Generate NetEase Cloud Music card — Spotify-style.

Shows the user's top song this week ("Current Playing" stand-in, since NetEase
has no real-time now-playing endpoint) plus weekly ranking of next songs.
Pulled via /api/v1/play/record (the /week variant was deprecated).
"""

import json
import os
import sys
import urllib.parse
import urllib.request

THEME_BG = "#1a1b27"
THEME_CARD = "#24283b"
THEME_FG = "#c0caf5"
THEME_TITLE = "#ffffff"
THEME_ACCENT = "#7aa2f7"
THEME_MUTED = "#565f89"
THEME_GREEN = "#1db954"

WIDTH = 460
COVER_LG = 96
COVER_SM = 40
PAD = 18
ROW_GAP = 10
HEADER_H = 56
CURRENT_H = COVER_LG + 2 * PAD
RECENT_ROW_H = COVER_SM + ROW_GAP
FOOTER_H = 14

RECENT_TIMES = [
    "Just now", "1 hr. ago", "3 hr. ago", "5 hr. ago",
    "8 hr. ago", "Today", "Yesterday", "2 days ago",
    "3 days ago", "5 days ago",
]


def fetch(cookie: str) -> tuple[str, list[dict]]:
    headers = {
        "Cookie": f"MUSIC_U={cookie}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Referer": "https://music.163.com/",
    }

    account = json.loads(
        urllib.request.urlopen(
            urllib.request.Request(
                "https://music.163.com/api/nuser/account/get", headers=headers
            ),
            timeout=15,
        ).read()
    )
    if account.get("code") != 200 or not account.get("account"):
        raise RuntimeError(f"account API rejected cookie: {account}")
    uid = account["account"]["id"]
    nickname = account["profile"]["nickname"]

    data = urllib.parse.urlencode({"uid": uid, "type": "1"}).encode()
    week = json.loads(
        urllib.request.urlopen(
            urllib.request.Request(
                "https://music.163.com/api/v1/play/record",
                data=data,
                headers=headers,
            ),
            timeout=15,
        ).read()
    )
    if week.get("code") != 200:
        raise RuntimeError(f"play-record API: {week}")

    songs = []
    for item in week.get("weekData", []):
        s = item.get("song") or {}
        album = s.get("album") or {}
        pic = album.get("picUrl", "")
        if pic and "?" in pic:
            pic = pic.split("?")[0] + "?param=300y300"
        elif pic:
            pic = pic + "?param=300y300"
        artists = s.get("artists") or []
        songs.append(
            {
                "name": s.get("name", ""),
                "artists": "/".join(a.get("name", "") for a in artists)
                or (s.get("artist") or {}).get("name", ""),
                "cover": pic,
                "score": item.get("score", 0),
            }
        )

    return nickname, songs[:10]


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def build_svg(nickname: str, songs: list[dict], error_msg: str = "") -> str:
    n_recent = max(len(songs) - 1, 0)
    show_weekly = songs and not error_msg
    height = (
        HEADER_H
        + CURRENT_H
        + 30
        + n_recent * RECENT_ROW_H
        + FOOTER_H
    )

    nick = escape((nickname or "KEVIN").upper())[:14]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'font-family="-apple-system, Segoe UI, Roboto, sans-serif">',
        f'<rect width="100%" height="100%" fill="{THEME_BG}" rx="12"/>',
        # Header — two blocks (Spotify-style)
        f'<g transform="translate({PAD},{PAD})">',
        f'<rect x="0" y="0" width="96" height="28" rx="6" fill="#1f2330"/>',
        f'<text x="14" y="19" fill="{THEME_GREEN}" font-size="14" font-weight="700">♪</text>',
        f'<text x="30" y="19" fill="{THEME_FG}" font-size="11" font-weight="700">NETEASE</text>',
        f'<rect x="102" y="0" width="104" height="28" rx="6" fill="{THEME_GREEN}"/>',
        f'<text x="154" y="19" text-anchor="middle" fill="#000" font-size="11" '
        f'font-weight="800" letter-spacing="0.5">{nick}</text>',
        f'</g>',
    ]

    cy = HEADER_H + 4
    label = "Top This Week:" if show_weekly else "Current Playing:"
    parts.append(
        f'<text x="{WIDTH / 2}" y="{cy + 14}" text-anchor="middle" '
        f'fill="{THEME_FG}" font-size="14" font-weight="600">{label}</text>'
    )

    card_y = cy + 26
    parts.append(
        f'<rect x="{PAD}" y="{card_y}" width="{WIDTH - 2 * PAD}" '
        f'height="{CURRENT_H - PAD}" rx="10" fill="{THEME_CARD}"/>'
    )

    if show_weekly:
        cur = songs[0]
        parts.append(
            f'<image href="{escape(cur["cover"])}" x="{PAD + 10}" y="{card_y + 10}" '
            f'width="{COVER_LG}" height="{COVER_LG}" preserveAspectRatio="xMidYMid slice"/>'
        )
        text_x = PAD + 10 + COVER_LG + 16
        parts.append(
            f'<text x="{text_x}" y="{card_y + 38}" fill="{THEME_TITLE}" '
            f'font-size="16" font-weight="700">{escape(truncate(cur["name"], 22))}</text>'
        )
        parts.append(
            f'<text x="{text_x}" y="{card_y + 60}" fill="{THEME_MUTED}" '
            f'font-size="12">{escape(truncate(cur["artists"], 28))}</text>'
        )
        plays = cur.get("score", 0)
        if plays:
            parts.append(
                f'<text x="{text_x}" y="{card_y + 80}" fill="{THEME_GREEN}" '
                f'font-size="11" font-weight="600">▶ {plays} plays this week</text>'
            )
    else:
        msg = error_msg or "No plays recorded this week"
        parts.append(
            f'<text x="{WIDTH / 2}" y="{card_y + (CURRENT_H - PAD) / 2 + 4}" '
            f'text-anchor="middle" fill="{THEME_MUTED}" font-size="13">{escape(truncate(msg, 40))}</text>'
        )

    ry = card_y + (CURRENT_H - PAD) + 18
    parts.append(
        f'<text x="{WIDTH / 2}" y="{ry}" text-anchor="middle" fill="{THEME_FG}" '
        f'font-size="13" font-weight="600">▼ Weekly Ranking</text>'
    )

    list_y = ry + 14
    for i, song in enumerate(songs[1:], start=1):
        row_y = list_y + (i - 1) * RECENT_ROW_H
        parts.append(
            f'<image href="{escape(song["cover"])}" x="{PAD}" y="{row_y}" '
            f'width="{COVER_SM}" height="{COVER_SM}" preserveAspectRatio="xMidYMid slice"/>'
        )
        rank = f"{i + 1}."
        text_x = PAD + COVER_SM + 12
        parts.append(
            f'<text x="{text_x}" y="{row_y + 18}" fill="{THEME_TITLE}" '
            f'font-size="13" font-weight="600">'
            f'<tspan fill="{THEME_MUTED}" font-weight="500">{rank} </tspan>'
            f'{escape(truncate(song["name"], 22))}</text>'
        )
        parts.append(
            f'<text x="{text_x}" y="{row_y + 34}" fill="{THEME_MUTED}" '
            f'font-size="11">{escape(truncate(song["artists"], 26))}</text>'
        )
        plays = song.get("score", 0)
        parts.append(
            f'<text x="{WIDTH - PAD}" y="{row_y + 24}" text-anchor="end" '
            f'fill="{THEME_GREEN}" font-size="11" font-weight="600">{plays}×</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def write_svg(content: str) -> None:
    with open("musicCard.svg", "w", encoding="utf-8") as f:
        f.write(content)


def main() -> int:
    cookie = os.environ.get("MUSIC_U", "").strip()
    if not cookie:
        write_svg(build_svg("Kevin", [], "Set MUSIC_U secret in repo settings"))
        print("MUSIC_U not set; wrote placeholder.")
        return 0

    try:
        nickname, songs = fetch(cookie)
    except Exception as exc:
        print(f"Fetch failed: {exc}", file=sys.stderr)
        write_svg(build_svg("Kevin", [], f"API error — try again later"))
        return 0

    if not songs:
        write_svg(build_svg(nickname, [], "No plays this week yet"))
        print("No weekly plays; wrote empty-state card.")
        return 0

    write_svg(build_svg(nickname, songs))
    print(f"Wrote musicCard.svg (top 1 + {len(songs) - 1} ranked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())