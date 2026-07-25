"""Generate GitHub profile stats cards via the GraphQL API.

Produces three SVGs at the repo root:
  - stats-card.svg      (commits / stars / repos / current streak overview)
  - streak-card.svg     (current + longest streak with mini heatmap)
  - languages-card.svg  (top languages with proportional bars)

Uses the workflow-provided GITHUB_TOKEN (5000/hr authenticated rate limit)
so no personal access token is needed in production.
"""

import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.request

USERNAME = os.environ.get("GITHUB_USERNAME", "KevinDeng-0411")

# --- Theme (mirrors .github/scripts/netease.py for visual consistency) ---
THEME_BG = "#1a1b27"
THEME_CARD = "#24283b"
THEME_FG = "#c0caf5"
THEME_TITLE = "#ffffff"
THEME_MUTED = "#565f89"
THEME_RED = "#c20c0c"
THEME_RED_LIGHT = "#e72d2c"
HEATMAP_LEVELS = ["#16161e", "#3b2238", "#6b1f33", "#a31628", "#c20c0c"]

# Fallback colors for common languages (used when API returns no color)
LANG_COLORS = {
    "Java": "#b07219",
    "Python": "#3572A5",
    "Go": "#00ADD8",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Rust": "#dea584",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Shell": "#89e051",
    "Bash": "#89e051",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "SCSS": "#c6538c",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "Dart": "#00B4AB",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
    "YAML": "#cb171e",
    "JSON": "#292929",
    "Markdown": "#083fa1",
    "SQL": "#dad8d8",
    "Lua": "#000080",
    "Perl": "#0298c3",
    "Scala": "#c22d40",
    "Groovy": "#4298b8",
    "GraphQL": "#e10098",
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    repositories(ownerAffiliations: OWNER, first: 100, isFork: false) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


# ---------- API ----------

def fetch(token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "github-profile-stats-bot",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


# ---------- Computations ----------

def flatten_days(weeks: list[dict]) -> list[dict]:
    return [d for w in weeks for d in w["contributionDays"]]


def compute_streaks(days: list[dict]) -> tuple[int, int]:
    """Return (current_streak, longest_streak) in days."""
    if not days:
        return 0, 0
    longest = 0
    run = 0
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            if run > longest:
                longest = run
        else:
            run = 0
    # current streak: from the last day backward
    current = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            current += 1
        else:
            break
    return current, longest


def aggregate_languages(repos: list[dict]) -> list[dict]:
    """Sum language sizes across all repos; return sorted list with color."""
    totals: dict[str, dict] = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            entry = totals.setdefault(
                edge["node"]["name"],
                {"size": 0, "color": edge["node"].get("color")},
            )
            entry["size"] += edge["size"]
    items = [
        {
            "name": name,
            "size": data["size"],
            "color": data["color"] or LANG_COLORS.get(name, THEME_MUTED),
        }
        for name, data in totals.items()
    ]
    items.sort(key=lambda x: x["size"], reverse=True)
    return items


def heatmap_color(count: int, max_count: int) -> str:
    if count == 0 or max_count == 0:
        return HEATMAP_LEVELS[0]
    ratio = count / max_count
    idx = min(int(ratio * len(HEATMAP_LEVELS)), len(HEATMAP_LEVELS) - 1)
    if count > 0 and idx == 0:
        idx = 1
    return HEATMAP_LEVELS[idx]


# ---------- SVG helpers ----------

def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_header(width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'font-family="-apple-system, Segoe UI, Roboto, sans-serif">'
        f'<rect width="100%" height="100%" fill="{THEME_BG}" rx="12"/>'
    )


def write_svg(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------- Card builders ----------

def build_stats_card(data: dict) -> str:
    W = 410
    cc = data["contributionsCollection"]
    repos = data["repositories"]
    total_commits = cc["totalCommitContributions"]
    total_contribs = cc["contributionCalendar"]["totalContributions"]
    total_stars = sum(r["stargazerCount"] for r in repos["nodes"])
    days = flatten_days(cc["contributionCalendar"]["weeks"])
    current, longest = compute_streaks(days)
    days_active = sum(1 for d in days if d["contributionCount"] > 0)

    H = 196
    PAD = 18
    parts = [svg_header(W, H)]

    # Title
    parts.append(
        f'<text x="{PAD}" y="{PAD + 14}" fill="{THEME_FG}" '
        f'font-size="13" font-weight="700">⚡ GitHub Activity</text>'
    )
    parts.append(
        f'<text x="{W - PAD}" y="{PAD + 14}" text-anchor="end" fill="{THEME_MUTED}" '
        f'font-size="11">last 365 days</text>'
    )

    # 4-cell metric row
    cell_y = PAD + 30
    cell_h = 60
    cell_w = (W - 2 * PAD - 12) / 4
    metrics = [
        ("Commits", total_commits, THEME_TITLE),
        ("Contribs", total_contribs, THEME_TITLE),
        ("Stars", total_stars, THEME_TITLE),
        ("Repos", repos["totalCount"], THEME_TITLE),
    ]
    for i, (label, value, _) in enumerate(metrics):
        x = PAD + i * (cell_w + 4)
        parts.append(
            f'<rect x="{x}" y="{cell_y}" width="{cell_w}" height="{cell_h}" '
            f'rx="8" fill="{THEME_CARD}"/>'
        )
        parts.append(
            f'<text x="{x + cell_w / 2}" y="{cell_y + 24}" text-anchor="middle" '
            f'fill="{THEME_RED_LIGHT}" font-size="20" font-weight="700">'
            f'{value}</text>'
        )
        parts.append(
            f'<text x="{x + cell_w / 2}" y="{cell_y + 44}" text-anchor="middle" '
            f'fill="{THEME_MUTED}" font-size="10" font-weight="600" '
            f'letter-spacing="0.5">{label.upper()}</text>'
        )

    # Streak summary line
    streak_y = cell_y + cell_h + 26
    parts.append(
        f'<text x="{PAD}" y="{streak_y}" fill="{THEME_MUTED}" font-size="11">'
        f'🔥 Current streak '
        f'<tspan fill="{THEME_FG}" font-weight="700">{current} days</tspan>'
        f'  ·  🏆 Longest '
        f'<tspan fill="{THEME_FG}" font-weight="700">{longest} days</tspan>'
        f'  ·  {days_active} active days</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def build_streak_card(data: dict) -> str:
    W = 410
    cc = data["contributionsCollection"]
    days = flatten_days(cc["contributionCalendar"]["weeks"])
    current, longest = compute_streaks(days)
    max_count = max((d["contributionCount"] for d in days), default=0) or 1
    active = sum(1 for d in days if d["contributionCount"] > 0)

    H = 150
    PAD = 18
    parts = [svg_header(W, H)]

    # Title
    parts.append(
        f'<text x="{PAD}" y="{PAD + 14}" fill="{THEME_FG}" '
        f'font-size="13" font-weight="700">🔥 Contribution Streak</text>'
    )

    # Two big numbers
    y_num = PAD + 56
    y_lbl = y_num + 18

    half = (W - 2 * PAD) / 2
    # Current
    parts.append(
        f'<text x="{PAD}" y="{y_num}" fill="{THEME_RED_LIGHT}" font-size="32" '
        f'font-weight="800">{current}</text>'
    )
    parts.append(
        f'<text x="{PAD + 60}" y="{y_num}" fill="{THEME_MUTED}" font-size="13">'
        f'current</text>'
    )
    # Longest
    parts.append(
        f'<text x="{PAD + half}" y="{y_num}" fill="{THEME_TITLE}" font-size="32" '
        f'font-weight="800">{longest}</text>'
    )
    parts.append(
        f'<text x="{PAD + half + 60}" y="{y_num}" fill="{THEME_MUTED}" font-size="13">'
        f'longest</text>'
    )
    parts.append(
        f'<text x="{PAD}" y="{y_lbl}" fill="{THEME_MUTED}" font-size="11">'
        f'{active} of {len(days)} days active</text>'
    )

    # Mini heatmap (compact 7x14 cells, last ~14 weeks)
    weeks = cc["contributionCalendar"]["weeks"]
    last_weeks = weeks[-14:]
    cell = 5
    gap = 1
    grid_w = 14 * (cell + gap) - gap
    grid_x = W - PAD - grid_w
    grid_y = y_lbl + 10
    for wi, week in enumerate(last_weeks):
        for di, day in enumerate(week["contributionDays"]):
            x = grid_x + wi * (cell + gap)
            y = grid_y + di * (cell + gap)
            color = heatmap_color(day["contributionCount"], max_count)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="1" fill="{color}"/>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def build_languages_card(data: dict) -> str:
    W = 410
    PAD = 18
    ROW_H = 22
    HEADER_H = 36
    FOOTER_H = 12

    langs = aggregate_languages(data["repositories"]["nodes"])
    top = langs[:5]
    shown_total = sum(l["size"] for l in top)
    grand_total = sum(l["size"] for l in langs)
    if grand_total > shown_total and top:
        top.append(
            {
                "name": "Other",
                "size": grand_total - shown_total,
                "color": THEME_MUTED,
            }
        )

    H = HEADER_H + len(top) * ROW_H + FOOTER_H
    parts = [svg_header(W, H)]

    # Title
    parts.append(
        f'<text x="{PAD}" y="{PAD + 8}" fill="{THEME_FG}" '
        f'font-size="13" font-weight="700">🧪 Top Languages</text>'
    )
    parts.append(
        f'<text x="{W - PAD}" y="{PAD + 8}" text-anchor="end" fill="{THEME_MUTED}" '
        f'font-size="11">across public repos</text>'
    )

    # Rows
    bar_x = PAD + 110
    bar_w = W - PAD - bar_x - 40  # leave space for % label
    row_y = HEADER_H
    for lang in top:
        pct = (lang["size"] / grand_total * 100) if grand_total else 0
        fill_w = bar_w * (lang["size"] / grand_total) if grand_total else 0

        # Color dot
        parts.append(
            f'<circle cx="{PAD + 4}" cy="{row_y + 8}" r="4" fill="{lang["color"]}"/>'
        )
        # Name
        parts.append(
            f'<text x="{PAD + 16}" y="{row_y + 12}" fill="{THEME_TITLE}" '
            f'font-size="12" font-weight="600">{escape(lang["name"])}</text>'
        )
        # Bar background
        parts.append(
            f'<rect x="{bar_x}" y="{row_y + 3}" width="{bar_w}" height="10" '
            f'rx="5" fill="{THEME_CARD}"/>'
        )
        # Bar fill
        parts.append(
            f'<rect x="{bar_x}" y="{row_y + 3}" width="{fill_w:.1f}" height="10" '
            f'rx="5" fill="{lang["color"]}"/>'
        )
        # Percentage
        parts.append(
            f'<text x="{W - PAD}" y="{row_y + 12}" text-anchor="end" fill="{THEME_FG}" '
            f'font-size="11" font-weight="700">{pct:.1f}%</text>'
        )
        row_y += ROW_H

    parts.append("</svg>")
    return "\n".join(parts)


# ---------- Main ----------

def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("GITHUB_TOKEN env var not set.", file=sys.stderr)
        return 1

    try:
        raw = fetch(token)
    except urllib.error.HTTPError as e:
        print(f"GitHub API HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"GitHub API error: {e}", file=sys.stderr)
        return 1

    if "errors" in raw:
        print(f"GraphQL errors: {raw['errors']}", file=sys.stderr)
        return 1

    user = raw["data"]["user"]
    write_svg("stats-card.svg", build_stats_card(user))
    print("Wrote stats-card.svg")

    write_svg("streak-card.svg", build_streak_card(user))
    print("Wrote streak-card.svg")

    write_svg("languages-card.svg", build_languages_card(user))
    print("Wrote languages-card.svg")

    return 0


if __name__ == "__main__":
    sys.exit(main())