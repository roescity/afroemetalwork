# AFRoeMetalwork

Portfolio website for Alisa Formway Roe — sculpture in steel and bronze.

The site is fully static, generated into `docs/` and served by GitHub Pages.

## How it works

| File / folder | Role |
| --- | --- |
| `site.toml` | **All content**: work titles, materials, descriptions, ordering, artist statement, bio, exhibitions. Edit this. |
| `2026 filtered portfolio/` | Source photographs, one folder per work, plus `Hero.JPG` for the home-page banner. The file named `Primary.*` in each folder is that work's cover and lead image. |
| `build.py` | Generator. Resizes photos with `sips` (built into macOS) and writes HTML into `docs/`. |
| `rename_images.py` | Tidies photo filenames: `Primary.*` keeps its name, everything else becomes `1.jpg`, `2.jpg`, `3.jpg`… |
| `assets/` | Stylesheet and the small lightbox script (copied into `docs/`). |
| `docs/` | The generated site. Never edit by hand — rebuild instead. |

## Building and previewing

```bash
python3 build.py
```

(Requires Python 3.11+ and macOS for `sips`. Image resizing is incremental —
only new or changed photos are reprocessed. `--force` redoes everything.)

The build also prunes: delete a photo or remove a `[[projects]]` block, and
the matching pages and images disappear from `docs/` on the next run.

Note that the source photograph and document folders are **not** committed to
git (see `.gitignore`) — they are archived separately. You need them present
locally to rebuild.

Preview locally:

```bash
python3 -m http.server 4173 --directory docs
```

then open <http://localhost:4173/>.

## Common edits

- **Change any text** (description, materials, year, statement…): edit
  `site.toml`, rebuild.
- **Add a work**: create a folder of photos under `2026 filtered portfolio/`
  with a `Primary.jpg`, add a `[[projects]]` block to `site.toml` at the spot
  in the gallery order you want, rebuild.
- **Add photos to a work**: drop them in its folder, then run

  ```bash
  python3 rename_images.py && python3 build.py
  ```

  The `Primary` image becomes the large lead photo; the rest become the
  "More views" strip beneath it, in numeric order.
- **Reorder the photos within a work**: renumber the files (`1.jpg`, `2.jpg`,
  …) however you like and rebuild — the strip follows that order. To promote a
  different photo to the lead, swap its name with `Primary`.
- **Change the home-page banner**: replace `2026 filtered portfolio/Hero.JPG`.
  It is shown at whatever proportions the file has, so crop it to the banner
  shape you want before saving.
- **Reorder the gallery**: move `[[projects]]` blocks around, rebuild.
- **Remove a work**: delete its `[[projects]]` block (and, if you like, its
  folder), rebuild.

## Publishing on GitHub Pages

1. Commit and push (including `docs/`).
2. On GitHub: **Settings → Pages → Build and deployment → Deploy from a
   branch**, choose `main` and `/docs`.
3. The site appears at `https://<user>.github.io/<repo>/`. For a custom
   domain (e.g. `afroemetalwork.com`), add it under **Settings → Pages →
   Custom domain** and point the domain's DNS at GitHub Pages.
