import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageOps, ImageDraw


# ---------- Data model ----------
@dataclass
class PhotoAsset:
    id: int
    role: str          # "element" or "background"
    path: str          # stringified path for JSON
    width: int
    height: int
    # The actual PIL image is kept in-memory but not serialized in summary
    _image: Image.Image = None


# ---------- I/O helpers ----------
def load_rgba_with_exif(path: Path) -> Image.Image:
    """Open an image, apply EXIF orientation, return RGBA."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)        # fixes rotated portraits, etc.
    return img.convert("RGBA")


def list_images(input_dir: Path) -> List[Path]:
    """Return image paths sorted by name; expects at least 6."""
    exts = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
    files = sorted([p for p in input_dir.iterdir() if p.suffix.lower() in exts])
    if len(files) < 6:
        raise ValueError(f"Need at least 6 images in {input_dir}, found {len(files)}.")
    return files[:6]  # take first 6 deterministically


def make_assets(paths: List[Path]) -> List[PhotoAsset]:
    """Create PhotoAsset objects from paths; 1-5 elements, 6 background."""
    assets: List[PhotoAsset] = []
    for i, p in enumerate(paths, start=1):
        role = "element" if i < 6 else "background"
        img = load_rgba_with_exif(p)
        assets.append(PhotoAsset(
            id=i,
            role=role,
            path=str(p),
            width=img.width,
            height=img.height,
            _image=img
        ))
    return assets


# ---------- Debug outputs ----------
def save_contact_sheet(assets: List[PhotoAsset], out_path: Path,
                       tile_size: Tuple[int, int] = (480, 320),
                       cols: int = 3) -> None:
    """Save a 2x3 grid preview to verify inputs quickly."""
    w, h = tile_size
    rows = (len(assets) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * w, rows * h), (245, 245, 245, 255))
    draw = ImageDraw.Draw(sheet)

    for idx, a in enumerate(assets):
        thumb = a._image.copy()
        thumb.thumbnail(tile_size, Image.Resampling.LANCZOS)
        x = (idx % cols) * w + (w - thumb.width) // 2
        y = (idx // cols) * h + (h - thumb.height) // 2
        sheet.alpha_composite(thumb, (x, y))

        # label
        label = f"{a.id}: {a.role}"
        tw, th = draw.textlength(label), 12
        draw.rectangle([x, y, x + tw + 8, y + th + 6], fill=(0, 0, 0, 120))
        draw.text((x + 4, y + 2), label, fill=(255, 255, 255, 230))

    sheet.convert("RGB").save(out_path, quality=90)


def save_normalized_images(assets: List[PhotoAsset], out_dir: Path,
                           max_side_element: int = 1600,
                           max_side_background: int = 2400) -> None:
    """Export normalized copies you’ll use in later steps."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for a in assets:
        img = a._image.copy()
        target = max_side_background if a.role == "background" else max_side_element
        # scale down if very large; preserve aspect
        if max(img.width, img.height) > target:
            img.thumbnail((target, target), Image.Resampling.LANCZOS)
        img.save(out_dir / f"{a.id:02d}_{a.role}.png")


def write_summary(assets: List[PhotoAsset], out_path: Path) -> None:
    summary = [{
        "id": a.id,
        "role": a.role,
        "path": a.path,
        "width": a.width,
        "height": a.height
    } for a in assets]
    out_path.write_text(json.dumps(summary, indent=2))


# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Step A: Input & Prep")
    parser.add_argument("--input", required=True, help="Folder containing 6 images")
    parser.add_argument("--outdir", default="outputs/stepA", help="Output folder for Step A artifacts")
    args = parser.parse_args()

    input_dir = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    paths = list_images(input_dir)
    assets = make_assets(paths)

    # Artifacts you can visually check:
    save_contact_sheet(assets, outdir / "contact_sheet.png")
    save_normalized_images(assets, outdir)

    # Machine-readable summary for later steps:
    write_summary(assets, outdir / "summary.json")

    print("✅ Step A complete.")
    print(f" - Contact sheet: {outdir/'contact_sheet.png'}")
    print(f" - Normalized images: {outdir}")
    print(f" - Summary JSON: {outdir/'summary.json'}")
    print("Next: Step B (Main element recognition & masks).")


if __name__ == "__main__":
    main()
