"""Standalone printable SVG renderers for Perler bead grids."""

from __future__ import annotations

from collections import Counter
from html import escape
from math import ceil, floor
from pathlib import Path

import numpy as np

try:  # Support both ``python scripts/...`` and package imports.
    from validate_pattern import validate_pattern
except ImportError:  # pragma: no cover
    from .validate_pattern import validate_pattern


def _appearance(shape: str, diameter_mm: float, pitch_mm: float) -> tuple[str, float, float]:
    if shape not in {"circle", "square"}:
        raise ValueError("Bead shape must be 'circle' or 'square'.")
    if diameter_mm <= 0 or pitch_mm <= 0:
        raise ValueError("Bead diameter and pitch must be positive.")
    if diameter_mm > pitch_mm:
        raise ValueError("Bead diameter cannot exceed bead pitch.")
    return shape, float(diameter_mm), float(pitch_mm)


def _bead_element(*, entry: dict, row: int, column: int, x: float, y: float, pitch: float, diameter: float, shape: str) -> str:
    attributes = f'data-color-id="{escape(entry["id"])}" data-row="{row + 1}" data-column="{column + 1}" fill="{entry["hex"]}"'
    if shape == "circle":
        return f'<circle {attributes} cx="{x + pitch / 2:.3f}" cy="{y + pitch / 2:.3f}" r="{diameter / 2:.3f}"/>'
    inset = (pitch - diameter) / 2
    return f'<rect {attributes} x="{x + inset:.3f}" y="{y + inset:.3f}" width="{diameter:.3f}" height="{diameter:.3f}" rx="0.25"/>'


def _physical_dimensions(canvas_units: float, cell_size: float, pitch_mm: float) -> float:
    return canvas_units * pitch_mm / cell_size


def render_svg(*, grid, palette, output_path, metadata=None, cell_size: int = 12, bead_shape: str = "circle", bead_diameter_mm: float = 5.0, bead_pitch_mm: float = 5.0) -> Path:
    """Render the coordinate construction plan and legend as a standalone SVG.

    The root SVG uses millimetre dimensions, so the bead grid has its declared
    physical size when printed at 100%. The legend intentionally sits outside
    the finished bead area.
    """
    shape, diameter, pitch = _appearance(bead_shape, bead_diameter_mm, bead_pitch_mm)
    if cell_size < 4:
        raise ValueError("Cell size must be at least 4.")
    indices = np.asarray(grid, dtype=np.int16)
    stats = validate_pattern(grid=indices, palette=palette, max_colors=len(palette))
    height, width = indices.shape
    margin_left, margin_top = 42, 42
    legend_x, legend_width = margin_left + width * cell_size + 34, 260
    canvas_width = legend_x + legend_width
    canvas_height = max(margin_top + height * cell_size + 42, 70 + len(palette) * 27 + 55)
    physical_width = _physical_dimensions(canvas_width, cell_size, pitch)
    physical_height = _physical_dimensions(canvas_height, cell_size, pitch)
    finished_width, finished_height = width * pitch, height * pitch
    title = escape(str((metadata or {}).get("title", "Perler Beads Pattern")))
    description = escape(str((metadata or {}).get("description", "Vector bead construction blueprint.")))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{physical_width:.2f}mm" height="{physical_height:.2f}mm" viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-labelledby="title desc" data-grid-width-mm="{finished_width:.2f}" data-grid-height-mm="{finished_height:.2f}" data-bead-diameter-mm="{diameter:.2f}" data-bead-pitch-mm="{pitch:.2f}">',
        f"<title id=\"title\">{title}</title>",
        f"<desc id=\"desc\">{description}. Finished bead area: {finished_width:.2f} by {finished_height:.2f} mm. Grid: {width} by {height}; total beads: {stats['total_beads']}.</desc>",
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<g font-family="Arial, Helvetica, sans-serif" fill="#1F2937">',
        f'<text x="{margin_left}" y="22" font-size="16" font-weight="700">{title}</text>',
        f'<text x="{margin_left}" y="37" font-size="10">{width} × {height} grid · {finished_width:.1f} × {finished_height:.1f} mm · {len(palette)} colours · {stats["total_beads"]} beads</text>',
        '</g>', '<g font-family="Arial, Helvetica, sans-serif" font-size="8" fill="#374151">',
    ]
    for column in range(width):
        lines.append(f'<text x="{margin_left + (column + 0.5) * cell_size:.1f}" y="{margin_top - 8}" text-anchor="middle">{column + 1}</text>')
    for row in range(height):
        lines.append(f'<text x="{margin_left - 8}" y="{margin_top + (row + 0.5) * cell_size + 3:.1f}" text-anchor="end">{row + 1}</text>')
    lines.extend(['</g>', '<g id="beads" stroke="#9CA3AF" stroke-width="0.45">'])
    for row in range(height):
        for column in range(width):
            entry = palette[int(indices[row, column])]
            lines.append(_bead_element(entry=entry, row=row, column=column, x=margin_left + column * cell_size, y=margin_top + row * cell_size, pitch=cell_size, diameter=cell_size * diameter / pitch, shape=shape))
    lines.extend(['</g>', f'<rect x="{margin_left}" y="{margin_top}" width="{width * cell_size}" height="{height * cell_size}" fill="none" stroke="#374151" stroke-width="1"/>', '<g id="legend" font-family="Arial, Helvetica, sans-serif" fill="#111827">', f'<text x="{legend_x}" y="30" font-size="15" font-weight="700">Bead legend</text>'])
    counts = Counter(int(value) for value in indices.ravel())
    for index, entry in enumerate(palette):
        y = 55 + index * 27
        lines.extend([f'<g data-legend-color-id="{escape(entry["id"])}" data-legend-count="{counts.get(index, 0)}">', f'<circle cx="{legend_x + 9}" cy="{y - 4}" r="8" fill="{entry["hex"]}" stroke="#6B7280" stroke-width="0.5"/>', f'<text x="{legend_x + 24}" y="{y}" font-size="11">{escape(entry["id"])} · {escape(entry.get("name", ""))}</text>', f'<text x="{legend_x + 24}" y="{y + 12}" font-size="9" fill="#4B5563">{entry["hex"]} · {counts.get(index, 0)} beads</text>', '</g>'])
    lines.extend([f'<text x="{legend_x}" y="{70 + len(palette) * 27}" font-size="11" font-weight="700">Total: {stats["total_beads"]} beads</text>', '</g>', '</svg>'])
    destination = Path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("\n".join(lines), encoding="utf-8")
    except OSError as error:
        raise OSError(f"Cannot write construction-plan SVG to {destination}. Choose a writable --output path.") from error
    return destination


def render_preview_svg(*, grid, palette, output_path, bead_shape: str = "circle", bead_diameter_mm: float = 5.0, bead_pitch_mm: float = 5.0, background: str = "#FFFFFF") -> Path:
    """Render a clean finished-piece pixel preview without coordinates or legend."""
    shape, diameter, pitch = _appearance(bead_shape, bead_diameter_mm, bead_pitch_mm)
    indices = np.asarray(grid, dtype=np.int16)
    stats = validate_pattern(grid=indices, palette=palette, max_colors=len(palette))
    height, width = indices.shape
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * pitch:.2f}mm" height="{height * pitch:.2f}mm" viewBox="0 0 {width * pitch} {height * pitch}" role="img" aria-label="Perler pixel preview">', f'<rect width="100%" height="100%" fill="{escape(background)}"/>', '<g id="beads" stroke="#9CA3AF" stroke-width="0.08">']
    for row in range(height):
        for column in range(width):
            lines.append(_bead_element(entry=palette[int(indices[row, column])], row=row, column=column, x=column * pitch, y=row * pitch, pitch=pitch, diameter=diameter, shape=shape))
    lines.extend([f'<desc>{stats["total_beads"]} beads; {width} by {height} cells.</desc>', '</g>', '</svg>'])
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


def render_a4_pages(*, grid, palette, output_dir, base_name: str, bead_shape: str = "circle", bead_diameter_mm: float = 5.0, bead_pitch_mm: float = 5.0, orientation: str = "portrait") -> list[Path]:
    """Tile a bead grid into labelled, 100%-scale A4 construction SVG pages."""
    shape, diameter, pitch = _appearance(bead_shape, bead_diameter_mm, bead_pitch_mm)
    if orientation not in {"portrait", "landscape"}:
        raise ValueError("Page orientation must be 'portrait' or 'landscape'.")
    page_width, page_height = (210.0, 297.0) if orientation == "portrait" else (297.0, 210.0)
    margin_x, margin_top, margin_bottom = 12.0, 22.0, 16.0
    cells_x = floor((page_width - 2 * margin_x) / pitch)
    cells_y = floor((page_height - margin_top - margin_bottom) / pitch)
    if cells_x < 1 or cells_y < 1:
        raise ValueError("Bead pitch is too large to fit any cells on A4.")
    indices = np.asarray(grid, dtype=np.int16)
    validate_pattern(grid=indices, palette=palette, max_colors=len(palette))
    height, width = indices.shape
    pages_x, pages_y = ceil(width / cells_x), ceil(height / cells_y)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for page_row in range(pages_y):
        for page_column in range(pages_x):
            start_column, start_row = page_column * cells_x, page_row * cells_y
            end_column, end_row = min(width, start_column + cells_x), min(height, start_row + cells_y)
            tile = indices[start_row:end_row, start_column:end_column]
            tile_height, tile_width = tile.shape
            page_number = page_row * pages_x + page_column + 1
            lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_width:.0f}mm" height="{page_height:.0f}mm" viewBox="0 0 {page_width} {page_height}" role="img" data-page-row="{page_row + 1}" data-page-column="{page_column + 1}">', f'<rect width="100%" height="100%" fill="#FFFFFF"/>', '<g font-family="Arial, Helvetica, sans-serif" fill="#1F2937">', f'<text x="{margin_x}" y="8" font-size="4" font-weight="700">{escape(base_name)} · A4 tile {page_number}/{pages_x * pages_y} ({page_column + 1},{page_row + 1})</text>', f'<text x="{margin_x}" y="14" font-size="2.7">Global columns {start_column + 1}–{end_column}; rows {start_row + 1}–{end_row} · print at 100%</text>', '</g>', '<g font-family="Arial, Helvetica, sans-serif" font-size="2" fill="#374151">']
            for column in range(tile_width):
                lines.append(f'<text x="{margin_x + (column + 0.5) * pitch:.2f}" y="{margin_top - 3}" text-anchor="middle">{start_column + column + 1}</text>')
            for row in range(tile_height):
                lines.append(f'<text x="{margin_x - 2}" y="{margin_top + (row + 0.5) * pitch + 0.7:.2f}" text-anchor="end">{start_row + row + 1}</text>')
            lines.extend(['</g>', '<g id="beads" stroke="#9CA3AF" stroke-width="0.12">'])
            for row in range(tile_height):
                for column in range(tile_width):
                    lines.append(_bead_element(entry=palette[int(tile[row, column])], row=start_row + row, column=start_column + column, x=margin_x + column * pitch, y=margin_top + row * pitch, pitch=pitch, diameter=diameter, shape=shape))
            lines.extend(['</g>', f'<rect x="{margin_x}" y="{margin_top}" width="{tile_width * pitch}" height="{tile_height * pitch}" fill="none" stroke="#111827" stroke-width="0.25" stroke-dasharray="1 0.7"/>', f'<text x="{margin_x}" y="{page_height - 7}" font-family="Arial, Helvetica, sans-serif" font-size="2.8" fill="#374151">Tile edges: align with adjacent pages; finished grid is {width * pitch:.1f} × {height * pitch:.1f} mm.</text>', '</svg>'])
            output = destination / f"{base_name}_page_{page_row + 1:02d}_{page_column + 1:02d}.svg"
            output.write_text("\n".join(lines), encoding="utf-8")
            outputs.append(output)
    return outputs
