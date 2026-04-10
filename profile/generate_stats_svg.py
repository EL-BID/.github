"""
Generate an SVG dashboard for the EL-BID org profile README.
Only uses PUBLIC repo data from the GitHub API.
"""
import json
import os
import requests
from datetime import datetime, timezone

ORG = "EL-BID"
TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}
PYPI_PACKAGES = ["viasegura", "pavimentados", "urbantrips", "urbanpy", "idbsocialdatapy"]
OUTPUT_PATH = "profile/stats.svg"


def fetch_all_public_repos():
    """Fetch ALL public repos from the org (paginated)."""
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{ORG}/repos?type=public&per_page=100&page={page}"
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def fetch_org_followers():
    """Fetch the org's follower count."""
    url = f"https://api.github.com/orgs/{ORG}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("followers", 0)


def fetch_pypi_downloads(package):
    """Fetch monthly download count from pypistats.org API."""
    try:
        url = f"https://pypistats.org/api/packages/{package}/recent"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("last_month", 0)
    except Exception:
        return 0


def format_number(n):
    """Format number with comma separators."""
    return f"{n:,}"


def format_compact(n):
    """Format number compactly: 1200 -> 1.2K"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def compute_language_stats(repos):
    """Count repos per primary language (public repos only)."""
    lang_count = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_count[lang] = lang_count.get(lang, 0) + 1
    total = sum(lang_count.values()) or 1
    # Sort by count descending
    sorted_langs = sorted(lang_count.items(), key=lambda x: -x[1])
    # Top 5 + "Otros"
    top = sorted_langs[:5]
    others = sum(c for _, c in sorted_langs[5:])
    result = [(name, count, round(100 * count / total)) for name, count in top]
    if others > 0:
        result.append(("Otros", others, round(100 * others / total)))
    return result


# GitHub language colors
LANG_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#198CE7",
    "R": "#198CE7",
    "HTML": "#e34c26",
    "Jupyter Notebook": "#DA5B0B",
    "Java": "#b07219",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Go": "#00ADD8",
    "Shell": "#89e051",
    "CSS": "#563D7C",
    "PHP": "#4F5D95",
    "Otros": "#8899AA",
}


def get_top_repos_by_stars(repos, n=5):
    """Get top N public repos by stargazer count."""
    sorted_repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)
    return sorted_repos[:n]


def truncate_name(name, max_len=15):
    """Truncate repo name for display."""
    if len(name) <= max_len:
        return name
    return name[: max_len - 2] + ".."


def generate_svg(total_repos, total_stars, total_forks, followers,
                 top_repos, languages, pypi_data, updated_at):
    """Generate the full SVG dashboard string."""
    W = 680
    # Colors (light mode — GitHub README doesn't support dark mode switching)
    NAVY = "#003876"
    BLUE = "#0077C8"
    TEAL = "#00A19A"
    AMBER = "#D4960F"
    GREEN = "#1B8A3A"
    TEXT = "#1A2B3C"
    MUTED = "#5A6E80"
    LIGHT = "#EDF5FB"
    BG = "#FAFCFD"
    BORDER = "#D8E4ED"
    WHITE = "#FFFFFF"

    # --- Build bar chart data ---
    max_stars = top_repos[0]["stargazers_count"] if top_repos else 1

    def bar_pct(count):
        return max(4, round(100 * count / max_stars))

    # --- Compute layout ---
    y = 0

    svg_parts = []

    def add(s):
        svg_parts.append(s)

    # --- Header ---
    add(f'<rect x="0" y="{y}" width="{W}" height="42" fill="{WHITE}"/>')
    add(f'<line x1="0" y1="42" x2="{W}" y2="42" stroke="{BLUE}" stroke-width="2"/>')
    add(f'<text x="20" y="26" font-family="system-ui,sans-serif" font-size="13" font-weight="500" fill="{NAVY}" letter-spacing="0.3">Codigo para el Desarrollo · Open source</text>')
    add(f'<text x="{W - 20}" y="26" font-family="system-ui,sans-serif" font-size="10" fill="{MUTED}" text-anchor="end">{updated_at}</text>')
    y = 44

    # --- Scope indicator ---
    add(f'<rect x="0" y="{y}" width="{W}" height="26" fill="{LIGHT}"/>')
    add(f'<circle cx="16" cy="{y + 13}" r="3" fill="{GREEN}"/>')
    add(f'<text x="26" y="{y + 17}" font-family="system-ui,sans-serif" font-size="10.5" fill="{MUTED}">Solo repositorios publicos de github.com/EL-BID</text>')
    y += 26

    # --- Metric cards ---
    card_w = W // 4
    metrics = [
        (format_number(total_repos), "Repos publicos", BLUE),
        (format_number(total_stars), "Estrellas", AMBER),
        (format_number(total_forks), "Forks", TEAL),
        (format_number(followers), "Seguidores", GREEN),
    ]
    add(f'<rect x="0" y="{y}" width="{W}" height="60" fill="{BG}"/>')
    for i, (val, label, color) in enumerate(metrics):
        cx = i * card_w + card_w // 2
        if i > 0:
            add(f'<line x1="{i * card_w}" y1="{y + 8}" x2="{i * card_w}" y2="{y + 52}" stroke="{BORDER}" stroke-width="0.5"/>')
        add(f'<text x="{cx}" y="{y + 28}" font-family="system-ui,sans-serif" font-size="22" font-weight="500" fill="{color}" text-anchor="middle">{val}</text>')
        add(f'<text x="{cx}" y="{y + 44}" font-family="system-ui,sans-serif" font-size="9" fill="{MUTED}" text-anchor="middle" letter-spacing="0.5" font-weight="500">{label.upper()}</text>')
    add(f'<line x1="0" y1="{y + 60}" x2="{W}" y2="{y + 60}" stroke="{BORDER}" stroke-width="0.5"/>')
    y += 62

    # --- Top repos bar chart ---
    add(f'<text x="20" y="{y + 18}" font-family="system-ui,sans-serif" font-size="9.5" fill="{MUTED}" letter-spacing="0.6" font-weight="500">TOP 5 REPOS PUBLICOS POR ESTRELLAS</text>')
    y += 28
    bar_left = 126
    bar_right = W - 56
    bar_w = bar_right - bar_left
    for repo in top_repos:
        name = truncate_name(repo["name"])
        stars = repo["stargazers_count"]
        pct = bar_pct(stars)
        fill_w = max(4, round(bar_w * pct / 100))
        opacity = max(0.4, 1.0 - (1 - pct / 100) * 0.6)
        add(f'<text x="{bar_left - 8}" y="{y + 12}" font-family="system-ui,sans-serif" font-size="11" fill="{TEXT}" text-anchor="end">{name}</text>')
        add(f'<rect x="{bar_left}" y="{y + 1}" width="{bar_w}" height="16" rx="3" fill="{LIGHT}"/>')
        add(f'<rect x="{bar_left}" y="{y + 1}" width="{fill_w}" height="16" rx="3" fill="{BLUE}" opacity="{opacity:.2f}"/>')
        add(f'<text x="{W - 20}" y="{y + 12}" font-family="system-ui,sans-serif" font-size="10" fill="{MUTED}" text-anchor="end" font-weight="500">{stars}</text>')
        y += 22
    y += 4

    # --- Language bar ---
    add(f'<line x1="20" y1="{y}" x2="{W - 20}" y2="{y}" stroke="{BORDER}" stroke-width="0.5"/>')
    y += 12
    add(f'<text x="20" y="{y + 12}" font-family="system-ui,sans-serif" font-size="9.5" fill="{MUTED}" letter-spacing="0.6" font-weight="500">LENGUAJES EN REPOS PUBLICOS</text>')
    y += 22
    # Stacked bar
    bar_x = 20
    bar_total_w = W - 40
    for name, count, pct in languages:
        color = LANG_COLORS.get(name, "#8899AA")
        seg_w = max(2, round(bar_total_w * pct / 100))
        add(f'<rect x="{bar_x}" y="{y}" width="{seg_w}" height="7" fill="{color}" rx="0"/>')
        # Round first and last
        if bar_x == 20:
            add(f'<rect x="{bar_x}" y="{y}" width="{seg_w}" height="7" fill="{color}" rx="3.5"/>')
            add(f'<rect x="{bar_x + 4}" y="{y}" width="{seg_w - 4}" height="7" fill="{color}"/>')
        bar_x += seg_w
    # Last segment rounding
    y += 14
    # Legend
    lx = 20
    for name, count, pct in languages:
        color = LANG_COLORS.get(name, "#8899AA")
        add(f'<rect x="{lx}" y="{y}" width="7" height="7" rx="1.5" fill="{color}"/>')
        label = f"{name} {pct}%"
        add(f'<text x="{lx + 11}" y="{y + 6}" font-family="system-ui,sans-serif" font-size="10" fill="{MUTED}">{label}</text>')
        lx += len(label) * 6 + 22
        if lx > W - 60:
            lx = 20
            y += 16
    y += 18

    # --- PyPI section ---
    add(f'<line x1="20" y1="{y}" x2="{W - 20}" y2="{y}" stroke="{BORDER}" stroke-width="0.5"/>')
    y += 12
    add(f'<text x="20" y="{y + 12}" font-family="system-ui,sans-serif" font-size="9.5" fill="{MUTED}" letter-spacing="0.6" font-weight="500">LIBRERIAS PYTHON EN PYPI · DESCARGAS MENSUALES</text>')
    y += 22
    # Grid: 3 columns
    col_w = (W - 40 - 12) // 3
    col = 0
    row_y = y
    for pkg_name, downloads in pypi_data:
        cx = 20 + col * (col_w + 6)
        add(f'<rect x="{cx}" y="{row_y}" width="{col_w}" height="50" rx="6" fill="{LIGHT}"/>')
        add(f'<text x="{cx + col_w // 2}" y="{row_y + 17}" font-family="monospace" font-size="10" font-weight="500" fill="{NAVY}" text-anchor="middle">{pkg_name}</text>')
        add(f'<text x="{cx + col_w // 2}" y="{row_y + 33}" font-family="system-ui,sans-serif" font-size="14" font-weight="500" fill="{TEXT}" text-anchor="middle">{format_compact(downloads)}</text>')
        add(f'<text x="{cx + col_w // 2}" y="{row_y + 44}" font-family="system-ui,sans-serif" font-size="8" fill="{MUTED}" text-anchor="middle" letter-spacing="0.3">DESCARGAS/MES</text>')
        col += 1
        if col >= 3:
            col = 0
            row_y += 56
    if col > 0:
        row_y += 56
    y = row_y + 4

    # --- Footer ---
    add(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{BORDER}" stroke-width="0.5"/>')
    y += 6
    add(f'<text x="{W // 2}" y="{y + 12}" font-family="system-ui,sans-serif" font-size="10" fill="{MUTED}" text-anchor="middle" opacity="0.6">Datos de repositorios publicos · Generado automaticamente via GitHub Actions</text>')
    y += 24

    total_h = y + 4
    # Assemble SVG
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="680" viewBox="0 0 {W} {total_h}" role="img">
<title>Dashboard de estadisticas de repositorios publicos de EL-BID</title>
<desc>Muestra {total_repos} repositorios publicos, {total_stars} estrellas, {total_forks} forks y descargas PyPI</desc>
<rect width="{W}" height="{total_h}" rx="8" fill="{WHITE}" stroke="{BORDER}" stroke-width="0.5"/>
{''.join(svg_parts)}
</svg>'''
    return svg


def main():
    print("Fetching public repos...")
    repos = fetch_all_public_repos()
    print(f"  Found {len(repos)} public repos")

    total_repos = len(repos)
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    print("Fetching org followers...")
    followers = fetch_org_followers()
    print(f"  {followers} followers")

    top_repos = get_top_repos_by_stars(repos, n=5)
    print(f"  Top repo: {top_repos[0]['name']} ({top_repos[0]['stargazers_count']} stars)")

    languages = compute_language_stats(repos)
    print(f"  Languages: {', '.join(f'{n} ({p}%)' for n, _, p in languages)}")

    print("Fetching PyPI downloads...")
    pypi_data = []
    for pkg in PYPI_PACKAGES:
        dl = fetch_pypi_downloads(pkg)
        pypi_data.append((pkg, dl))
        print(f"  {pkg}: {dl}")
    # Sort by downloads descending
    pypi_data.sort(key=lambda x: -x[1])

    updated_at = datetime.now(timezone.utc).strftime("Actualizado %d %b %Y")

    print("Generating SVG...")
    svg = generate_svg(
        total_repos=total_repos,
        total_stars=total_stars,
        total_forks=total_forks,
        followers=followers,
        top_repos=top_repos,
        languages=languages,
        pypi_data=pypi_data,
        updated_at=updated_at,
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"SVG written to {OUTPUT_PATH} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
