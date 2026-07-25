"""Generate NetEase Cloud Music weekly ranking card.

NetEase deprecated /api/v1/play/record/week — the new endpoint is
/api/v1/play/record with type=1, which still returns weekData sorted by
play count within the past 7 days. We render that as a Spotify-style
"Recently Played" list with album art and play counts.

Real-time "currently playing" isn't available via NetEase's public API,
so we don't try to show it.
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
THEME_MUTED = "#565f89"
THEME_GREEN = "#1db954"

WIDTH = 460
COVER_SM = 40
PAD = 18
ROW_GAP = 8
HEADER_H = 56
LIST_HEADER_H = 24
FOOTER_H = 14


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
    n = len(songs)
    height = HEADER_H + LIST_HEADER_H + max(n, 1) * (COVER_SM + ROW_GAP) + FOOTER_H
    nick = escape((nickname or "KEVIN").upper())[:14]
    show_list = bool(songs) and not error_msg

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'font-family="-apple-system, Segoe UI, Roboto, sans-serif">',
        f'<rect width="100%" height="100%" fill="{THEME_BG}" rx="12"/>',
        f'<g transform="translate({PAD},{PAD})">',
        f'<rect x="0" y="0" width="96" height="28" rx="6" fill="#1f2330"/>',
        f'<text x="14" y="19" fill="{THEME_GREEN}" font-size="14" font-weight="700">♪</text>',
        f'<text x="30" y="19" fill="{THEME_FG}" font-size="11" font-weight="700">NETEASE</text>',
        f'<rect x="102" y="0" width="104" height="28" rx="6" fill="{THEME_GREEN}"/>',
        f'<text x="154" y="19" text-anchor="middle" fill="#000" font-size="11" '
        f'font-weight="800" letter-spacing="0.5">{nick}</text>',
        f'</g>',
    ]

    # List header
    lh_y = HEADER_H + 18
    label = "Recently Played · Past 7 Days" if show_list else (error_msg or "No plays yet")
    parts.append(
        f'<text x="{WIDTH / 2}" y="{lh_y}" text-anchor="middle" fill="{THEME_FG}" '
        f'font-size="13" font-weight="600">{escape(truncate(label, 38))}</text>'
    )

    if not show_list:
        msg_y = lh_y + 40
        parts.append(
            f'<text x="{WIDTH / 2}" y="{msg_y}" text-anchor="middle" fill="{THEME_MUTED}" '
            f'font-size="12">Once you start playing on NetEase, your weekly ranking shows up here.</text>'
        )
    else:
        list_y = lh_y + 18
        for i, song in enumerate(songs):
            row_y = list_y + i * (COVER_SM + ROW_GAP)
            parts.append(
                f'<image href="{escape(song["cover"])}" x="{PAD}" y="{row_y}" '
                f'width="{COVER_SM}" height="{COVER_SM}" preserveAspectRatio="xMidYMid slice"/>'
            )
            text_x = PAD + COVER_SM + 12
            parts.append(
                f'<text x="{text_x}" y="{row_y + 18}" fill="{THEME_TITLE}" '
                f'font-size="13" font-weight="600">'
                f'<tspan fill="{THEME_MUTED}" font-weight="500">{i + 1:>2}. </tspan>'
                f'{escape(truncate(song["name"], 22))}</text>'
            )
            parts.append(
                f'<text x="{text_x}" y="{row_y + 34}" fill="{THEME_MUTED}" '
                f'font-size="11">{escape(truncate(song["artists"], 26))}</text>'
            )
            plays = song.get("score", 0)
            parts.append(
                f'<text x="{WIDTH - PAD}" y="{row_y + 24}" text-anchor="end" '
                f'fill="{THEME_GREEN}" font-size="12" font-weight="700">{plays}×</text>'
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
        write_svg(build_svg("Kevin", [], "API error — try again later"))
        return 0

    if not songs:
        write_svg(build_svg(nickname, [], "No plays this week"))
        print("No weekly plays; wrote empty-state card.")
        return 0

    write_svg(build_svg(nickname, songs))
    print(f"Wrote musicCard.svg ({len(songs)} songs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())