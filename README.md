# AFRoeMetalwork

Portfolio website for Alisa Formway Roe — sculpture in steel and bronze.

The site is fully static, generated into `docs/` and served by GitHub Pages.

## How it works

| File / folder | Role |
| --- | --- |
| `site.toml` | **All words and ordering**: work titles, materials, descriptions, gallery order, artist statement, bio, exhibitions. Edit this. |
| `docs/images/` | **All photographs**, web-sized and committed. These are the site's own copy of the artwork — nothing else is needed to rebuild. |
| `build.py` | Writes the site's HTML from the two things above. |
| `import_photos.py` | Only for adding or replacing photographs: resizes originals into `docs/images/`. Needs macOS. |
| `assets/` | Stylesheet and lightbox script. |
| `docs/` | The generated site. Don't edit by hand — edit `site.toml` and rebuild. |

## Everyday use

```bash
python3 build.py
```

Needs only Python 3.11 or newer. It works on any computer that has this
repository — the original photo folders are **not** required, because the
photographs the site uses already live in `docs/images/`.

Preview what you built:

```bash
python3 -m http.server 4173 --directory docs
```

then open <http://localhost:4173/>. After rebuilding, hard-reload the page
(**⌘⇧R**) or the browser may show you the previous version.

## Common edits

All of these are edits to `site.toml`, followed by `python3 build.py`:

- **Change any text** — a description, materials, year, the artist statement.
- **Reorder the gallery** — move a `[[projects]]` block up or down. The home
  page fills three columns top-to-bottom, left to right.
- **Remove a work** — delete its `[[projects]]` block. Its pages disappear on
  the next build; to reclaim the disk space too, run
  `python3 import_photos.py --prune`.

## Adding new photographs

This is the only task that needs the original photos and a Mac.

1. Put the photographs in a folder, one folder per artwork, inside the folder
   named by `source_dir` in site.toml's `[import]` section. Name the best
   shot `Primary.jpg` — it becomes the cover and the large lead image. The
   others can be named anything; they appear as "More views" in filename
   order, so `1.jpg`, `2.jpg`, `3.jpg` gives you exact control.
2. For a brand-new artwork, add a `[[projects]]` block to `site.toml` where
   you want it in the gallery, with `slug`, `folder`, and `title`.
3. Then:

   ```bash
   python3 import_photos.py <slug>
   python3 build.py
   ```

   Leave off `<slug>` to import every artwork whose folder is present.

## Publishing

The site deploys from `main` at the `/docs` folder. Commit and push, and
GitHub Pages updates within about a minute.

To set it up the first time: **Settings → Pages → Build and deployment →
Deploy from a branch**, then choose `main` and the `/docs` folder.
