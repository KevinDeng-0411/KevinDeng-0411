"""Generate daily quote SVG card using hitokoto (一言)."""

import json
import sys
import urllib.request


THEME_BG = "#1f2330"
THEME_FG = "#c0caf5"
THEME_ACCENT = "#bb9af7"
THEME_MUTED = "#565f89"


def fetch_quote() -> dict:
    req = urllib.request.Request(
        "https://v1.hitokoto.cn/?encode=json",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def build_svg(hitokoto: str, source: str) -> str:
    width = 520
    height = 110
    safe = (
        hitokoto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    safe_source = (
        source.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="-apple-system, Segoe UI, Roboto, sans-serif">'
        f'<rect width="100%" height="100%" fill="{THEME_BG}" rx="10"/>'
        f'<text x="20" y="38" fill="{THEME_ACCENT}" font-size="14">❝</text>'
        f'<text x="36" y="56" fill="{THEME_FG}" font-size="15">{safe}</text>'
        f'<text x="{width - 20}" y="88" text-anchor="end" fill="{THEME_MUTED}" font-size="12">'
        f'— {safe_source}</text>'
        f'</svg>'
    )


def main() -> int:
    try:
        data = fetch_quote()
        hitokoto = data.get("hitokoto", "Stay hungry, stay foolish.")
        source = data.get("from", "Unknown") or "Unknown"
    except Exception as exc:
        print(f"Fetch failed: {exc}", file=sys.stderr)
        hitokoto = "Stay hungry, stay foolish."
        source = "Joaquin Phoenix / Stewart Brand"

    svg = build_svg(hitokoto, source)
    with open("quote.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote quote.svg.")
    return 0


if __name__ == "__main__":
    sys.exit(main())