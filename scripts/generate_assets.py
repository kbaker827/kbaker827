#!/usr/bin/env python3
"""
Generate profile README assets:
  - assets/github-stats.svg  (stars / commits / repos / forks card)
  - assets/word-cloud.png    (technologies & platforms word cloud)
  - assets/trend-chart.png   (yearly stars / repos / commits trend)
  - assets/pin-<repo>.svg    (cards for the most popular repositories)

Also rewrites the block between the PINNED markers in README.md so the
"Most Popular Repositories" section always matches the generated cards.
"""

import os
import re
import sys
from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from wordcloud import WordCloud

try:
    import requests
except ImportError:
    sys.exit("requests is required: pip install requests")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
USERNAME = "kbaker827"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
README_PATH = os.path.join(ROOT_DIR, "README.md")

PINNED_COUNT = 6
FIRST_YEAR = 2018
PINNED_START = "<!-- PINNED:START -->"
PINNED_END = "<!-- PINNED:END -->"

BG_COLOR = "#0d1117"
PANEL_COLOR = "#161b22"
BORDER_COLOR = "#30363d"
TEXT_COLOR = "#c9d1d9"
MUTED_COLOR = "#8b949e"

# ---------------------------------------------------------------------------
# Technology keywords → display name.
# Matched against repo topics, names and descriptions (most of my repos have
# no topics), so the cloud reflects what the repos *do*, not their language.
# ---------------------------------------------------------------------------
KEYWORD_MAP = {
    # Smart home
    "home assistant": "Home Assistant",
    "home-assistant": "Home Assistant",
    "homeassistant": "Home Assistant",
    "ha-": "Home Assistant",
    "hacs": "HACS",
    "govee": "Govee",
    "eufy": "Eufy RoboVac",
    "robovac": "Eufy RoboVac",
    "tempest": "WeatherFlow Tempest",
    "weatherflow": "WeatherFlow Tempest",
    "meater": "Meater",
    "hidratespark": "HidrateSpark",
    "hidrate": "HidrateSpark",
    "tesla": "Tesla",
    # Wearables
    "rokid": "Rokid Glasses",
    "ray-ban": "Meta Ray-Ban",
    "rayban": "Meta Ray-Ban",
    "pebble": "Pebble",
    # 3D printing
    "snapmaker": "Snapmaker U1",
    "sovol": "Sovol SV08",
    "klipper": "Klipper",
    "moonraker": "Moonraker",
    "orcaslicer": "OrcaSlicer",
    "orca": "OrcaSlicer",
    "3d print": "3D Printing",
    "3d-print": "3D Printing",
    "filament": "3D Printing",
    "firmware": "Firmware",
    # Microsoft / endpoint management
    "intune": "Microsoft Intune",
    "autopilot": "Windows Autopilot",
    "microsoft 365": "Microsoft 365",
    "m365": "Microsoft 365",
    "teams": "Microsoft Teams",
    "outlook": "Outlook",
    "sharepoint": "SharePoint",
    "onedrive": "OneDrive",
    "active directory": "Active Directory",
    "adexplorer": "Active Directory",
    "admx": "Group Policy",
    "group policy": "Group Policy",
    "windows": "Windows",
    "pdq": "PDQ Deploy",
    "lansweeper": "Lansweeper",
    "dell": "Dell",
    "osd": "OS Deployment",
    "mdt": "OS Deployment",
    "dsc": "PowerShell DSC",
    "dns": "DNS",
    "eap-tls": "EAP-TLS Wi-Fi",
    "wi-fi": "Wi-Fi",
    "wifi": "Wi-Fi",
    "adobe": "Adobe Acrobat",
    "macos": "macOS",
    # AI
    "claude": "Claude",
    "chatgpt": "ChatGPT",
    "openai": "OpenAI",
    "openclaw": "OpenClaw",
    "hermes": "Hermes Agent",
    "kimi": "Kimi",
    " ai ": "AI Assistants",
    "ai assistant": "AI Assistants",
    "agent": "AI Agents",
    "translation": "Translation",
    # Media / services
    "spotify": "Spotify",
    "youtube": "YouTube",
    "twitch": "Twitch",
    "lyrics": "Lyrics",
    "google maps": "Google Maps",
    "gmaps": "Google Maps",
    "fox news": "News",
    "foxnews": "News",
    "sports": "Sports Scores",
    "bluetooth": "Bluetooth",
    "github": "GitHub",
}

LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "Shell": "#89e051",
    "PowerShell": "#012456",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "C#": "#178600",
    "C++": "#f34b7d",
    "C": "#555555",
}

# Octicon path data (16×16 viewBox)
_ICON_STAR = (
    "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 "
    ".416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347"
    "l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 "
    "0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z"
)
_ICON_FORK = (
    "M5 3.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0zm0 2.122a2.25 "
    "2.25 0 1 0-1.5 0v.878A2.25 2.25 0 0 0 5.75 8.5h1.5v2.128a2.251 "
    "2.251 0 1 0 1.5 0V8.5h1.5a2.25 2.25 0 0 0 2.25-2.25v-.878a2.25 "
    "2.25 0 1 0-1.5 0v.878a.75.75 0 0 1-.75.75h-4.5A.75.75 0 0 1 5 "
    "6.25v-.878zm3.75 7.378a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 "
    "0zm3-8.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5z"
)
_ICON_REPO = (
    "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75"
    ".75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 "
    "0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5zm"
    "10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8zM5 "
    "12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25"
    ".25 0 0 1-.4.2l-1.45-1.087a.25.25 0 0 0-.3 0L5.4 15.7a.25"
    ".25 0 0 1-.4-.2z"
)
_ICON_COMMIT = (
    "M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32"
    "a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.5a2.5 "
    "2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z"
)

_SVG_FONT = (
    "-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, "
    "sans-serif"
)
_APPROX_CHAR_WIDTH = 7.2


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def get_repos():
    """Return all public repos for USERNAME, paginating as needed."""
    repos = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def get_commits_by_year():
    """Commit contributions per calendar year via the GraphQL API.

    One query per year instead of one REST call per (repo, year) pair.
    Requires a token; returns an empty dict without one.
    """
    if not GITHUB_TOKEN:
        print("  No GITHUB_TOKEN – skipping commit history.")
        return {}
    query = (
        "query($login:String!,$from:DateTime!,$to:DateTime!){"
        "user(login:$login){contributionsCollection(from:$from,to:$to)"
        "{totalCommitContributions restrictedContributionsCount}}}"
    )
    current_year = datetime.now(tz=timezone.utc).year
    commits = {}
    for year in range(FIRST_YEAR, current_year + 1):
        variables = {
            "login": USERNAME,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        }
        resp = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"GraphQL error for {year}: {payload['errors']}")
        coll = payload["data"]["user"]["contributionsCollection"]
        commits[year] = coll["totalCommitContributions"]
    return commits


# ---------------------------------------------------------------------------
# Word cloud
# ---------------------------------------------------------------------------

def repo_keywords(repo):
    """Return the set of display names a single repo matches."""
    text = " ".join(
        [
            repo["name"].lower(),
            (repo.get("description") or "").lower(),
            " ".join(repo.get("topics", [])),
        ]
    )
    text = f" {text} "
    return {name for key, name in KEYWORD_MAP.items() if key in text}


def build_word_frequencies(repos):
    freq = {}
    for repo in repos:
        for name in repo_keywords(repo):
            freq[name] = freq.get(name, 0) + 1
    return freq


def generate_word_cloud(repos, out_path):
    freq = build_word_frequencies(repos)
    if not freq:
        print("  No keywords found – skipping word cloud.")
        return

    wc = WordCloud(
        width=900,
        height=420,
        background_color=BG_COLOR,
        colormap="cool",
        max_words=70,
        relative_scaling=0.5,
        min_font_size=14,
        prefer_horizontal=0.85,
        collocations=False,
        margin=8,
        random_state=42,
    )
    wc.generate_from_frequencies(freq)

    fig, ax = plt.subplots(figsize=(9, 4.2))
    fig.patch.set_facecolor(BG_COLOR)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    print(f"  Word cloud saved -> {out_path}")


# ---------------------------------------------------------------------------
# Trend chart
# ---------------------------------------------------------------------------

def generate_trend_chart(repos, commits_by_year, out_path):
    current_year = datetime.now(tz=timezone.utc).year
    years = list(range(FIRST_YEAR, current_year + 1))

    stars_by_year = {y: 0 for y in years}
    repos_by_year = {y: 0 for y in years}
    for r in repos:
        year = int(r["created_at"][:4])
        if year in repos_by_year:
            repos_by_year[year] += 1
            stars_by_year[year] += r.get("stargazers_count", 0)

    stars_vals = list(np.cumsum([stars_by_year[y] for y in years]))
    repos_vals = [repos_by_year[y] for y in years]
    commits_vals = [commits_by_year.get(y, 0) for y in years]

    datasets = [
        ("Cumulative Stars", stars_vals, "#f1c40f", "o-"),
        ("Repositories Created", repos_vals, "#58a6ff", "s--"),
        ("Commits", commits_vals, "#3fb950", "^:"),
    ]

    x = np.arange(len(years))
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.patch.set_facecolor(BG_COLOR)

    for ax, (title, vals, color, style) in zip(axes, datasets):
        ax.set_facecolor(PANEL_COLOR)
        ax.plot(x, vals, style, color=color, linewidth=2.5, markersize=7)
        ax.set_title(title, color=TEXT_COLOR, fontsize=12, pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in years], color=TEXT_COLOR,
                           fontsize=9, rotation=45)
        ax.tick_params(axis="y", labelcolor=TEXT_COLOR)
        ax.tick_params(colors=TEXT_COLOR)
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.15, color=BORDER_COLOR, linestyle="--")
        for spine in ax.spines.values():
            spine.set_color(BORDER_COLOR)

    fig.suptitle("My GitHub Journey", color=TEXT_COLOR, fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    print(f"  Trend chart saved -> {out_path}")


# ---------------------------------------------------------------------------
# SVG cards
# ---------------------------------------------------------------------------

def _svg_octicon(path_d, x, y, fill, size=16):
    return (
        f'<svg x="{x}" y="{y}" width="{size}" height="{size}" '
        f'viewBox="0 0 16 16">'
        f'<path fill-rule="evenodd" d="{path_d}" fill="{fill}"/></svg>'
    )


def _wrap_text(text, max_chars=54):
    """Word-wrap *text* into at most two lines, ellipsising the overflow."""
    words = (text or "").split()
    lines = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > max_chars and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    if len(lines) > 2:
        lines = [lines[0], lines[1][: max_chars - 3].rstrip() + "..."]
    return lines or [""]


def generate_stats_card(repos, commits_by_year, out_path):
    owned = [r for r in repos if not r.get("fork")]
    stats = [
        ("Total Stars Earned",
         sum(r.get("stargazers_count", 0) for r in repos),
         _ICON_STAR, "#f1c40f"),
        ("Total Commits", sum(commits_by_year.values()),
         _ICON_COMMIT, "#3fb950"),
        ("Original Public Repos", len(owned), _ICON_REPO, "#58a6ff"),
        ("Total Forks Received",
         sum(r.get("forks_count", 0) for r in owned),
         _ICON_FORK, MUTED_COLOR),
    ]

    w, h = 495, 195
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
        f'height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" rx="4.5" fill="{BG_COLOR}"/>',
        f'<text x="25" y="35" font-family="{_SVG_FONT}" font-size="18" '
        f'font-weight="bold" fill="{TEXT_COLOR}">'
        f"{USERNAME}&#x27;s GitHub Stats</text>",
    ]
    for i, (label, value, icon, icon_fill) in enumerate(stats):
        y = 68 + i * 32
        parts.append(_svg_octicon(icon, 25, y - 13, icon_fill))
        parts.append(
            f'<text x="50" y="{y}" font-family="{_SVG_FONT}" '
            f'font-size="14" fill="{MUTED_COLOR}">{xml_escape(label)}:</text>'
        )
        parts.append(
            f'<text x="{w - 25}" y="{y}" font-family="{_SVG_FONT}" '
            f'font-size="14" font-weight="bold" fill="{TEXT_COLOR}" '
            f'text-anchor="end">{value:,}</text>'
        )
    parts.append("</svg>")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print(f"  Stats card saved -> {out_path}")


def _footer_item(parts, icon, value, x, y):
    parts.append(_svg_octicon(icon, x, y - 13, MUTED_COLOR))
    parts.append(
        f'<text x="{x + 20}" y="{y}" font-family="{_SVG_FONT}" '
        f'font-size="12" fill="{MUTED_COLOR}">{value}</text>'
    )
    return x + 20 + len(str(value)) * _APPROX_CHAR_WIDTH + 16


def generate_repo_card(repo, out_path):
    name = repo["name"]
    lang = repo.get("language") or ""
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)

    w, h = 400, 120
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
        f'height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" '
        f'rx="4.5" fill="{BG_COLOR}" stroke="{BORDER_COLOR}"/>',
        _svg_octicon(_ICON_REPO, 20, 14, MUTED_COLOR),
        f'<text x="44" y="28" font-family="{_SVG_FONT}" font-size="14" '
        f'font-weight="bold" fill="#58a6ff">{xml_escape(name)}</text>',
    ]
    for j, line in enumerate(_wrap_text(repo.get("description"))):
        parts.append(
            f'<text x="20" y="{50 + j * 16}" font-family="{_SVG_FONT}" '
            f'font-size="12" fill="{MUTED_COLOR}">{xml_escape(line)}</text>'
        )

    fy, fx = h - 16, 20
    if lang:
        color = LANGUAGE_COLORS.get(lang, MUTED_COLOR)
        parts.append(f'<circle cx="{fx + 6}" cy="{fy - 4}" r="6" fill="{color}"/>')
        parts.append(
            f'<text x="{fx + 18}" y="{fy}" font-family="{_SVG_FONT}" '
            f'font-size="12" fill="{MUTED_COLOR}">{xml_escape(lang)}</text>'
        )
        fx += 18 + len(lang) * _APPROX_CHAR_WIDTH + 16
    if stars:
        fx = _footer_item(parts, _ICON_STAR, stars, int(fx), fy)
    if forks:
        _footer_item(parts, _ICON_FORK, forks, int(fx), fy)
    parts.append("</svg>")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))


def top_repos(repos):
    """Most-starred original repos; ties broken by most recently pushed."""
    owned = [r for r in repos if not r.get("fork") and r["name"] != USERNAME]
    ranked = sorted(
        owned,
        key=lambda r: (r.get("stargazers_count", 0), r.get("pushed_at", "")),
        reverse=True,
    )
    return ranked[:PINNED_COUNT]


def remove_stale_pins(keep_names):
    keep = {f"pin-{n}.svg" for n in keep_names}
    for fname in os.listdir(ASSETS_DIR):
        if fname.startswith("pin-") and fname not in keep:
            os.remove(os.path.join(ASSETS_DIR, fname))


def update_readme_pins(repos):
    with open(README_PATH, encoding="utf-8") as fh:
        readme = fh.read()
    if PINNED_START not in readme or PINNED_END not in readme:
        print("  README has no PINNED markers – leaving it unchanged.")
        return
    links = "\n".join(
        f'  <a href="{r["html_url"]}">\n'
        f'    <img src="assets/pin-{r["name"]}.svg" alt="{r["name"]}"/>\n'
        f"  </a>"
        for r in repos
    )
    block = f'{PINNED_START}\n<div align="center">\n{links}\n</div>\n{PINNED_END}'
    pattern = re.compile(
        re.escape(PINNED_START) + r".*?" + re.escape(PINNED_END), re.DOTALL
    )
    with open(README_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(pattern.sub(lambda _: block, readme))
    print("  README pinned section updated")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)

    print("Fetching repos ...")
    repos = get_repos()
    print(f"  Found {len(repos)} repos")

    print("Collecting commit activity ...")
    commits_by_year = get_commits_by_year()

    print("Generating stats card ...")
    generate_stats_card(
        repos, commits_by_year, os.path.join(ASSETS_DIR, "github-stats.svg")
    )

    print("Generating word cloud ...")
    generate_word_cloud(repos, os.path.join(ASSETS_DIR, "word-cloud.png"))

    print("Generating trend chart ...")
    generate_trend_chart(
        repos, commits_by_year, os.path.join(ASSETS_DIR, "trend-chart.png")
    )

    print("Generating repo pin cards ...")
    pinned = top_repos(repos)
    for repo in pinned:
        generate_repo_card(
            repo, os.path.join(ASSETS_DIR, f"pin-{repo['name']}.svg")
        )
    remove_stale_pins([r["name"] for r in pinned])
    update_readme_pins(pinned)
    print(f"  Top repos: {', '.join(r['name'] for r in pinned)}")

    print("Done!")


if __name__ == "__main__":
    main()
