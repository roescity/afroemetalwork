#!/usr/bin/env python3
"""Static-site generator for AFRoeMetalwork.

Writes the site's HTML from site.toml and the photographs already stored
in docs/images/. Those images ARE the site's copy of the artwork: they
are committed to the repo, so this runs on any machine with Python 3.11+
and needs neither the original photo folders nor macOS.

To add or replace photographs, use import_photos.py, which resizes
originals into docs/images/. Then run this.

Usage:
    python3 build.py
"""

import hashlib
import html
import json
import re
import shutil
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs"
ASSETS = ROOT / "assets"
IMAGES = OUT / "images"
MANIFEST = IMAGES / ".manifest.json"

# Every file this run produces, as docs-relative posix paths. Anything
# else found in docs/ afterwards is left over from a deleted work or
# photo and gets pruned, so the site always matches site.toml.
KEPT: set[str] = set()

# ...except these, which are not generated but must survive a prune.
# CNAME is written by GitHub when a custom domain is configured.
PRESERVE = {".nojekyll", "CNAME", "images/.manifest.json"}


# --------------------------------------------------------------- helpers

def esc(s: str) -> str:
    return html.escape(s, quote=True)


def slugify(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.lower())
    return s.strip("-") or "img"


def asset_version(name: str) -> str:
    """Short content hash, appended to asset URLs.

    Without it a browser keeps serving the stylesheet it cached before the
    last deploy, so a visitor sees new pages with old styling.
    """
    digest = hashlib.sha256((ASSETS / name).read_bytes()).hexdigest()
    return digest[:8]


def ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 11 -> '11th'."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def natural_key(name: str):
    """Sort so 2 comes before 10."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


class Photos:
    """The photographs stored under docs/images/, with their dimensions.

    Each artwork folder holds a '<base>-large.jpg' and '<base>-thumb.jpg'
    for every photograph, where base is 'primary' (the cover and lead
    image) or a number. Dimensions come from the committed manifest, so
    no image library is needed to build the site.
    """

    def __init__(self):
        try:
            self.dims = json.loads(MANIFEST.read_text())
        except (OSError, json.JSONDecodeError):
            sys.exit(f"ERROR: cannot read {MANIFEST}. Run import_photos.py.")

    def size(self, rel: str):
        if rel not in self.dims:
            sys.exit(f"ERROR: {rel} is missing from {MANIFEST.name}. "
                     "Run import_photos.py to regenerate it.")
        w, h = self.dims[rel]
        return rel, w, h

    def _bases(self, folder: Path):
        bases = {f.name[: -len("-large.jpg")] for f in folder.glob("*-large.jpg")}
        ordered = sorted(bases - {"primary"}, key=natural_key)
        return (["primary"] if "primary" in bases else []) + ordered

    def series(self, rel_dir: str, what: str):
        """[(large, thumb)] for one artwork or process folder, in order."""
        folder = OUT / rel_dir
        if not folder.is_dir():
            sys.exit(f"ERROR: no photographs for {what}: {folder} does not exist.\n"
                     "       Add them with import_photos.py.")
        bases = self._bases(folder)
        if not bases:
            sys.exit(f"ERROR: no photographs for {what} in {folder}.")
        out = []
        for b in bases:
            large = self.size(f"{rel_dir}/{b}-large.jpg")
            thumb_rel = f"{rel_dir}/{b}-thumb.jpg"
            thumb = self.size(thumb_rel) if (OUT / thumb_rel).exists() else large
            out.append((large, thumb))
        return out


def paragraphs(text: str, cls: str = "") -> str:
    """Blank-line separated text -> <p> blocks."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    attr = f' class="{cls}"' if cls else ""
    return "\n".join(f"<p{attr}>{esc(p)}</p>" for p in paras)


# --------------------------------------------------------------- templates

def page(*, rel: str, title: str, description: str, body: str,
         site: dict, active: str = "", og_image: str = "",
         versions: dict | None = None) -> str:
    versions = versions or {}
    home = rel if rel else "./"
    og = (f'\n  <meta property="og:image" content="{esc(og_image)}">'
          if og_image else "")
    nav_work = ' class="active"' if active == "work" else ""
    nav_about = ' class="active"' if active == "about" else ""
    year = date.today().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta property="og:title" content="{esc(title)}">{og}
  <link rel="icon" href="{rel}favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{rel}assets/style.css?v={versions.get('style.css', '')}">
</head>
<body>
<header class="site-head">
  <a class="brand" href="{home}">
    <span class="brand-name">{esc(site['title'])}</span>
    <span class="brand-sub">{esc(site['subtitle'])}</span>
  </a>
  <nav class="site-nav">
    <a href="{home}"{nav_work}>Work</a>
    <a href="{rel}about/"{nav_about}>About</a>
  </nav>
</header>
{body}
<footer class="site-foot">
  <p>{esc(site['title'])} &nbsp;·&nbsp; <a href="mailto:{esc(site['email'])}">{esc(site['email'])}</a></p>
  <p class="fineprint">© {year} {esc(site['title'])}. All works copyright the artist.</p>
</footer>
<script src="{rel}assets/lightbox.js?v={versions.get('lightbox.js', '')}" defer></script>
</body>
</html>
"""


def tombstone(p: dict) -> str:
    """The museum-label line: materials · dimensions · year."""
    bits = [p.get(k, "") for k in ("materials", "dimensions", "year")]
    bits = [esc(b) for b in bits if b]
    return " &nbsp;·&nbsp; ".join(bits)


def card(p: dict, thumb, href: str) -> str:
    rel_img, w, h = thumb
    meta = (f'\n    <span class="card-meta">{esc(p["materials"])}</span>'
            if p.get("materials") else "")
    return f"""<a class="card" href="{href}">
  <img src="{rel_img}" width="{w}" height="{h}" alt="{esc(p['title'])}" loading="lazy">
  <span class="card-label">
    <span class="card-title">{esc(p['title'])}</span>{meta}
  </span>
</a>"""


def figures(p: dict, rel: str, group: str, alt: str, lead_first: bool):
    """The lead photograph and the strip of further views for one work.

    `group` scopes the lightbox: on a series page each work keeps its own
    group, so the arrows cycle within that work rather than the whole page.
    """
    lead_src, lw, lh = p["_large"][0]
    priority = ' fetchpriority="high"' if lead_first else ' loading="lazy"'
    lead = (f'<figure class="lead">'
            f'<a href="{rel}{lead_src}" data-lightbox="{group}">'
            f'<img src="{rel}{lead_src}" width="{lw}" height="{lh}" '
            f'alt="{esc(alt)}"{priority}></a></figure>')

    views = ""
    if len(p["_large"]) > 1:
        tiles = "\n".join(
            f'    <a class="view" href="{rel}{full}" data-lightbox="{group}">'
            f'<img src="{rel}{tn}" width="{tw}" height="{th}" '
            f'alt="{esc(alt)} — view {i + 2}" loading="lazy"></a>'
            for i, ((full, _, _), (tn, tw, th))
            in enumerate(zip(p["_large"][1:], p["_thumbs"][1:])))
        views = f"""<section class="views">
  <h2 class="views-label">More views</h2>
  <div class="views-strip">
{tiles}
  </div>
</section>"""
    return lead, views


# --------------------------------------------------------------- build

def main():
    with open(ROOT / "site.toml", "rb") as f:
        data = tomllib.load(f)
    site = data["site"]
    hero = data["hero"]
    about = data["about"]
    projects = data["projects"]

    OUT.mkdir(exist_ok=True)
    (OUT / ".nojekyll").touch()
    photos = Photos()

    # ---- assets ------------------------------------------------------
    out_assets = OUT / "assets"
    out_assets.mkdir(exist_ok=True)
    for f in ASSETS.iterdir():
        if f.is_file():
            shutil.copy2(f, out_assets / f.name)
            KEPT.add(f"assets/{f.name}")
    write_page(OUT / "favicon.svg", FAVICON)
    versions = {f.name: asset_version(f.name)
                for f in ASSETS.iterdir() if f.is_file()}

    # ---- gather the stored photographs per project -------------------
    for p in projects:
        series = photos.series(f"images/{p['slug']}", p["title"])
        p["_large"] = [large for large, _ in series]
        p["_thumbs"] = [thumb for _, thumb in series]
        p["_thumb"] = p["_thumbs"][0]

        if p.get("process_folder"):
            proc = photos.series(f"images/{p['slug']}/process",
                                 f"{p['title']} process")
            p["_process"] = [large for large, _ in proc]
            p["_process_thumbs"] = [thumb for _, thumb in proc]

    hero_img = photos.size(hero["image"])
    about_img = photos.size(site["about_photo"])

    # ---- home page ---------------------------------------------------
    # The gallery is written out column by column in site.toml, once per
    # breakpoint. Each arrangement becomes its own block and CSS shows the
    # one that fits, so the browser never chooses a column for us.
    by_slug = {p["slug"]: p for p in projects}

    # A series gathers several works onto one page. The works keep their own
    # records and their own cards on the home page; only the page is shared.
    series_by_slug = {x["slug"]: x for x in data.get("series", [])}
    member_series = {}
    for sr in series_by_slug.values():
        for m in sr["members"]:
            if m not in by_slug:
                sys.exit(f"ERROR: [[series]] {sr['slug']} lists an unknown work: {m}")
            for field in ("series_title", "series_anchor"):
                if not by_slug[m].get(field):
                    sys.exit(f"ERROR: {m} is in series {sr['slug']} but has no {field}")
            member_series[m] = sr

    def work_href(proj: dict, prefix: str = "work/") -> str:
        """Where a work's card or link points — a series member goes to its
        section of the shared page."""
        sr = member_series.get(proj["slug"])
        if sr:
            return f"{prefix}{sr['slug']}/#{proj['series_anchor']}"
        return f"{prefix}{proj['slug']}/"

    galleries = []
    for key, css in (("three_columns", "gallery-3"),
                     ("two_columns", "gallery-2"),
                     ("one_column", "gallery-1")):
        arrangement = data["layout"][key]
        listed = [slug for col in arrangement for slug in col]
        if sorted(listed) != sorted(by_slug):
            missing = sorted(set(by_slug) - set(listed))
            extra = sorted(set(listed) - set(by_slug))
            dupes = sorted({s for s in listed if listed.count(s) > 1})
            sys.exit(f"ERROR: [layout] {key} does not list every work exactly once."
                     + (f"\n  missing: {', '.join(missing)}" if missing else "")
                     + (f"\n  unknown: {', '.join(extra)}" if extra else "")
                     + (f"\n  repeated: {', '.join(dupes)}" if dupes else ""))
        cols = "\n".join(
            '<div class="gcol">\n'
            + "\n".join(card(by_slug[slug], by_slug[slug]["_thumb"],
                                work_href(by_slug[slug])) for slug in col)
            + "\n</div>"
            for col in arrangement)
        galleries.append(f'<section class="gallery {css}">\n{cols}\n</section>')

    hrel, hw, hh = hero_img
    body = f"""<main>
  <section class="hero">
    <img src="{hrel}" width="{hw}" height="{hh}" alt="{esc(hero.get('alt', ''))}" fetchpriority="high">
  </section>
  <section class="intro">
    <p class="intro-quote">“{esc(hero['quote'])}”</p>
    <p class="intro-link"><a href="about/">About the artist →</a></p>
  </section>
{chr(10).join(galleries)}
</main>"""
    write_page(OUT / "index.html", page(
        rel="", title=f"{site['title']} — {site['subtitle']}",
        description=site["description"], body=body, site=site,
        active="work", og_image=hrel, versions=versions))

    # ---- work and series pages ----------------------------------------
    # Page order follows the project list, except that a series is a single
    # stop: its members share one page, so previous/next skips over them.
    sequence = []
    for proj in projects:
        sr = member_series.get(proj["slug"])
        if sr is None:
            sequence.append({"slug": proj["slug"], "title": proj["title"],
                             "project": proj, "series": None})
        elif not any(e["slug"] == sr["slug"] for e in sequence):
            sequence.append({"slug": sr["slug"], "title": sr["title"],
                             "project": None, "series": sr})

    n = len(sequence)
    for idx, entry in enumerate(sequence):
        rel = "../../"
        prev_e, next_e = sequence[(idx - 1) % n], sequence[(idx + 1) % n]

        def make_pager(extra: str = "") -> str:
            return f"""<nav class="pager{extra}" aria-label="Works">
  <a href="../{prev_e['slug']}/" rel="prev">← {esc(prev_e['title'])}</a>
  <a class="pager-all" href="{rel}">All work</a>
  <a href="../{next_e['slug']}/" rel="next">{esc(next_e['title'])} →</a>
</nav>"""

        # ---- a series: one page, one section per work ------------------
        if entry["series"]:
            sr = entry["series"]
            head = [f'<h1>{esc(sr["title"])}</h1>']
            if tombstone(sr):
                head.append(f'<p class="tombstone">{tombstone(sr)}</p>')
            if sr.get("description"):
                head.append(f'<div class="prose">\n'
                            f'{paragraphs(sr["description"])}\n</div>')
            head.append('<p class="series-nav">' + " · ".join(
                f'<a href="#{esc(by_slug[m]["series_anchor"])}">'
                f'{esc(by_slug[m]["series_title"])}</a>'
                for m in sr["members"]) + '</p>')

            parts = []
            for i, m in enumerate(sr["members"]):
                mp = by_slug[m]
                # Each work keeps its own lightbox group, so the arrows stay
                # within that work instead of running through the whole series.
                lead, views = figures(mp, rel, esc(mp["slug"]),
                                      mp["series_title"], lead_first=(i == 0))
                mtext = (f'<div class="work-text prose">\n'
                         f'{paragraphs(mp["description"])}\n</div>'
                         if mp.get("description") else "")
                # A card on the home page lands part way down this page, so
                # each work states its own materials and where it falls in
                # the series rather than relying on the header above.
                place = f'{ordinal(i + 1)} in <a href="#top">series</a>'
                stone = tombstone(mp)
                label = (f'\n    <p class="tombstone">{stone}</p>' if stone else "")
                parts.append(
                    f'<section class="series-part" id="{esc(mp["series_anchor"])}">\n'
                    f'  <header class="series-head">\n'
                    f'    <h2>{esc(mp["series_title"])} '
                    f'<span class="series-index">({place})</span></h2>'
                    f'{label}\n'
                    f'  </header>\n'
                    f'{lead}\n{views}\n{mtext}\n</section>')

            sections = "\n".join(parts)
            body = f"""<main class="work">
{make_pager(" pager-top")}
  <header class="work-head" id="top">
{chr(10).join(head)}
  </header>
{sections}
{make_pager()}
</main>"""
            cover = by_slug.get(sr.get("cover", ""), by_slug[sr["members"][0]])
            write_page(OUT / "work" / sr["slug"] / "index.html", page(
                rel=rel, title=f"{sr['title']} — {site['title']}",
                description=f"{sr['title']} by {site['title']}"
                            + (f" — {sr['materials']}" if sr.get("materials") else ""),
                body=body, site=site, active="work",
                og_image=rel + cover["_large"][0][0], versions=versions))
            continue

        # ---- a single work ---------------------------------------------
        p = entry["project"]
        stone = tombstone(p)
        head = [f'<h1>{esc(p["title"])}</h1>']
        if stone:
            head.append(f'<p class="tombstone">{stone}</p>')
        for key in ("collection", "exhibited"):
            if p.get(key):
                head.append(f'<p class="note">{esc(p[key])}</p>')

        # The written account of a piece sits below its photographs, so the
        # work itself is the first thing on the page.
        text = ""
        if p.get("description"):
            text = (f'<div class="work-text prose">\n'
                    f'{paragraphs(p["description"])}\n</div>')

        lead, views = figures(p, rel, esc(p["slug"]), p["title"], lead_first=True)

        process_block = ""
        if p.get("_process"):
            strip = "\n".join(
                f'<img src="{rel}{img}" width="{w}" height="{h}" alt="" loading="lazy">'
                for img, w, h in p["_process_thumbs"][:3])
            process_block = f"""<a class="process-teaser" href="process/">
  <span class="process-strip">
{strip}
  </span>
  <span class="process-text">
    <span class="process-title">{esc(p.get('process_title', 'In the Studio'))}</span>
    <span class="process-sub">{len(p['_process'])} photographs from the making of this piece →</span>
  </span>
</a>"""

        body = f"""<main class="work">
{make_pager(" pager-top")}
  <header class="work-head">
{chr(10).join(head)}
  </header>
{lead}
{views}
{text}
{process_block}
{make_pager()}
</main>"""
        write_page(OUT / "work" / p["slug"] / "index.html", page(
            rel=rel, title=f"{p['title']} — {site['title']}",
            description=f"{p['title']} by {site['title']}"
                        + (f" — {p['materials']}" if p.get("materials") else ""),
            body=body, site=site, active="work",
            og_image=rel + p["_large"][0][0], versions=versions))

        # process page
        if p.get("_process"):
            prel = "../../../"
            tiles = "\n".join(
                f'<a class="tile" href="{prel}{img}" data-lightbox="process">'
                f'<img src="{prel}{timg}" width="{tw}" height="{th}" '
                f'alt="{esc(p["title"])} in progress — photo {i + 1}" loading="lazy"></a>'
                for i, ((img, _, _), (timg, tw, th))
                in enumerate(zip(p["_process"], p["_process_thumbs"])))
            body = f"""<main class="work">
  <header class="work-head">
    <p class="crumb"><a href="../">← {esc(p['title'])}</a></p>
    <h1>{esc(p.get('process_title', 'In the Studio'))}</h1>
    <div class="prose"><p>{esc(p.get('process_intro', ''))}</p></div>
  </header>
  <div class="tile-grid">
{tiles}
  </div>
</main>"""
            write_page(OUT / "work" / p["slug"] / "process" / "index.html", page(
                rel=prel, title=f"{p.get('process_title', 'Process')} — {site['title']}",
                description=f"Process photographs of {p['title']} by {site['title']}.",
                body=body, site=site, active="work", versions=versions))

    # ---- about page --------------------------------------------------
    arel, aw, ah = about_img
    shows = "\n".join(
        f'<div class="show"><span class="show-year">{esc(s["year"])}</span>'
        f'<span class="show-text">{esc(s["text"])}</span></div>'
        for s in about.get("exhibitions", []))
    body = f"""<main class="about">
  <div class="about-top">
    <figure class="about-photo">
      <img src="../{arel}" width="{aw}" height="{ah}" alt="Portrait of {esc(site['title'])}">
    </figure>
    <div class="about-statement">
      <h1>Artist Statement</h1>
      <div class="prose">
{paragraphs(about['statement'])}
      </div>
    </div>
  </div>
  <section class="about-bio">
    <h2>About</h2>
    <div class="prose">
{paragraphs(about['bio'])}
    </div>
  </section>
  <section class="about-shows">
    <h2>Selected Exhibitions &amp; Collections</h2>
{shows}
  </section>
  <section class="about-contact">
    <h2>Contact</h2>
    <p class="prose"><a href="mailto:{esc(site['email'])}">{esc(site['email'])}</a></p>
  </section>
</main>"""
    write_page(OUT / "about" / "index.html", page(
        rel="../", title=f"About — {site['title']}",
        description=f"About the sculptor {site['title']}: artist statement, "
                    "biography, and exhibition history.",
        body=body, site=site, active="about", og_image="../" + arel, versions=versions))

    prune()
    print(f"\nDone → {OUT}")


def write_page(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    KEPT.add(path.relative_to(OUT).as_posix())


def prune():
    """Delete generated pages left over from works that were removed.

    Only pages and copied assets are pruned. Everything under images/ is
    the stored artwork itself, not build output, so it is never touched
    here — remove photographs with import_photos.py instead.
    """
    for path in sorted(OUT.rglob("*"), reverse=True):
        rel = path.relative_to(OUT).as_posix()
        if rel == "images" or rel.startswith("images/"):
            continue
        if path.is_dir():
            if not any(path.iterdir()):
                path.rmdir()
            continue
        if rel not in KEPT and rel not in PRESERVE:
            print(f"  – removed {rel}")
            path.unlink()


FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="10" fill="#8a4520"/>
<path d="M18 46 L32 16 L46 46" fill="none" stroke="#f4ede2" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="24" y1="36" x2="40" y2="36" stroke="#d9c9a8" stroke-width="4" stroke-linecap="round"/>
</svg>
"""

if __name__ == "__main__":
    main()
