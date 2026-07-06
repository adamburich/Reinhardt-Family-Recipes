"""Build the deployable recipe box.

Reads the original scans from ../Recipes/<Category>/, writes web-optimized
copies and thumbnails into images/ and thumbs/ here, and regenerates
recipes.json. Originals are never modified.

Usage:  py build.py
Rerun it whenever recipes are added, renamed, or re-filed; it skips images
whose outputs are already up to date.
"""
import io, json, pathlib, re, sys

from PIL import Image, ImageOps

HERE = pathlib.Path(__file__).parent
SRC = HERE.parent / "Recipes"
IMAGES = HERE / "images"   # lightbox size: readable recipe text
THUMBS = HERE / "thumbs"   # category-grid size
IMG_MAX = 1600
IMG_QUALITY = 78
THUMB_MAX = 560
THUMB_QUALITY = 72

PAGE_RE = re.compile(r"\s*\((\d+)\)\s*$")


def out_name(src: pathlib.Path) -> str:
    return src.stem + ".jpg"


def convert(src: pathlib.Path, dst: pathlib.Path, max_px: int, quality: int) -> bool:
    """Write a resized JPEG copy of src to dst. Returns True if (re)written."""
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # bake in phone-camera rotation
        im.thumbnail((max_px, max_px), Image.LANCZOS)
        if im.mode != "RGB":
            im = im.convert("RGB")
        im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return True


def main() -> None:
    if not SRC.is_dir():
        sys.exit(f"source folder not found: {SRC}")

    cats = []
    converted = 0
    total = 0
    for cat_dir in sorted((d for d in SRC.iterdir() if d.is_dir()),
                          key=lambda p: p.name.lower()):
        files = sorted((f for f in cat_dir.iterdir() if f.is_file()),
                       key=lambda p: p.name.lower())
        recipes: dict[str, dict] = {}
        order: list[str] = []
        for f in files:
            total += 1
            web = IMAGES / cat_dir.name / out_name(f)
            th = THUMBS / cat_dir.name / out_name(f)
            converted += convert(f, web, IMG_MAX, IMG_QUALITY)
            convert(f, th, THUMB_MAX, THUMB_QUALITY)

            # "Prefix - Title (2).jpeg" -> title "Title", page 2
            title = f.stem.split(" - ", 1)[1] if " - " in f.stem else f.stem
            m = PAGE_RE.search(title)
            page_no = int(m.group(1)) if m else 1
            base = (PAGE_RE.sub("", title) if m else title).replace("_", "'").strip()
            key = base.lower()
            if key not in recipes:
                recipes[key] = {"title": base, "pages": []}
                order.append(key)
            recipes[key]["pages"].append((page_no, {
                "img": f"images/{cat_dir.name}/{web.name}",
                "thumb": f"thumbs/{cat_dir.name}/{th.name}",
            }))

        recipe_list = []
        for key in order:
            r = recipes[key]
            recipe_list.append({
                "title": r["title"],
                "pages": [p for _, p in sorted(r["pages"], key=lambda x: x[0])],
            })
        slug = re.sub(r"[^a-z0-9]+", "-", cat_dir.name.lower()).strip("-")
        cats.append({"name": cat_dir.name, "slug": slug, "recipes": recipe_list})

    manifest = HERE / "recipes.json"
    manifest.write_text(
        json.dumps({"categories": cats}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    n_recipes = sum(len(c["recipes"]) for c in cats)
    print(f"{len(cats)} categories, {n_recipes} recipes, {total} scans "
          f"({converted} converted, {total - converted} already current)")
    print(f"manifest: {manifest}")


if __name__ == "__main__":
    main()
