"""Generate NetEase Cloud Music weekly ranking card.

NetEase deprecated /api/v1/play/record/week — the new endpoint is
/api/v1/play/record with type=1, which still returns weekData sorted by
play count within the past 7 days. We render that as a Spotify-style
"Recently Played" list with album art and play counts.

Real-time "currently playing" isn't available via NetEase's public API,
so we don't try to show it.
"""

import base64
import datetime as _dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

THEME_BG = "#1a1b27"
THEME_CARD = "#24283b"
THEME_FG = "#c0caf5"
THEME_TITLE = "#ffffff"
THEME_MUTED = "#565f89"
THEME_RED = "#c20c0c"
THEME_RED_LIGHT = "#e72d2c"
THEME_RED_FAINT = "#7a1e1e"


def fetch_cover_data_uri(url: str) -> str:
    """Download album cover and return as base64 data URI.

    GitHub renders SVGs via <img src>, which blocks nested <image href>
    external references — they only render when inlined as data URIs.
    """
    if not url:
        return ""

    cdn_nodes = ["p1", "p2", "p3", "p4"]
    chrome_ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )

    for attempt in range(3):
        test_url = url
        if attempt > 0:
            for node in cdn_nodes:
                if f"{node}.music.126.net" in url:
                    new_node = cdn_nodes[attempt % len(cdn_nodes)]
                    test_url = url.replace(f"{node}.music.126.net", f"{new_node}.music.126.net")
                    break
        try:
            req = urllib.request.Request(
                test_url,
                headers={
                    "User-Agent": chrome_ua,
                    "Referer": "https://music.163.com/",
                },
            )
            data = urllib.request.urlopen(req, timeout=20).read()
            if len(data) < 100:
                raise ValueError(f"suspiciously small response: {len(data)} bytes")
            return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        except Exception as exc:
            print(f"cover fetch attempt {attempt+1}/3 failed for {test_url[:80]}: {exc}", file=sys.stderr)
            if attempt < 2:
                time.sleep(2)

    print(f"cover fetch all 3 attempts failed, falling back to URL: {url[:80]}", file=sys.stderr)
    return url

WIDTH = 460
COVER_SM = 40
PAD = 18
ROW_GAP = 8
HEADER_H = 56
LIST_HEADER_H = 24
FOOTER_H = 14


class CookieExpiredError(RuntimeError):
    """Raised when NetEase API rejects the cookie."""


class TransientApiError(RuntimeError):
    """Raised when NetEase API returns 200 but malformed body (temp flake)."""


def fetch(cookie: str) -> tuple[str, list[dict]]:
    headers = {
        "Cookie": f"MUSIC_U={cookie}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Referer": "https://music.163.com/",
    }

    acc_resp = urllib.request.urlopen(
        urllib.request.Request(
            "https://music.163.com/api/nuser/account/get", headers=headers
        ),
        timeout=15,
    )
    acc_body = acc_resp.read().decode("utf-8", errors="replace")
    acc_headers = dict(acc_resp.headers.items())
    try:
        account = json.loads(acc_body)
    except json.JSONDecodeError:
        print(f"[debug] account API non-JSON body (first 500): {acc_body[:500]}", file=sys.stderr)
        print(f"[debug] account API headers: {acc_headers}", file=sys.stderr)
        raise TransientApiError("account API returned non-JSON body")
    code = account.get("code")
    if code in (301, -460, 404):
        print(f"[debug] account API cookie-expired body: {acc_body[:500]}", file=sys.stderr)
        print(f"[debug] account API headers: {acc_headers}", file=sys.stderr)
        raise CookieExpiredError(f"account API code={code}: {account.get('message', '')}")
    if code != 200 or not account.get("account"):
        print(f"[debug] account API anomaly body: {acc_body[:500]}", file=sys.stderr)
        print(f"[debug] account API headers: {acc_headers}", file=sys.stderr)
        set_cookies = acc_resp.headers.get_all("Set-Cookie") or []
        for sc in set_cookies:
            if "MUSIC_U=" in sc:
                new_mu = sc.split("MUSIC_U=")[1].split(";")[0]
                print(f"[debug] Set-Cookie returned new MUSIC_U (len={len(new_mu)})", file=sys.stderr)
                break
        raise TransientApiError(f"account API code={code}: {account.get('message', '')}")
    uid = account["account"]["id"]
    nickname = account["profile"]["nickname"]

    data = urllib.parse.urlencode({"uid": uid, "type": "1"}).encode()
    week_resp = urllib.request.urlopen(
        urllib.request.Request(
            "https://music.163.com/api/v1/play/record",
            data=data,
            headers=headers,
        ),
        timeout=15,
    )
    week_body = week_resp.read().decode("utf-8", errors="replace")
    week_headers = dict(week_resp.headers.items())
    try:
        week = json.loads(week_body)
    except json.JSONDecodeError:
        print(f"[debug] play-record API non-JSON body (first 500): {week_body[:500]}", file=sys.stderr)
        print(f"[debug] play-record API headers: {week_headers}", file=sys.stderr)
        raise TransientApiError("play-record API returned non-JSON body")
    if week.get("code") != 200:
        print(f"[debug] play-record API anomaly body: {week_body[:500]}", file=sys.stderr)
        print(f"[debug] play-record API headers: {week_headers}", file=sys.stderr)
        raise CookieExpiredError(f"play-record API code={week.get('code')}: {week.get('message', '')}")

    songs = []
    for item in week.get("weekData", []):
        s = item.get("song") or {}
        album = s.get("album") or s.get("al") or {}
        pic = album.get("picUrl", "")
        if pic.startswith("http://"):
            pic = "https://" + pic[len("http://"):]
        if pic and "?" in pic:
            pic = pic.split("?")[0] + "?param=300y300"
        elif pic:
            pic = pic + "?param=300y300"
        artists = s.get("artists") or s.get("ar") or []
        songs.append(
            {
                "name": s.get("name", ""),
                "artists": "/".join(a.get("name", "") for a in artists)
                or (s.get("artist") or {}).get("name", ""),
                "cover": fetch_cover_data_uri(pic),
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
        f'<text x="14" y="19" fill="{THEME_RED_LIGHT}" font-size="14" font-weight="700">♪</text>',
        f'<text x="30" y="19" fill="{THEME_FG}" font-size="11" font-weight="700">NETEASE</text>',
        f'<rect x="102" y="0" width="104" height="28" rx="6" fill="{THEME_RED}"/>',
        f'<text x="154" y="19" text-anchor="middle" fill="#fff" font-size="11" '
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
            cover = song.get("cover") or ""
            if cover:
                parts.append(
                    f'<image href="{cover}" x="{PAD}" y="{row_y}" '
                    f'width="{COVER_SM}" height="{COVER_SM}" preserveAspectRatio="xMidYMid slice"/>'
                )
            else:
                parts.append(
                    f'<rect x="{PAD}" y="{row_y}" width="{COVER_SM}" height="{COVER_SM}" '
                    f'rx="4" fill="{THEME_RED_FAINT}"/>'
                )
                parts.append(
                    f'<text x="{PAD + COVER_SM / 2}" y="{row_y + COVER_SM / 2 + 4}" '
                    f'text-anchor="middle" fill="#fff" font-size="11" font-weight="700">'
                    f'{i + 1}</text>'
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

    parts.append("</svg>")
    return "\n".join(parts)


def write_svg(content: str) -> None:
    with open("musicCard.svg", "w", encoding="utf-8") as f:
        f.write(content)


README_PATH = "README.md"
BANNER_START = "<!-- NETEASE_BANNER_START -->"
BANNER_END = "<!-- NETEASE_BANNER_END -->"
SECRETS_URL = (
    "https://github.com/KevinDeng-0411/KevinDeng-0411/settings/secrets/actions"
)


def update_readme_banner(error_msg: str | None) -> None:
    """Insert or remove the cookie-expired banner at the top of README.

    error_msg: str → insert banner with this message
    error_msg: None → strip any existing banner
    """
    try:
        with open(README_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return

    if error_msg is None:
        # Remove any existing banner block
        pattern = re.compile(
            re.escape(BANNER_START) + r".*?" + re.escape(BANNER_END) + r"\n?",
            re.DOTALL,
        )
        new_content = pattern.sub("", content)
    else:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        banner = (
            f"{BANNER_START}\n"
            f"> ⚠️ **NetEase Music Card unavailable** — Cookie expired. "
            f"[Update `MUSIC_U` secret]({SECRETS_URL}) · "
            f"_last attempt: {ts}, error: `{error_msg[:80]}`_\n"
            f"{BANNER_END}\n\n"
        )
        pattern = re.compile(
            re.escape(BANNER_START) + r".*?" + re.escape(BANNER_END) + r"\n?",
            re.DOTALL,
        )
        if pattern.search(content):
            new_content = pattern.sub(banner.rstrip("\n") + "\n", content, count=1)
        else:
            new_content = banner + content

    if new_content != content:
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"README.md banner {'set' if error_msg else 'cleared'}.")


def fetch_with_retry(cookie: str, attempts: int = 3, delay: int = 5) -> tuple[str, list[dict]]:
    last_exc = None
    for i in range(attempts):
        try:
            return fetch(cookie)
        except CookieExpiredError:
            raise
        except TransientApiError as exc:
            last_exc = exc
            if i < attempts - 1:
                print(f"Transient API error: {exc}; retry {i+1}/{attempts} in {delay}s", file=sys.stderr)
                time.sleep(delay)
    raise last_exc


def main() -> int:
    cookie = os.environ.get("MUSIC_U", "").strip()
    if not cookie:
        write_svg(build_svg("Kevin", [], "Set MUSIC_U secret in repo settings"))
        update_readme_banner("MUSIC_U secret is not set")
        print("MUSIC_U not set; wrote placeholder + banner.")
        return 0

    try:
        nickname, songs = fetch_with_retry(cookie)
    except CookieExpiredError as exc:
        print(f"Cookie expired: {exc}", file=sys.stderr)
        write_svg(build_svg("Kevin", [], "Cookie expired"))
        update_readme_banner(str(exc))
        return 0
    except TransientApiError as exc:
        print(f"Transient API error after retries: {exc}", file=sys.stderr)
        update_readme_banner(f"transient API error (will retry next run): {exc}")
        return 0
    except Exception as exc:
        print(f"Fetch failed: {exc}", file=sys.stderr)
        update_readme_banner(f"transient API error: {exc}")
        return 0

    if not songs:
        write_svg(build_svg(nickname, [], "No plays this week"))
        update_readme_banner(None)
        print("No weekly plays; wrote empty-state card.")
        return 0

    write_svg(build_svg(nickname, songs))
    update_readme_banner(None)
    print(f"Wrote musicCard.svg ({len(songs)} songs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())