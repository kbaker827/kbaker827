#!/usr/bin/env python3
"""
Generate home-assistant.md — every original (non-fork) repo of mine that is
related to Home Assistant, with type, description, latest release and stars.
"""

import os
import sys
from datetime import datetime, timezone

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
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "home-assistant.md")

HA_TOPICS = frozenset(
    {
        "home-assistant",
        "homeassistant",
        "homeassistant-custom-component",
        "homeassistant-integration",
        "home-assistant-integration",
        "hacs",
        "lovelace",
        "lovelace-custom-card",
    }
)
HA_NAME_PREFIXES = ("ha-", "ha_", "homeassistant", "home-assistant")
HA_TEXT_MARKERS = ("home assistant", "homeassistant")

# Type is decided by the first matching rule, checked against name,
# description and topics.
TYPE_RULES = [
    ("🧩 Integration", ("integration", "custom component", "custom-component")),
    ("📊 Dashboard", ("dashboard", "lovelace", "card")),
    ("🎨 Theme", ("theme",)),
    ("🕶️ Companion App", ("glasses", "rokid", "ray-ban", "ios", "android")),
]
DEFAULT_TYPE = "🏠 Project"


def get_all_repos():
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


def _search_text(repo):
    return " ".join(
        [
            repo["name"].lower(),
            (repo.get("description") or "").lower(),
            " ".join(repo.get("topics", [])),
        ]
    )


def is_ha_repo(repo):
    if repo.get("fork"):
        return False
    if set(repo.get("topics", [])) & HA_TOPICS:
        return True
    lower = repo["name"].lower()
    if lower.startswith(HA_NAME_PREFIXES) or lower.endswith("-ha"):
        return True
    desc = (repo.get("description") or "").lower()
    return any(marker in desc for marker in HA_TEXT_MARKERS)


def classify(repo):
    text = _search_text(repo)
    for label, keywords in TYPE_RULES:
        if any(k in text for k in keywords):
            return label
    return DEFAULT_TYPE


def latest_release(repo):
    """Return 'tag (YYYY-MM-DD)' for the latest release, or '—'."""
    url = f"https://api.github.com/repos/{USERNAME}/{repo['name']}/releases/latest"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return "—"
    resp.raise_for_status()
    data = resp.json()
    tag = data.get("tag_name", "")
    date = (data.get("published_at") or "")[:10]
    link = data.get("html_url", repo["html_url"])
    return f"[{tag}]({link}) ({date})" if date else f"[{tag}]({link})"


def _cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ")


def render(rows):
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# 🏠 Home Assistant Projects",
        "",
        "Custom integrations, dashboards and smart-glasses companions I've "
        "built around Home Assistant. Generated automatically from my "
        "repositories — refreshed weekly.",
        "",
        "| Project | Type | Description | Latest release | ⭐ |",
        "|---|---|---|---|---|",
    ]
    for repo, kind, release in rows:
        lines.append(
            f"| [{_cell(repo['name'])}]({repo['html_url']}) | {kind} | "
            f"{_cell(repo.get('description'))} | {release} | "
            f"{repo.get('stargazers_count', 0)} |"
        )
    if not rows:
        lines.append("| _No Home Assistant projects found_ | | | | |")
    lines += ["", f"<sub>Last updated {now} · [Back to profile](README.md)</sub>", ""]
    return "\n".join(lines)


def main():
    print("Fetching repos ...")
    repos = [r for r in get_all_repos() if is_ha_repo(r)]
    repos.sort(key=lambda r: (-r.get("stargazers_count", 0), r["name"].lower()))
    print(f"  Found {len(repos)} Home Assistant repos")

    rows = [(r, classify(r), latest_release(r)) for r in repos]
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(rows))
    print(f"  Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
