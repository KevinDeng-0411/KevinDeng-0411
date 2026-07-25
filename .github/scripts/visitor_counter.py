"""Generate a kawaii-style visitor counter card.

Daily GitHub Actions run pulls unique-visitor counts from the GitHub Traffic
API (14-day rolling window) and accumulates them into visitors.json. A
random SFW anime illustration from waifu.pics is fetched each run, base64
embedded into the SVG so visitors don't hit any external network - same
pattern netease.py uses for album covers.

Requires a classic PAT with `repo` scope stored as VISITOR_TOKEN (Traffic
API rejects fine-grained tokens and GITHUB_TOKEN cannot read it).
"""

import base64
import datetime as _dt
import json
import os
import random
import sys
import urllib.error
import urllib.request

OWNER = "KevinDeng-0411"
REPO = "KevinDeng-0411"

TAGS = ["neko", "kitsune"]

THEME_BG = "#1a1b27"
THEME_CARD = "#24283b"
THEME_FG = "#c0caf5"
THEME_TITLE = "#ffffff"
THEME_MUTED = "#565f89"
THEME_PINK = "#f7768e"
THEME_YELLOW = "#e0af68"

WIDTH = 460
HEIGHT = 180
PAD = 24
CHAR_SIZE = 80
CHAR_RADIUS = 12

HISTORY_PATH = "visitors.json"
LAST_CHAR_PATH = "last_character.json"
SVG_PATH = "visitorCard.svg"


class TrafficAPIError(RuntimeError):
    pass


def fetch_traffic(token: str, owner: str, repo: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/traffic/views",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "github-profile-visitor-bot",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def load_history() -> dict:
    today = _dt.date.today().isoformat()
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            h = json.load(f)
        if not isinstance(h, dict) or "total" not in h:
            raise ValueError("malformed history")
        h.setdefault("since", today)
        h.setdefault("seen_days", [])
        h.setdefault("last_seen", None)
        return h
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return {"total": 0, "since": today, "seen_days": [], "last_seen": None}


def save_history(h: dict) -> None:
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)


def accumulate(history: dict, traffic: dict) -> dict:
    seen = set(history.get("seen_days", []))
    for entry in traffic.get("views", []):
        day = entry.get("timestamp", "")[:10]
        if day and day not in seen:
            history["total"] += int(entry.get("uniques", 0))
            seen.add(day)
            history["last_seen"] = day
    history["seen_days"] = sorted(seen)[-14:]
    return history


def fetch_character() -> dict | None:
    tag = random.choice(TAGS)
    try:
        meta_req = urllib.request.Request(
            f"https://nekos.best/api/v2/{tag}",
            headers={"User-Agent": "github-profile-visitor-bot"},
        )
        with urllib.request.urlopen(meta_req, timeout=15) as resp:
            results = json.loads(resp.read()).get("results", [])
        if not results:
            return None
        url = results[0].get("url")
        if not url:
            return None

        img_req = urllib.request.Request(
            url,
            headers={"User-Agent": "github-profile-visitor-bot"},
        )
        with urllib.request.urlopen(img_req, timeout=20) as resp:
            data = resp.read()

        data_uri = resize_to_data_uri(data, size=200)
        return {
            "data_uri": data_uri,
            "tag": tag,
            "source": url,
        }
    except Exception as exc:
        print(f"character fetch failed ({tag}): {exc}", file=sys.stderr)
        return None


def resize_to_data_uri(data: bytes, size: int = 200) -> str:
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB").resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except ImportError:
        mime = "image/png"
        return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def load_last_character() -> dict | None:
    try:
        with open(LAST_CHAR_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_last_character(char: dict) -> None:
    with open(LAST_CHAR_PATH, "w", encoding="utf-8") as f:
        json.dump(char, f, indent=2, ensure_ascii=False)


def draw_fallback_ghost(cx: int, cy: int) -> list[str]:
    body_top = cy - 30
    body_bottom = cy + 22
    path = (
        f"M {cx - 25},{body_top + 25} "
        f"a 25,25 0 1 1 50,0 "
        f"v {body_bottom - body_top - 25} "
        f"q -8,8 -16,0 q -8,-8 -16,0 q -8,8 -18,0 z"
    )
    return [
        f'<path d="{path}" fill="{THEME_FG}"/>',
        f'<ellipse cx="{cx - 9}" cy="{body_top + 22}" rx="3.5" ry="5.5" fill="{THEME_BG}"/>',
        f'<ellipse cx="{cx + 9}" cy="{body_top + 22}" rx="3.5" ry="5.5" fill="{THEME_BG}"/>',
        f'<circle cx="{cx - 15}" cy="{body_top + 30}" r="3" fill="{THEME_PINK}" opacity="0.7"/>',
        f'<circle cx="{cx + 15}" cy="{body_top + 30}" r="3" fill="{THEME_PINK}" opacity="0.7"/>',
    ]


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(total: int, today: int, since: str,
              character: dict | None = None, error: str = "") -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'font-family="-apple-system, Segoe UI, Roboto, sans-serif">',
        f'<rect width="100%" height="100%" fill="{THEME_BG}" rx="12"/>',
        f'<defs><clipPath id="char-round">'
        f'<rect x="{PAD}" y="{PAD}" width="{CHAR_SIZE}" height="{CHAR_SIZE}" '
        f'rx="{CHAR_RADIUS}"/></clipPath></defs>',
    ]

    if character and character.get("data_uri"):
        parts.append(
            f'<image href="{character["data_uri"]}" x="{PAD}" y="{PAD}" '
            f'width="{CHAR_SIZE}" height="{CHAR_SIZE}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#char-round)"/>'
        )
        parts.append(
            f'<rect x="{PAD}" y="{PAD}" width="{CHAR_SIZE}" height="{CHAR_SIZE}" '
            f'rx="{CHAR_RADIUS}" fill="none" stroke="{THEME_PINK}" stroke-width="1.5" '
            f'opacity="0.6"/>'
        )
    else:
        parts.append(
            f'<rect x="{PAD}" y="{PAD}" width="{CHAR_SIZE}" height="{CHAR_SIZE}" '
            f'rx="{CHAR_RADIUS}" fill="{THEME_CARD}"/>'
        )
        parts.extend(draw_fallback_ghost(PAD + CHAR_SIZE // 2, PAD + CHAR_SIZE // 2))

    text_x = PAD + CHAR_SIZE + 24
    num_y = PAD + 38
    parts.append(
        f'<text x="{text_x}" y="{num_y}" fill="{THEME_TITLE}" font-size="40" '
        f'font-weight="800">{total:,}</text>'
    )
    parts.append(
        f'<text x="{text_x}" y="{num_y + 22}" fill="{THEME_PINK}" font-size="12" '
        f'font-weight="700" letter-spacing="2">VISITORS</text>'
    )

    tag_label = (character.get("tag") if character else None) or "ghost"
    sub = f"since {since}  ·  today +{today}  ·  {tag_label}"
    parts.append(
        f'<text x="{text_x}" y="{num_y + 42}" fill="{THEME_MUTED}" font-size="11">'
        f'{escape(sub)}</text>'
    )

    if error:
        parts.append(
            f'<text x="{WIDTH - PAD}" y="{HEIGHT - 12}" text-anchor="end" '
            f'fill="{THEME_YELLOW}" font-size="10">⚠ {escape(error[:48])}</text>'
        )
    else:
        parts.append(
            f'<text x="{WIDTH - PAD}" y="{HEIGHT - 12}" text-anchor="end" '
            f'fill="{THEME_MUTED}" font-size="10" opacity="0.6">auto-updated daily</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def write_svg(content: str) -> None:
    with open(SVG_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> int:
    token = os.environ.get("VISITOR_TOKEN", "").strip()
    history = load_history()
    today_iso = _dt.date.today().isoformat()
    error = ""
    today_count = 0

    if not token:
        error = "Set VISITOR_TOKEN"
        print("VISITOR_TOKEN not set; using cached history.")
    else:
        try:
            traffic = fetch_traffic(token, OWNER, REPO)
            history = accumulate(history, traffic)
            today_count = sum(
                int(e.get("uniques", 0))
                for e in traffic.get("views", [])
                if e.get("timestamp", "")[:10] == today_iso
            )
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}"
            print(f"Traffic API HTTP {exc.code}: {exc.read().decode()[:200]}", file=sys.stderr)
        except Exception as exc:
            error = f"API error: {exc}"
            print(f"Traffic API error: {exc}", file=sys.stderr)

    save_history(history)

    char = fetch_character()
    if char:
        save_last_character(char)
    else:
        char = load_last_character()

    write_svg(build_svg(history["total"], today_count, history["since"], char, error))
    print(f"Wrote {SVG_PATH} (total={history['total']}, today=+{today_count}, "
          f"tag={char.get('tag') if char else 'ghost'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
