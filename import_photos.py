#!/usr/bin/env python3
"""Bring original photographs into the site's own image store.

The site is built from the web-sized images kept in docs/images/, which
are committed to the repo. This script is what puts them there: it reads
originals from the folders named in site.toml's [import] section, resizes
them with sips (built into macOS), and records their dimensions.

You only need this when adding, replacing, or removing photographs.
Everyday rebuilds just need build.py, which does not use this script or
the original folders at all.

    python3 import_photos.py                # every work whose folder is present
    python3 import_photos.py marianas       # one work, by slug
    python3 import_photos.py --site         # just the hero and portrait
    python3 import_photos.py --prune        # drop images for removed works
    python3 import_photos.py --force        # redo images that already exist

In each source folder, a file named Primary.* becomes the cover and lead
image; the rest become 1, 2, 3 … in natural filename order.
"""

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs"
IMAGES = OUT / "images"
MANIFEST = IMAGES / ".manifest.json"

SIZES = {"hero": 2400, "large": 1800, "thumb": 900}
QUALITY = "82"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif"}

FORCE = "--force" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]


def natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def originals_in(folder: Path):
    """Photographs directly inside folder, in natural filename order."""
    return sorted((p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
                  key=lambda p: natural_key(p.name))


def explain_empty(folder: Path) -> str:
    """Say why a folder yielded no photographs, rather than just 'none'."""
    entries = list(folder.iterdir())
    stubs = [e for e in entries if e.suffix.lower() == ".icloud"]
    others = sorted({e.suffix.lower() or "(no extension)" for e in entries
                     if e.is_file() and e.suffix.lower() not in IMAGE_EXTS
                     and e.suffix.lower() != ".icloud"})
    subs = [e.name for e in entries if e.is_dir()]
    lines = []
    if stubs:
        lines.append(f"  {len(stubs)} file(s) are iCloud placeholders that are not "
                     "downloaded to this Mac.\n"
                     "  In Finder, right-click the folder and choose "
                     "\"Download Now\", then retry.")
    if others:
        lines.append(f"  other file types present: {', '.join(others)}")
    if subs:
        lines.append(f"  subfolders (not searched): {', '.join(sorted(subs))}")
    if not entries:
        lines.append("  the folder is empty.")
    lines.append(f"  recognised: {', '.join(sorted(IMAGE_EXTS))}")
    return "\n".join(lines)


def sips_dims(path: Path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return (int(re.search(r"pixelWidth: (\d+)", out).group(1)),
            int(re.search(r"pixelHeight: (\d+)", out).group(1)))


def resize(src: Path, dst: Path, max_px: int):
    dst.parent.mkdir(parents=True, exist_ok=True)
    w, h = sips_dims(src)
    cmd = ["sips"]
    if max(w, h) > max_px:                      # never enlarge a photograph
        cmd += ["--resampleHeightWidthMax", str(max_px)]
    cmd += ["-s", "format", "jpeg", "-s", "formatOptions", QUALITY,
            str(src), "--out", str(dst)]
    subprocess.run(cmd, check=True, capture_output=True)


class Store:
    def __init__(self):
        try:
            self.dims = json.loads(MANIFEST.read_text())
        except (OSError, json.JSONDecodeError):
            self.dims = {}

    def put(self, src: Path, rel: str, kind: str):
        dst = OUT / rel
        if FORCE or not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            print(f"  · {rel}")
            resize(src, dst, SIZES[kind])
            self.dims.pop(rel, None)
        if rel not in self.dims:
            self.dims[rel] = list(sips_dims(dst))

    def save(self):
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(self.dims, indent=0))

    def drop(self, rel: str):
        (OUT / rel).unlink(missing_ok=True)
        self.dims.pop(rel, None)


def import_folder(store: Store, src: Path, rel_dir: str, label: str,
                  numbered_only: bool = False):
    """Resize one folder of originals into docs/images/<rel_dir>/.

    Artwork folders get a 'primary' cover plus 1, 2, 3 …; process folders
    are numbered straight through, with no cover image.
    """
    imgs = originals_in(src)
    if not imgs:
        sys.exit(f"ERROR: no photographs in {src}\n{explain_empty(src)}")

    if numbered_only:
        pairs = [(str(n), i) for n, i in enumerate(imgs, 1)]
    else:
        primary = next((i for i in imgs if i.stem.lower() == "primary"), None)
        rest = [i for i in imgs if i is not primary]
        if primary is None:
            print(f"  ! {label}: no Primary image; using {rest[0].name} as the cover")
            primary, rest = rest[0], rest[1:]
        pairs = [("primary", primary)] + [(str(n), i) for n, i in enumerate(rest, 1)]

    for base, img in pairs:
        for kind in ("large", "thumb"):
            store.put(img, f"images/{rel_dir}/{base}-{kind}.jpg", kind)

    # photographs removed from the source folder should leave the store too
    keep = {f"{b}-{k}.jpg" for b, _ in pairs for k in ("large", "thumb")}
    folder = OUT / "images" / rel_dir
    for f in folder.glob("*.jpg"):
        if f.name not in keep:
            print(f"  – {f.name}")
            store.drop(f"images/{rel_dir}/{f.name}")


def main():
    with open(ROOT / "site.toml", "rb") as f:
        data = tomllib.load(f)
    conf = data["import"]
    projects = data["projects"]
    src_root = ROOT / conf["source_dir"]
    store = Store()

    if "--prune" in sys.argv:
        live = {p["slug"] for p in projects}
        for d in sorted(IMAGES.iterdir()):
            if d.is_dir() and d.name != "site" and d.name not in live:
                for f in d.rglob("*.jpg"):
                    store.drop(f.relative_to(OUT).as_posix())
                print(f"  – removed images for {d.name}")
        store.save()
        return

    if "--site" in sys.argv or not args:
        for key, rel, kind in (("hero", "images/site/hero.jpg", "hero"),
                               ("portrait", "images/site/portrait.jpg", "large")):
            src = ROOT / conf[key]
            if src.exists():
                print(f"[{key}]")
                store.put(src, rel, kind)
            elif "--site" in sys.argv:
                sys.exit(f"ERROR: {key} original not found: {src}")
        if "--site" in sys.argv:
            store.save()
            print("\nDone. Now run: python3 build.py")
            return

    wanted = set(args) if args else None
    if wanted and (unknown := wanted - {p["slug"] for p in projects}):
        sys.exit(f"ERROR: no such work in site.toml: {', '.join(sorted(unknown))}")

    done = 0
    for p in projects:
        if wanted and p["slug"] not in wanted:
            continue
        folder = src_root / p.get("folder", "")
        if not folder.is_dir():
            if wanted:
                sys.exit(f"ERROR: source folder not found for {p['slug']}: {folder}")
            continue                      # nothing to import for this work
        print(f"[{p['slug']}]")
        import_folder(store, folder, p["slug"], p["title"])
        if p.get("process_folder"):
            proc = folder / p["process_folder"]
            if proc.is_dir():
                import_folder(store, proc, f"{p['slug']}/process",
                              f"{p['title']} process", numbered_only=True)
        done += 1

    store.save()
    print(f"\nimported {done} work(s). Now run: python3 build.py")


if __name__ == "__main__":
    main()
