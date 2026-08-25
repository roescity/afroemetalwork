#!/usr/bin/env python3
"""Static-site generator for AFRoeMetalwork.

Reads site.toml + the portfolio image folders, writes a complete site
into docs/ (which GitHub Pages serves). Images are resized with sips
(built into macOS) into web-friendly sizes; originals are never touched.

Usage:
    python3 build.py            # incremental (skips images already done)
    python3 build.py --force    # regenerate everything, including images
"""

import html
import json
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs"
ASSETS = ROOT / "assets"
SIZES = {
    "hero": 2400,   # home-page banner (never upscaled)
    "large": 1800,  # work-page lead image / lightbox
    "thumb": 900,   # gallery cards and view strips
}
QUALITY = "82"    # JPEG quality percent

FORCE = "--force" in sys.argv

IMAGE_EXTS = {".jpg", ".jpeg"}

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


def natural_key(name: str):
    """Sort so 2.jpg comes before 10.jpg (see rename_images.py)."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def images_in(folder: Path):
    """Image files directly inside folder (not subfolders), in display order."""
    return sorted(
        (p for p in folder.iterdir()
         if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: natural_key(p.name),
    )


def sips_dims(path: Path):
    out = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    w = int(re.search(r"pixelWidth: (\d+)", out).group(1))
    h = int(re.search(r"pixelHeight: (\d+)", out).group(1))
    return w, h


def resize(src: Path, dst: Path, max_px: int):
    """Resize src to dst with the long edge at most max_px (never upscale)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    w, h = sips_dims(src)
    if max(w, h) <= max_px:
        cmd = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", QUALITY,
               str(src), "--out", str(dst)]
    else:
        cmd = ["sips", "--resampleHeightWidthMax", str(max_px),
               "-s", "format", "jpeg", "-s", "formatOptions", QUALITY,
               str(src), "--out", str(dst)]
    subprocess.run(cmd, check=True, capture_output=True)


class ImagePipeline:
    """Turns source photos into docs/images/... and remembers dimensions."""

    def __init__(self):
        self.manifest_path = OUT / "images" / ".manifest.json"
        try:
            self.manifest = json.loads(self.manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            self.manifest = {}

    def process(self, src: Path, rel_dir: str, kind: str):
        """kind: one of SIZES. Returns (site-relative path, w, h)."""
        max_px = SIZES[kind]
        name = f"{slugify(src.stem)}-{kind}.jpg"
        rel = f"images/{rel_dir}/{name}"
        dst = OUT / rel
        stale = FORCE or not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime
        if stale:
            print(f"  · {rel}")
            resize(src, dst, max_px)
            self.manifest.pop(rel, None)
        if rel not in self.manifest:
            w, h = sips_dims(dst)
            self.manifest[rel] = [w, h]
        KEPT.add(rel)
        w, h = self.manifest[rel]
        return rel, w, h

    def save(self):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        live = {k: v for k, v in self.manifest.items() if k in KEPT}
        self.manifest_path.write_text(json.dumps(live, indent=0))


def paragraphs(text: str, cls: str = "") -> str:
    """Blank-line separated text -> <p> blocks."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    attr = f' class="{cls}"' if cls else ""
    return "\n".join(f"<p{attr}>{esc(p)}</p>" for p in paras)


# --------------------------------------------------------------- templates

def page(*, rel: str, title: str, description: str, body: str,
         site: dict, active: str = "", og_image: str = "") -> str:
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
  <link rel="stylesheet" href="{rel}assets/style.css">
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
<script src="{rel}assets/lightbox.js" defer></script>
</body>
</html>
"""


def tombstone(p: dict) -> str:
    """The museum-label line: materials · dimensions · year."""
    bits = [p.get(k, "") for k in ("materials", "dimensions", "year")]
    bits = [esc(b) for b in bits if b]
    return " &nbsp;·&nbsp; ".join(bits)


def card(p: dict, thumb) -> str:
    rel_img, w, h = thumb
    meta = (f'\n    <span class="card-meta">{esc(p["materials"])}</span>'
            if p.get("materials") else "")
    return f"""<a class="card" href="work/{p['slug']}/">
  <img src="{rel_img}" width="{w}" height="{h}" alt="{esc(p['title'])}" loading="lazy">
  <span class="card-label">
    <span class="card-title">{esc(p['title'])}</span>{meta}
  </span>
</a>"""


# --------------------------------------------------------------- build

def main():
    with open(ROOT / "site.toml", "rb") as f:
        data = tomllib.load(f)
    site = data["site"]
    hero = data["hero"]
    about = data["about"]
    projects = data["projects"]
    src_root = ROOT / site["source_dir"]

    OUT.mkdir(exist_ok=True)
    (OUT / ".nojekyll").touch()
    pipe = ImagePipeline()

    # ---- assets ------------------------------------------------------
    out_assets = OUT / "assets"
    out_assets.mkdir(exist_ok=True)
    for f in ASSETS.iterdir():
        if f.is_file():
            shutil.copy2(f, out_assets / f.name)
            KEPT.add(f"assets/{f.name}")
    write_page(OUT / "favicon.svg", FAVICON)

    # ---- collect + process images per project -----------------------
    for p in projects:
        folder = src_root / p["folder"]
        if not folder.is_dir():
            sys.exit(f"ERROR: folder not found for {p['slug']}: {folder!r}")
        imgs = images_in(folder)
        if not imgs:
            sys.exit(f"ERROR: no images in {folder!r}")

        primary_name = p.get("primary", "")
        if primary_name:
            primary = folder / primary_name
            if not primary.exists():
                sys.exit(f"ERROR: primary {primary_name!r} missing in {folder!r}")
        else:
            named = [i for i in imgs if i.stem.lower() == "primary"]
            primary = named[0] if named else imgs[0]
            if not named:
                print(f"  ! {p['slug']}: no Primary image; using {primary.name}")

        p["_primary_src"] = primary
        p["_secondary_src"] = [i for i in imgs if i != primary]

        print(f"[{p['slug']}]")
        ordered = [primary] + p["_secondary_src"]
        p["_large"] = [pipe.process(i, p["slug"], "large") for i in ordered]
        p["_thumbs"] = [pipe.process(i, p["slug"], "thumb") for i in ordered]
        p["_thumb"] = p["_thumbs"][0]

        proc_name = p.get("process_folder", "")
        if proc_name:
            proc_dir = folder / proc_name
            p["_process"] = [pipe.process(i, f"{p['slug']}/process", "large")
                             for i in images_in(proc_dir)]
            p["_process_thumbs"] = [pipe.process(i, f"{p['slug']}/process", "thumb")
                                    for i in images_in(proc_dir)]

    # hero + about photo
    hero_src = src_root / hero["image"]
    if not hero_src.exists():
        sys.exit(f"ERROR: hero image not found: {hero_src!r}")
    hero_img = pipe.process(hero_src, "site", "hero")
    about_img = pipe.process(ROOT / site["about_photo"], "site", "large")
    pipe.save()

    # ---- home page ---------------------------------------------------
    cards = "\n".join(card(p, p["_thumb"]) for p in projects)
    hrel, hw, hh = hero_img
    body = f"""<main>
  <section class="hero">
    <img src="{hrel}" width="{hw}" height="{hh}" alt="{esc(hero.get('alt', ''))}" fetchpriority="high">
  </section>
  <section class="intro">
    <p class="intro-quote">“{esc(hero['quote'])}”</p>
    <p class="intro-link"><a href="about/">About the artist →</a></p>
  </section>
  <section class="grid" id="work">
{cards}
  </section>
</main>"""
    write_page(OUT / "index.html", page(
        rel="", title=f"{site['title']} — {site['subtitle']}",
        description=site["description"], body=body, site=site,
        active="work", og_image=hrel))

    # ---- work pages --------------------------------------------------
    n = len(projects)
    for idx, p in enumerate(projects):
        rel = "../../"
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

        # Lead image is sized to fit the window (see .lead in style.css);
        # any further views become a uniform-height strip that opens the
        # lightbox, so a page never scrolls past half-visible photographs.
        group = esc(p["slug"])
        lead_src, lw, lh = p["_large"][0]
        lead = (f'<figure class="lead">'
                f'<a href="{rel}{lead_src}" data-lightbox="{group}">'
                f'<img src="{rel}{lead_src}" width="{lw}" height="{lh}" '
                f'alt="{esc(p["title"])}" fetchpriority="high"></a></figure>')

        views = ""
        if len(p["_large"]) > 1:
            tiles = "\n".join(
                f'    <a class="view" href="{rel}{full}" data-lightbox="{group}">'
                f'<img src="{rel}{tn}" width="{tw}" height="{th}" '
                f'alt="{esc(p["title"])} — view {i + 2}" loading="lazy"></a>'
                for i, ((full, _, _), (tn, tw, th))
                in enumerate(zip(p["_large"][1:], p["_thumbs"][1:])))
            views = f"""<section class="views">
  <h2 class="views-label">More views</h2>
  <div class="views-strip">
{tiles}
  </div>
</section>"""

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

        prev_p = projects[(idx - 1) % n]
        next_p = projects[(idx + 1) % n]

        def make_pager(extra: str = "") -> str:
            return f"""<nav class="pager{extra}" aria-label="Works">
  <a href="../{prev_p['slug']}/" rel="prev">← {esc(prev_p['title'])}</a>
  <a class="pager-all" href="{rel}">All work</a>
  <a href="../{next_p['slug']}/" rel="next">{esc(next_p['title'])} →</a>
</nav>"""

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
            body=body, site=site, active="work", og_image=rel + p["_large"][0][0]))

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
                body=body, site=site, active="work"))

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
        body=body, site=site, active="about", og_image="../" + arel))

    prune()
    print(f"\nDone → {OUT}")


def write_page(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    KEPT.add(path.relative_to(OUT).as_posix())


def prune():
    """Delete generated files left over from removed works or photos."""
    for path in sorted(OUT.rglob("*"), reverse=True):
        if path.is_dir():
            if not any(path.iterdir()):
                path.rmdir()
            continue
        rel = path.relative_to(OUT).as_posix()
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
