"""
generate_stats_svg.py
─────────────────────
Generate an SVG dashboard for the EL-BID org profile README.
Only uses PUBLIC repo data.

Data sources:
  - GitHub API: public repos, stars, forks, followers
  - c4d-repos-stats CSVs (checked out locally by the workflow):
    PyPI downloads (BigQuery), GitHub traffic (views/clones)
"""
import csv
import os
import requests
from datetime import datetime, timezone
from pathlib import Path

ORG = "EL-BID"
TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Local path to the checked-out c4d-repos-stats data
C4D_DATA = Path("c4d-data/data/expanded")

OUTPUT_PATH = "profile/stats.svg"


# ──────────────────────────────────────────────
# DATA FETCHING
# ──────────────────────────────────────────────

def fetch_all_public_repos():
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
    url = f"https://api.github.com/orgs/{ORG}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("followers", 0)


def read_local_csv(filename):
    """Read a CSV from the locally checked-out c4d-repos-stats data."""
    path = C4D_DATA / filename
    if not path.exists():
        print(f"  [WARN] File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def compute_pypi_totals(rows):
    by_pkg = {}
    total = 0
    for r in rows:
        pkg = r.get("package", "").strip()
        dl = int(r.get("downloads", "0").strip())
        by_pkg[pkg] = by_pkg.get(pkg, 0) + dl
        total += dl
    sorted_pkgs = sorted(by_pkg.items(), key=lambda x: -x[1])
    return total, sorted_pkgs


def compute_traffic_totals(rows):
    clones = 0
    views = 0
    for r in rows:
        t = r.get("type", "").strip()
        c = int(r.get("count", "0").strip())
        if t == "clones":
            clones += c
        elif t == "views":
            views += c
    return clones, views


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def format_number(n):
    return f"{n:,}"


def format_compact(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def compute_language_stats(repos):
    lang_count = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_count[lang] = lang_count.get(lang, 0) + 1
    total = sum(lang_count.values()) or 1
    sorted_langs = sorted(lang_count.items(), key=lambda x: -x[1])
    top = sorted_langs[:5]
    others = sum(c for _, c in sorted_langs[5:])
    result = [(name, count, round(100 * count / total)) for name, count in top]
    if others > 0:
        result.append(("Otros", others, round(100 * others / total)))
    return result


LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#198CE7",
    "R": "#198CE7", "HTML": "#e34c26", "Jupyter Notebook": "#DA5B0B",
    "Java": "#b07219", "C++": "#f34b7d", "Go": "#00ADD8",
    "Shell": "#89e051", "CSS": "#563D7C", "Otros": "#8899AA",
}


def get_top_repos_by_stars(repos, n=5):
    return sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:n]


def truncate_name(name, max_len=15):
    return name if len(name) <= max_len else name[:max_len - 2] + ".."


# ──────────────────────────────────────────────
# SVG GENERATION
# ──────────────────────────────────────────────

def generate_svg(total_repos, total_stars, total_forks, followers,
                 total_views, total_clones, pypi_total, pypi_packages,
                 top_repos, languages, updated_at):

    W = 680
    NAVY = "#003876"
    BLUE = "#0077C8"
    TEAL = "#00A19A"
    AMBER = "#D4960F"
    GREEN = "#1B8A3A"
    CORAL = "#E85D3A"
    TEXT = "#1A2B3C"
    MUTED = "#5A6E80"
    LIGHT = "#EDF5FB"
    BG = "#FAFCFD"
    BORDER = "#D8E4ED"
    WHITE = "#FFFFFF"

    max_stars = top_repos[0]["stargazers_count"] if top_repos else 1

    y = 0
    svg_parts = []

    def add(s):
        svg_parts.append(s)

    # ── Header ──
    add(f'<rect x="0" y="{y}" width="{W}" height="46" fill="{WHITE}"/>')
    add(f'<line x1="0" y1="46" x2="{W}" y2="46" stroke="{BLUE}" stroke-width="2"/>')
    add(f'<text x="20" y="29" font-family="system-ui,sans-serif" font-size="14" font-weight="600" fill="{NAVY}" letter-spacing="0.2">github.com/EL-BID en numeros</text>')
    add(f'<text x="{W - 20}" y="29" font-family="system-ui,sans-serif" font-size="10" fill="{MUTED}" text-anchor="end">{updated_at}</text>')
    y = 48

    # ── Scope ──
    add(f'<rect x="0" y="{y}" width="{W}" height="24" fill="{LIGHT}"/>')
    add(f'<circle cx="16" cy="{y + 12}" r="3" fill="{GREEN}"/>')
    add(f'<text x="26" y="{y + 16}" font-family="system-ui,sans-serif" font-size="10" fill="{MUTED}">Solo repositorios publicos · Datos historicos acumulados</text>')
    y += 24

    # ── KPI row 1: GitHub metrics ──
    add(f'<rect x="0" y="{y}" width="{W}" height="58" fill="{BG}"/>')
    add(f'<text x="{W // 2}" y="{y + 12}" font-family="system-ui,sans-serif" font-size="8" fill="{MUTED}" text-anchor="middle" letter-spacing="0.8" font-weight="500">GITHUB</text>')

    kpis_gh = [
        (format_number(total_repos), "Repos", BLUE),
        (format_number(total_stars), "Estrellas", AMBER),
        (format_number(total_forks), "Forks", TEAL),
        (format_compact(total_views), "Visitas", GREEN),
        (format_compact(total_clones), "Clones", NAVY),
    ]
    card_w = W // len(kpis_gh)
    for i, (val, label, color) in enumerate(kpis_gh):
        cx = i * card_w + card_w // 2
        if i > 0:
            add(f'<line x1="{i * card_w}" y1="{y + 16}" x2="{i * card_w}" y2="{y + 52}" stroke="{BORDER}" stroke-width="0.5"/>')
        add(f'<text x="{cx}" y="{y + 34}" font-family="system-ui,sans-serif" font-size="20" font-weight="500" fill="{color}" text-anchor="middle">{val}</text>')
        add(f'<text x="{cx}" y="{y + 48}" font-family="system-ui,sans-serif" font-size="8.5" fill="{MUTED}" text-anchor="middle" letter-spacing="0.4" font-weight="500">{label.upper()}</text>')
    y += 58

    # ── KPI row 2: PyPI total ──
    add(f'<rect x="0" y="{y}" width="{W}" height="50" fill="{WHITE}"/>')
    add(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{BORDER}" stroke-width="0.5"/>')
    add(f'<text x="{W // 2}" y="{y + 12}" font-family="system-ui,sans-serif" font-size="8" fill="{MUTED}" text-anchor="middle" letter-spacing="0.8" font-weight="500">PYPI · DESCARGAS HISTORICAS (PIP INSTALL)</text>')
    add(f'<text x="{W // 2}" y="{y + 34}" font-family="system-ui,sans-serif" font-size="22" font-weight="500" fill="{CORAL}" text-anchor="middle">{format_number(pypi_total)}</text>')
    add(f'<text x="{W // 2}" y="{y + 46}" font-family="system-ui,sans-serif" font-size="8.5" fill="{MUTED}" text-anchor="middle">descargas totales desde 2020</text>')
    y += 50

    add(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{BORDER}" stroke-width="0.5"/>')
    y += 2

    # ── Top repos ──
    add(f'<text x="20" y="{y + 16}" font-family="system-ui,sans-serif" font-size="9" fill="{MUTED}" letter-spacing="0.5" font-weight="500">TOP 5 REPOS PUBLICOS POR ESTRELLAS</text>')
    y += 26
    bar_left = 126
    bar_right = W - 56
    bar_w = bar_right - bar_left
    for repo in top_repos:
        name = truncate_name(repo["name"])
        stars = repo["stargazers_count"]
        pct = max(4, round(100 * stars / max_stars))
        fill_w = max(4, round(bar_w * pct / 100))
        opacity = max(0.4, 1.0 - (1 - pct / 100) * 0.6)
        add(f'<text x="{bar_left - 8}" y="{y + 11}" font-family="system-ui,sans-serif" font-size="11" fill="{TEXT}" text-anchor="end">{name}</text>')
        add(f'<rect x="{bar_left}" y="{y}" width="{bar_w}" height="16" rx="3" fill="{LIGHT}"/>')
        add(f'<rect x="{bar_left}" y="{y}" width="{fill_w}" height="16" rx="3" fill="{BLUE}" opacity="{opacity:.2f}"/>')
        add(f'<text x="{W - 20}" y="{y + 11}" font-family="system-ui,sans-serif" font-size="10" fill="{MUTED}" text-anchor="end" font-weight="500">{stars}</text>')
        y += 22
    y += 2

    # ── Languages ──
    add(f'<line x1="20" y1="{y}" x2="{W - 20}" y2="{y}" stroke="{BORDER}" stroke-width="0.5"/>')
    y += 10
    add(f'<text x="20" y="{y + 12}" font-family="system-ui,sans-serif" font-size="9" fill="{MUTED}" letter-spacing="0.5" font-weight="500">LENGUAJES EN REPOS PUBLICOS</text>')
    y += 20
    bar_x = 20
    bar_total_w = W - 40
    for i, (name, count, pct) in enumerate(languages):
        color = LANG_COLORS.get(name, "#8899AA")
        seg_w = max(2, round(bar_total_w * pct / 100))
        add(f'<rect x="{bar_x}" y="{y}" width="{seg_w}" height="7" fill="{color}"/>')
        bar_x += seg_w
    y += 13
    lx = 20
    for name, count, pct in languages:
        color = LANG_COLORS.get(name, "#8899AA")
        label = f"{name} {pct}%"
        add(f'<rect x="{lx}" y="{y}" width="7" height="7" rx="1.5" fill="{color}"/>')
        add(f'<text x="{lx + 11}" y="{y + 6}" font-family="system-ui,sans-serif" font-size="10" fill="{MUTED}">{label}</text>')
        lx += len(label) * 6 + 22
        if lx > W - 60:
            lx = 20
            y += 16
    y += 16

    # ── PyPI packages ──
    add(f'<line x1="20" y1="{y}" x2="{W - 20}" y2="{y}" stroke="{BORDER}" stroke-width="0.5"/>')
    y += 10
    add(f'<text x="20" y="{y + 12}" font-family="system-ui,sans-serif" font-size="9" fill="{MUTED}" letter-spacing="0.5" font-weight="500">DESCARGAS POR LIBRERIA (TOTAL HISTORICO)</text>')
    y += 20
    col_w = (W - 40 - 12) // 3
    col = 0
    row_y = y
    for pkg_name, downloads in pypi_packages:
        cx = 20 + col * (col_w + 6)
        add(f'<rect x="{cx}" y="{row_y}" width="{col_w}" height="48" rx="6" fill="{LIGHT}"/>')
        add(f'<text x="{cx + col_w // 2}" y="{row_y + 16}" font-family="monospace" font-size="10" font-weight="500" fill="{NAVY}" text-anchor="middle">{pkg_name}</text>')
        add(f'<text x="{cx + col_w // 2}" y="{row_y + 32}" font-family="system-ui,sans-serif" font-size="14" font-weight="500" fill="{TEXT}" text-anchor="middle">{format_compact(downloads)}</text>')
        add(f'<text x="{cx + col_w // 2}" y="{row_y + 43}" font-family="system-ui,sans-serif" font-size="7.5" fill="{MUTED}" text-anchor="middle" letter-spacing="0.3">DESCARGAS</text>')
        col += 1
        if col >= 3:
            col = 0
            row_y += 54
    if col > 0:
        row_y += 54
    y = row_y + 4

    # ── Footer ──
    add(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{BORDER}" stroke-width="0.5"/>')
    y += 5
    add(f'<text x="{W // 2}" y="{y + 11}" font-family="system-ui,sans-serif" font-size="9.5" fill="{MUTED}" text-anchor="middle" opacity="0.55">Datos de repositorios publicos · Generado automaticamente via GitHub Actions</text>')
    y += 22

    total_h = y + 4
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="680" viewBox="0 0 {W} {total_h}" role="img">
<title>github.com/EL-BID en numeros</title>
<desc>Dashboard: {total_repos} repos, {total_stars} estrellas, {format_number(pypi_total)} descargas PyPI</desc>
<rect width="{W}" height="{total_h}" rx="8" fill="{WHITE}" stroke="{BORDER}" stroke-width="0.5"/>
{''.join(svg_parts)}
</svg>'''
    return svg


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    print("Fetching public repos from GitHub API...")
    repos = fetch_all_public_repos()
    total_repos = len(repos)
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)
    print(f"  {total_repos} public repos, {total_stars} stars, {total_forks} forks")

    print("Fetching org followers...")
    followers = fetch_org_followers()
    print(f"  {followers} followers")

    top_repos = get_top_repos_by_stars(repos, n=5)
    print(f"  Top repo: {top_repos[0]['name']} ({top_repos[0]['stargazers_count']} stars)")

    languages = compute_language_stats(repos)
    print(f"  Languages: {', '.join(f'{n} ({p}%)' for n, _, p in languages)}")

    print(f"Reading PyPI data from {C4D_DATA}...")
    pypi_rows = read_local_csv("pypi_downloads_by_country.csv")
    pypi_total, pypi_packages = compute_pypi_totals(pypi_rows)
    print(f"  PyPI total: {pypi_total:,} downloads across {len(pypi_packages)} packages")
    for pkg, dl in pypi_packages:
        print(f"    {pkg}: {dl:,}")

    print(f"Reading GitHub traffic from {C4D_DATA}...")
    traffic_rows = read_local_csv("daily_traffic.csv")
    total_clones, total_views = compute_traffic_totals(traffic_rows)
    print(f"  Views: {total_views:,}, Clones: {total_clones:,}")

    updated_at = datetime.now(timezone.utc).strftime("Actualizado %d %b %Y")

    print("Generating SVG...")
    svg = generate_svg(
        total_repos=total_repos,
        total_stars=total_stars,
        total_forks=total_forks,
        followers=followers,
        total_views=total_views,
        total_clones=total_clones,
        pypi_total=pypi_total,
        pypi_packages=pypi_packages,
        top_repos=top_repos,
        languages=languages,
        updated_at=updated_at,
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"SVG written to {OUTPUT_PATH} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
