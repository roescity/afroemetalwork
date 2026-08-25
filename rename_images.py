#!/usr/bin/env python3
"""Give the portfolio photographs tidy, predictable filenames.

Within each work's folder, `Primary.*` keeps its name (it is the cover and
lead image) and every other photograph is renamed 1.jpg, 2.jpg, 3.jpg … in
the order it currently appears on the site. Process subfolders are numbered
straight through from 1.

Run this after dropping new photos into a folder, then run build.py.

    python3 rename_images.py --dry-run   # show what would change
    python3 rename_images.py             # do it
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGE_EXTS = {".jpg", ".jpeg"}
DRY = "--dry-run" in sys.argv


def natural_key(name: str):
    """Sort so 2.jpg comes before 10.jpg."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def images_in(folder: Path):
    return sorted(
        (p for p in folder.iterdir()
         if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: natural_key(p.name),
    )


def renumber(folder: Path, keep_primary: bool) -> int:
    """Rename the images in one folder. Returns how many moved."""
    imgs = images_in(folder)
    if keep_primary:
        imgs = [p for p in imgs if p.stem.lower() != "primary"]

    targets = [folder / f"{i + 1}.jpg" for i in range(len(imgs))]
    pairs = [(src, dst) for src, dst in zip(imgs, targets) if src != dst]
    if not pairs:
        return 0

    for src, dst in pairs:
        print(f"    {src.name}  →  {dst.name}")
    if DRY:
        return len(pairs)

    # Two phases, so a target name that is currently in use by another
    # photograph can never be clobbered mid-rename.
    staged = []
    for i, (src, dst) in enumerate(pairs):
        tmp = folder / f".renaming-{i}.jpg"
        src.rename(tmp)
        staged.append((tmp, dst))
    for tmp, dst in staged:
        tmp.rename(dst)
    return len(pairs)


def main():
    with open(ROOT / "site.toml", "rb") as f:
        data = tomllib.load(f)
    src_root = ROOT / data["site"]["source_dir"]

    total = 0
    for p in data["projects"]:
        folder = src_root / p["folder"]
        if not folder.is_dir():
            print(f"!  missing folder for {p['slug']}: {folder}")
            continue
        print(f"[{p['slug']}]")
        total += renumber(folder, keep_primary=True)

        proc = p.get("process_folder", "")
        if proc and (folder / proc).is_dir():
            print(f"[{p['slug']} / {proc}]")
            total += renumber(folder / proc, keep_primary=False)

    verb = "would rename" if DRY else "renamed"
    print(f"\n{verb} {total} file(s)."
          + ("" if DRY else "  Now run: python3 build.py"))


if __name__ == "__main__":
    main()
