"""CLI to convert an image into a printable, vector Perler bead pattern."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageOps
from sklearn.cluster import KMeans

try:  # Support both ``python scripts/...`` and package imports.
    from cleanup import cleanup_grid
    from palette import adaptive_palette, builtin_palette_names, build_shopping_list, compact_palette, hex_to_rgb, load_builtin_palette, load_inventory, load_palette, nearest_palette_indices, rgb_to_hex, write_shopping_list
    from report import write_report
    from svg_renderer import render_a4_pages, render_preview_svg, render_svg
    from validate_pattern import validate_pattern, validate_svg
except ImportError:  # pragma: no cover
    from .cleanup import cleanup_grid
    from .palette import adaptive_palette, builtin_palette_names, build_shopping_list, compact_palette, hex_to_rgb, load_builtin_palette, load_inventory, load_palette, nearest_palette_indices, rgb_to_hex, write_shopping_list
    from .report import write_report
    from .svg_renderer import render_a4_pages, render_preview_svg, render_svg
    from .validate_pattern import validate_pattern, validate_svg


MIN_GRID_SIZE, MAX_GRID_SIZE = 24, 112


@dataclass(frozen=True)
class ModeSettings:
    """Image-type decisions applied before user-specified cleanup overrides."""

    use_subject_crop: bool
    max_colours: int
    min_component_size: int
    cleanup_passes: int
    edge_protection: int
    resample: Image.Resampling
    prefer_face: bool = False


MODE_SETTINGS = {
    "auto": ModeSettings(True, 20, 3, 2, 0, Image.Resampling.LANCZOS),
    "portrait": ModeSettings(True, 18, 2, 1, 2, Image.Resampling.LANCZOS, prefer_face=True),
    "pet": ModeSettings(True, 18, 2, 1, 2, Image.Resampling.LANCZOS),
    "logo": ModeSettings(False, 20, 1, 0, 3, Image.Resampling.NEAREST),
    "landscape": ModeSettings(True, 14, 4, 2, 1, Image.Resampling.LANCZOS),
    "illustration": ModeSettings(True, 18, 2, 1, 3, Image.Resampling.LANCZOS),
    "art": ModeSettings(True, 18, 2, 1, 3, Image.Resampling.LANCZOS),
}


def mode_settings(mode: str) -> ModeSettings:
    """Return the declared strategy; centralising it makes mode behaviour auditable."""
    return MODE_SETTINGS[mode]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert an image into a physically buildable Perler Beads SVG pattern.")
    parser.add_argument("--input", required=True, help="Existing input image path.")
    parser.add_argument("--output", help="Construction-plan SVG path; defaults to the current working directory.")
    parser.add_argument("--width", type=int, default=56, help="Target grid width (default: 56).")
    parser.add_argument("--height", type=int, default=56, help="Target grid height (default: 56).")
    parser.add_argument("--max-colors", type=int, default=20, help="Maximum number of colours (1–20).")
    parser.add_argument("--mode", choices=tuple(MODE_SETTINGS), default="auto", help="Image strategy: auto, portrait, pet, logo, landscape, illustration, or art.")
    parser.add_argument("--auto-size", action="store_true", help="Fit grid dimensions to the detected subject aspect ratio.")
    parser.add_argument("--palette", help="Optional verified JSON or CSV bead palette.")
    parser.add_argument("--brand", choices=builtin_palette_names(), help="Use a shipped, source-documented physical bead palette.")
    parser.add_argument("--color-distance", choices=("rgb", "lab"), default="lab", help="Palette distance: RGB Euclidean or CIE76 Lab / Delta E (default: lab).")
    parser.add_argument("--inventory", help="Owned IDs as ID[:quantity],... or a JSON/CSV inventory file.")
    parser.add_argument("--inventory-bias", type=float, default=0.12, help="Prefer close owned colours from 0 to 1 (default: 0.12).")
    parser.add_argument("--inventory-only", action="store_true", help="Restrict physical matching to IDs listed in --inventory.")
    parser.add_argument("--shopping-list", help="CSV or JSON shopping-list path; defaults beside the SVG as <name>_shopping.csv.")
    parser.add_argument("--report", help="JSON processing-report path; defaults beside the SVG as <name>_report.json.")
    parser.add_argument("--no-crop", action="store_true", help="Fit image with padding instead of subject-aware cropping.")
    parser.add_argument("--crop", help="Crop source before transforms as x,y,width,height in source pixels.")
    parser.add_argument("--mirror", choices=("none", "horizontal", "vertical", "both"), default="none", help="Mirror the source image before conversion.")
    parser.add_argument("--rotate", choices=(0, 90, 180, 270), type=int, default=0, help="Rotate clockwise before conversion.")
    parser.add_argument("--remove-background", action="store_true", help="Estimate and replace the background with --background-color.")
    parser.add_argument("--background-color", default="#FFFFFF", help="HEX background used for transparency and background removal.")
    parser.add_argument("--min-component-size", type=int, help="Override the mode's minimum connected-region size.")
    parser.add_argument("--cleanup-passes", type=int, help="Override the mode's maximum cleanup iterations.")
    parser.add_argument("--bead-shape", choices=("circle", "square"), default="circle", help="Vector bead cell shape.")
    parser.add_argument("--bead-size-mm", type=float, help="Convenience shorthand that sets both bead diameter and pitch in mm.")
    parser.add_argument("--bead-diameter-mm", type=float, default=5.0, help="Physical bead diameter in mm (default: 5).")
    parser.add_argument("--bead-pitch-mm", type=float, default=5.0, help="Centre-to-centre bead spacing in mm (default: 5).")
    parser.add_argument("--finished-width-mm", type=float, help="Override pitch to make the finished grid this wide in mm.")
    parser.add_argument("--cell-size", type=int, default=12, help="SVG screen-cell spacing in pixels (default: 12).")
    parser.add_argument("--preview", action="store_true", help="Also write a clean pixel-preview SVG beside the construction plan.")
    parser.add_argument("--preview-output", help="Optional pixel-preview SVG destination (requires --preview).")
    parser.add_argument("--a4-pages", action="store_true", help="Also generate 100%%-scale labelled A4 construction tiles.")
    parser.add_argument("--pages-dir", help="Directory for A4 tile SVGs; defaults beside the construction plan.")
    parser.add_argument("--page-orientation", choices=("portrait", "landscape"), default="portrait", help="A4 tile orientation (default: portrait).")
    return parser


def resolve_output_path(input_path: Path, output: str | None, width: int, height: int) -> Path:
    destination = Path(output).expanduser().resolve() if output else (Path.cwd() / f"{input_path.stem}_perler_{width}x{height}.svg").resolve()
    if destination.suffix.lower() != ".svg":
        raise ValueError(f"Construction-plan output must end in .svg, received: {destination.name}. Use --output pattern.svg.")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OSError(f"Cannot create output directory {destination.parent}. Choose a writable --output path.") from error
    if not os.access(destination.parent, os.W_OK):
        raise PermissionError(f"Output directory is not writable: {destination.parent}. Choose a writable --output path.")
    return destination


def parse_crop(value: str, image: Image.Image) -> tuple[int, int, int, int]:
    """Parse a source-space x,y,width,height crop and constrain it to the image."""
    try:
        x, y, width, height = (int(piece.strip()) for piece in value.split(","))
    except ValueError as error:
        raise ValueError("--crop must be x,y,width,height using integer source pixels.") from error
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError("--crop must be wholly inside the source image with positive dimensions.")
    return x, y, x + width, y + height


def load_image(path: Path, background: str = "#FFFFFF") -> Image.Image:
    """Load source image, honour orientation, and flatten transparency to a colour."""
    background_rgb = hex_to_rgb(background)
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    return Image.alpha_composite(Image.new("RGBA", image.size, (*background_rgb, 255)), image).convert("RGB")


def apply_transforms(image: Image.Image, *, crop: str | None, mirror: str, rotate: int) -> Image.Image:
    """Apply user-controlled source crop, reflection, and clockwise rotation."""
    result = image.crop(parse_crop(crop, image)) if crop else image
    if mirror in {"horizontal", "both"}:
        result = ImageOps.mirror(result)
    if mirror in {"vertical", "both"}:
        result = ImageOps.flip(result)
    return result.rotate(-rotate, expand=True) if rotate else result


def detect_face_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Detect the main face locally and expand it to include hair and shoulders."""
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        return None
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    minimum = max(24, min(image.width, image.height) // 9)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(minimum, minimum))
    if len(faces) == 0:
        return None
    image_center = np.array((image.width / 2, image.height / 2))
    x, y, width, height = max(
        faces,
        key=lambda face: face[2] * face[3] - 0.08 * np.linalg.norm(np.array((face[0] + face[2] / 2, face[1] + face[3] / 2)) - image_center),
    )
    # Head/hair needs more space above; shoulders/garment need more space below.
    left, top = int(x - width * 0.7), int(y - height * 0.85)
    right, bottom = int(x + width * 1.7), int(y + height * 2.25)
    return max(0, left), max(0, top), min(image.width, right), min(image.height, bottom)


def estimate_foreground_mask(image: Image.Image) -> np.ndarray:
    """Estimate foreground pixels from border contrast and retain useful components."""
    rgb = np.asarray(image)
    height, width = rgb.shape[:2]
    if min(width, height) < 8:
        return np.ones((height, width), dtype=bool)
    border = max(1, min(width, height) // 20)
    border_pixels = np.concatenate((rgb[:border].reshape(-1, 3), rgb[-border:].reshape(-1, 3), rgb[:, :border].reshape(-1, 3), rgb[:, -border:].reshape(-1, 3)))
    background = np.median(border_pixels, axis=0)
    distance = np.linalg.norm(rgb.astype(np.float32) - background, axis=2)
    edges = cv2.Canny(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), 60, 140)
    mask = ((distance > max(18.0, float(np.percentile(distance, 70)))) | (edges > 0)).astype(np.uint8) * 255
    kernel_size = max(3, min(width, height) // 28)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((kernel_size, kernel_size), dtype=np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    result = np.zeros_like(mask, dtype=bool)
    minimum_area = width * height * 0.003
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= minimum_area:
            result[labels == index] = True
    return result


def detect_subject_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    """Select the strongest central foreground component; otherwise use all image."""
    mask = estimate_foreground_mask(image).astype(np.uint8)
    height, width = mask.shape
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    candidates, area = [], width * height
    for index in range(1, count):
        x, y, component_width, component_height, component_area = stats[index]
        if component_area < area * 0.008:
            continue
        center_x, center_y = centroids[index]
        centrality = 1.0 - min(1.0, np.hypot(center_x - width / 2, center_y - height / 2) / np.hypot(width / 2, height / 2))
        candidates.append((component_area / area + centrality * 0.12, (int(x), int(y), int(component_width), int(component_height))))
    if not candidates:
        return 0, 0, width, height
    _, (x, y, component_width, component_height) = max(candidates, key=lambda item: item[0])
    padding_x, padding_y = max(2, int(component_width * 0.09)), max(2, int(component_height * 0.09))
    return max(0, x - padding_x), max(0, y - padding_y), min(width, x + component_width + padding_x), min(height, y + component_height + padding_y)


def remove_background(image: Image.Image, background: str) -> Image.Image:
    """Replace non-subject pixels with a caller-selected solid background colour."""
    pixels = np.asarray(image).copy()
    pixels[~estimate_foreground_mask(image)] = hex_to_rgb(background)
    return Image.fromarray(pixels, mode="RGB")


def edge_protection_mask(image: Image.Image, *, width: int, height: int, strength: int, resample: Image.Resampling) -> np.ndarray | None:
    """Return a small-grid edge mask used to avoid deleting signature details."""
    if strength <= 0:
        return None
    resized = np.asarray(image.resize((width, height), resample), dtype=np.uint8)
    gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
    low_threshold = {1: 72, 2: 52, 3: 35}[min(strength, 3)]
    edges = cv2.Canny(gray, low_threshold, low_threshold * 2)
    if strength >= 2:
        edges = cv2.dilate(edges, np.ones((2, 2), dtype=np.uint8), iterations=1)
    return edges.astype(bool)


def choose_grid_size(width: int, height: int, *, base_width: int, base_height: int, auto_size: bool) -> tuple[int, int]:
    if base_width < MIN_GRID_SIZE or base_height < MIN_GRID_SIZE:
        raise ValueError(f"Grid dimensions must each be at least {MIN_GRID_SIZE}.")
    if not auto_size:
        return base_width, base_height
    aspect_ratio = width / max(1, height)
    if aspect_ratio >= 1:
        grid_width = min(MAX_GRID_SIZE, max(base_width, round(base_height * aspect_ratio)))
        return int(grid_width), max(MIN_GRID_SIZE, int(round(grid_width / aspect_ratio)))
    grid_height = min(MAX_GRID_SIZE, max(base_height, round(base_width / aspect_ratio)))
    return max(MIN_GRID_SIZE, int(round(grid_height * aspect_ratio))), int(grid_height)


def crop_to_aspect(image: Image.Image, *, target_width: int, target_height: int, use_subject: bool, subject_bbox: tuple[int, int, int, int] | None = None, resample: Image.Resampling = Image.Resampling.LANCZOS) -> Image.Image:
    if not use_subject:
        return ImageOps.pad(image, (target_width * 10, target_height * 10), color="white", method=resample)
    subject = image.crop(subject_bbox or detect_subject_bbox(image))
    target_aspect, subject_aspect = target_width / target_height, subject.width / subject.height
    if subject_aspect > target_aspect:
        crop_width = round(subject.height * target_aspect)
        crop_left = max(0, (subject.width - crop_width) // 2)
        return subject.crop((crop_left, 0, crop_left + crop_width, subject.height))
    crop_height = round(subject.width / target_aspect)
    crop_top = max(0, (subject.height - crop_height) // 2)
    return subject.crop((0, crop_top, subject.width, crop_top + crop_height))


def quantize_to_grid(image: Image.Image, *, width: int, height: int, max_colours: int, palette: list[dict] | None, color_distance: str = "lab", inventory: dict[str, int | None] | None = None, inventory_bias: float = 0.12, inventory_only: bool = False, resample: Image.Resampling = Image.Resampling.LANCZOS) -> tuple[np.ndarray, list[dict]]:
    """Resize then quantize to palette-index cells, with stable adaptive IDs."""
    pixels = np.asarray(image.resize((width, height), resample), dtype=np.uint8).reshape(-1, 3)
    if palette:
        source = pixels.reshape(height, width, 3)
        initial = nearest_palette_indices(source, palette, metric=color_distance, inventory=inventory, inventory_bias=inventory_bias, inventory_only=inventory_only)
        used = np.unique(initial)
        if len(used) > max_colours:
            frequency = np.bincount(initial.ravel(), minlength=len(palette))
            used = np.argsort(-frequency, kind="stable")[:max_colours]
            palette = [palette[int(index)] for index in used]
            initial = nearest_palette_indices(source, palette, metric=color_distance, inventory=inventory, inventory_bias=inventory_bias, inventory_only=inventory_only)
        else:
            palette = [palette[int(index)] for index in used]
            remap = {int(old): new for new, old in enumerate(used)}
            initial = np.vectorize(remap.__getitem__, otypes=[np.int16])(initial)
        return initial.astype(np.int16), palette
    unique = np.unique(pixels, axis=0)
    clusters = min(max_colours, len(unique))
    if clusters == 1:
        return np.zeros((height, width), dtype=np.int16), adaptive_palette(unique)
    model = KMeans(n_clusters=clusters, random_state=42, n_init="auto")
    labels = model.fit_predict(pixels)
    centres = np.clip(np.rint(model.cluster_centers_), 0, 255).astype(np.uint8)
    order = np.argsort(-np.bincount(labels, minlength=clusters), kind="stable")
    old_to_new = np.empty(clusters, dtype=np.int16)
    old_to_new[order] = np.arange(clusters, dtype=np.int16)
    return old_to_new[labels].reshape(height, width), adaptive_palette(centres[order])


def _preview_path(output_path: Path, explicit_output: str | None) -> Path:
    return Path(explicit_output).expanduser().resolve() if explicit_output else output_path.with_name(f"{output_path.stem}_preview.svg")


def _shopping_path(output_path: Path, explicit_output: str | None) -> Path:
    return Path(explicit_output).expanduser().resolve() if explicit_output else output_path.with_name(f"{output_path.stem}_shopping.csv")


def _report_path(output_path: Path, explicit_output: str | None) -> Path:
    return Path(explicit_output).expanduser().resolve() if explicit_output else output_path.with_name(f"{output_path.stem}_report.json")


def run_conversion(args: argparse.Namespace, *, emit: Callable[[str], None] | None = print) -> dict:
    """Run one conversion from parsed arguments and return its JSON manifest.

    ``emit=None`` keeps the conversion silent.  This is used by the MCP server,
    whose stdio transport reserves stdout for protocol messages.
    """
    def report_progress(message: str) -> None:
        if emit is not None:
            emit(message)

    settings = mode_settings(args.mode)
    if not 1 <= args.max_colors <= 20:
        raise ValueError("--max-colors must be between 1 and 20.")
    min_component_size = args.min_component_size if args.min_component_size is not None else settings.min_component_size
    cleanup_passes = args.cleanup_passes if args.cleanup_passes is not None else settings.cleanup_passes
    if min_component_size < 1 or cleanup_passes < 0:
        raise ValueError("Cleanup component size must be positive and pass count non-negative.")
    bead_diameter = args.bead_size_mm if args.bead_size_mm is not None else args.bead_diameter_mm
    bead_pitch = args.bead_size_mm if args.bead_size_mm is not None else args.bead_pitch_mm
    if args.cell_size < 4 or bead_diameter <= 0 or bead_pitch <= 0:
        raise ValueError("Cell size, bead diameter, and bead pitch must be positive.")
    if not 0 <= args.inventory_bias <= 1:
        raise ValueError("--inventory-bias must be between 0 and 1.")
    if args.palette and args.brand:
        raise ValueError("Use either --palette or --brand, not both.")
    if bead_diameter > bead_pitch:
        raise ValueError("--bead-diameter-mm cannot exceed --bead-pitch-mm.")
    background = rgb_to_hex(hex_to_rgb(args.background_color))
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input image not found: {input_path}. Check --input and use an existing PNG, JPG, WEBP, or PPM file.")
    original = load_image(input_path, background)
    if min(original.size) < 2:
        raise ValueError(f"Input image is too small ({original.width}x{original.height}px). Use an image at least 2x2 pixels; a 1-pixel image cannot preserve a buildable composition.")
    source_crop = parse_crop(args.crop, original) if args.crop else None
    source = apply_transforms(original, crop=args.crop, mirror=args.mirror, rotate=args.rotate)
    if args.remove_background:
        source = remove_background(source, background)
    use_subject_crop = settings.use_subject_crop and not args.no_crop
    if use_subject_crop and settings.prefer_face:
        bbox = detect_face_bbox(source) or detect_subject_bbox(source)
    else:
        bbox = detect_subject_bbox(source) if use_subject_crop else (0, 0, source.width, source.height)
    grid_width, grid_height = choose_grid_size(bbox[2] - bbox[0], bbox[3] - bbox[1], base_width=args.width, base_height=args.height, auto_size=args.auto_size)
    pitch = args.finished_width_mm / grid_width if args.finished_width_mm else bead_pitch
    if pitch <= 0 or bead_diameter > pitch:
        raise ValueError("Finished width produces a pitch smaller than the bead diameter.")
    palette = load_builtin_palette(args.brand) if args.brand else load_palette(args.palette)
    inventory = load_inventory(args.inventory)
    if inventory and palette:
        unknown_inventory_ids = sorted(set(inventory) - {entry["id"] for entry in palette})
        if unknown_inventory_ids:
            raise ValueError(f"Inventory IDs not found in the selected palette: {', '.join(unknown_inventory_ids)}.")
    if args.inventory_only and not inventory:
        raise ValueError("--inventory-only requires --inventory.")
    effective_max_colours = min(args.max_colors, settings.max_colours)
    prepared = crop_to_aspect(source, target_width=grid_width, target_height=grid_height, use_subject=use_subject_crop, subject_bbox=bbox, resample=settings.resample)
    edge_mask = edge_protection_mask(prepared, width=grid_width, height=grid_height, strength=settings.edge_protection, resample=settings.resample)
    grid, palette = quantize_to_grid(prepared, width=grid_width, height=grid_height, max_colours=effective_max_colours, palette=palette, color_distance=args.color_distance, inventory=inventory, inventory_bias=args.inventory_bias, inventory_only=args.inventory_only, resample=settings.resample)
    pre_cleanup_grid = grid.copy()
    cleaned_grid = cleanup_grid(grid, min_component_size=min_component_size, passes=cleanup_passes, protected_mask=edge_mask)
    cleaned_cell_count = int(np.count_nonzero(pre_cleanup_grid != cleaned_grid))
    grid, palette = compact_palette(cleaned_grid, palette)
    stats = validate_pattern(grid=grid, palette=palette, max_colors=effective_max_colours)
    output_path = resolve_output_path(input_path, args.output, grid_width, grid_height)
    appearance = {"bead_shape": args.bead_shape, "bead_diameter_mm": bead_diameter, "bead_pitch_mm": pitch}
    render_svg(grid=grid, palette=palette, output_path=output_path, cell_size=args.cell_size, metadata={"title": f"{input_path.stem} Perler Pattern", "description": f"Source: {input_path.name}; strategy: {args.mode}"}, **appearance)
    validate_svg(output_path, expected_total=stats["total_beads"], grid=grid, palette=palette, require_legend=True)
    report_progress(f"Generated construction plan: {output_path}")
    shopping_path = _shopping_path(output_path, args.shopping_list)
    write_shopping_list(build_shopping_list(grid, palette, inventory), shopping_path)
    report_progress(f"Generated shopping list: {shopping_path}")
    artifacts = {"construction_plan": str(output_path), "shopping_list": str(shopping_path)}
    if args.preview:
        preview_path = _preview_path(output_path, args.preview_output)
        render_preview_svg(grid=grid, palette=palette, output_path=preview_path, background=background, **appearance)
        validate_svg(preview_path, expected_total=stats["total_beads"], grid=grid, palette=palette)
        report_progress(f"Generated pixel preview: {preview_path}")
        artifacts["preview"] = str(preview_path)
    if args.a4_pages:
        pages_dir = Path(args.pages_dir).expanduser().resolve() if args.pages_dir else output_path.parent / f"{output_path.stem}_a4_pages"
        pages = render_a4_pages(grid=grid, palette=palette, output_dir=pages_dir, base_name=output_path.stem, orientation=args.page_orientation, **appearance)
        for page in pages:
            validate_svg(page)
        report_progress(f"Generated {len(pages)} A4 tiles: {pages_dir}")
        artifacts["a4_pages"] = [str(page) for page in pages]
    report_path = _report_path(output_path, args.report)
    report = {
        "input": {"path": str(input_path), "original_size_px": {"width": original.width, "height": original.height}, "source_crop_px": list(source_crop) if source_crop else None, "transformed_size_px": {"width": source.width, "height": source.height}, "subject_bbox_px": list(bbox) if use_subject_crop else None},
        "processing": {"mode": args.mode, "color_distance": args.color_distance, "background_removed": args.remove_background, "cleanup": {"min_component_size": min_component_size, "passes": cleanup_passes, "beads_before": int(pre_cleanup_grid.size), "beads_after": int(grid.size), "colours_before": len(set(int(value) for value in pre_cleanup_grid.ravel())), "colours_after": len(palette), "changed_cells": cleaned_cell_count}},
        "pattern": {"grid_size": {"width": stats["width"], "height": stats["height"]}, "physical_size_mm": {"width": grid_width * pitch, "height": grid_height * pitch}, "total_beads": stats["total_beads"], "colour_counts": stats["colour_counts"], "palette": palette, "grid": grid.tolist()},
        "artifacts": artifacts,
    }
    artifacts["report"] = str(report_path)
    report["artifacts"] = artifacts
    write_report(report, report_path)
    report_progress(f"Generated processing report: {report_path}")
    report_progress(f"Mode: {args.mode} | grid: {stats['width']}x{stats['height']} | {grid_width * pitch:.1f}x{grid_height * pitch:.1f} mm | colours: {len(palette)} | beads: {stats['total_beads']}")
    return report


def _run() -> None:
    run_conversion(build_parser().parse_args())


def main() -> None:
    """Run the CLI with concise, actionable errors instead of a Python traceback."""
    try:
        _run()
    except (OSError, ValueError) as error:
        raise SystemExit(f"error: {error}") from error


if __name__ == "__main__":
    main()
