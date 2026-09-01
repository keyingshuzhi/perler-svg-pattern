"""Validation helpers for Perler pattern data and standalone SVG artifacts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import numpy as np

try:  # Support both ``python scripts/...`` and package imports.
    from palette import hex_to_rgb, rgb_to_hex
except ImportError:  # pragma: no cover
    from .palette import hex_to_rgb, rgb_to_hex


SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SVG = f"{{{SVG_NAMESPACE}}}"
FORBIDDEN_TAGS = {"image", "linearGradient", "radialGradient", "filter", "mask", "pattern"}
OPACITY_RE = re.compile(r"(?:^|;)\s*(?:fill-|stroke-)?opacity\s*:\s*([0-9.]+)", re.IGNORECASE)


def validate_pattern(*, grid, palette, max_colors: int = 20) -> dict:
    """Validate grid geometry, palette references, colour limit, and bead counts."""
    indices = np.asarray(grid)
    if indices.ndim != 2 or not indices.size:
        raise ValueError("Pattern grid must be a non-empty two-dimensional array.")
    if not np.issubdtype(indices.dtype, np.integer):
        raise ValueError("Pattern grid must contain integer palette indices.")
    if not palette:
        raise ValueError("Pattern palette must contain at least one colour.")
    if len(palette) > max_colors:
        raise ValueError(f"Palette has {len(palette)} colours; maximum is {max_colors}.")
    used = set(int(value) for value in np.unique(indices))
    if not used.issubset(set(range(len(palette)))):
        raise ValueError("Grid contains an index absent from the palette.")
    ids = [entry.get("id") for entry in palette]
    hex_values = []
    for entry in palette:
        if not entry.get("id") or not entry.get("name") or not entry.get("hex"):
            raise ValueError("Every palette entry needs id, name, and hex.")
        hex_values.append(rgb_to_hex(hex_to_rgb(entry["hex"])))
    if len(ids) != len(set(ids)) or len(hex_values) != len(set(hex_values)):
        raise ValueError("Palette must use unique IDs and colours.")
    counts = Counter(int(value) for value in indices.ravel())
    return {"width": int(indices.shape[1]), "height": int(indices.shape[0]), "total_beads": int(indices.size), "colour_counts": {palette[index]["id"]: counts.get(index, 0) for index in range(len(palette))}}


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _ensure_opaque_vector_svg(root: ET.Element) -> None:
    for element in root.iter():
        name = _local_name(element)
        if name in FORBIDDEN_TAGS:
            raise ValueError(f"SVG uses forbidden {name} element; pattern must be standalone opaque vectors.")
        for attribute in ("opacity", "fill-opacity", "stroke-opacity"):
            if attribute in element.attrib and float(element.attrib[attribute]) < 1:
                raise ValueError("SVG contains transparency; Perler pattern cells must be opaque.")
        style = element.attrib.get("style", "")
        for match in OPACITY_RE.finditer(style):
            if float(match.group(1)) < 1:
                raise ValueError("SVG style contains transparency; Perler pattern cells must be opaque.")
        if "url(" in element.attrib.get("fill", "").lower() or "url(" in element.attrib.get("stroke", "").lower():
            raise ValueError("SVG uses a paint-server reference; gradients and patterns are not allowed.")


def validate_svg(path: str | Path, *, expected_total: int | None = None, grid: np.ndarray | None = None, palette: list[dict] | None = None, require_legend: bool = False) -> dict:
    """Validate SVG vector cells, safety constraints, grid geometry, and legend.

    Supplying ``grid`` and ``palette`` turns this into a full artifact audit: each
    cell's coordinate, colour ID, fill, total count, and legend count must match.
    """
    root = ET.parse(path).getroot()
    if root.tag != f"{SVG}svg":
        raise ValueError("Artifact root must be an SVG document.")
    _ensure_opaque_vector_svg(root)
    cells = [element for element in root.iter() if _local_name(element) in {"circle", "rect"} and "data-color-id" in element.attrib]
    if not cells:
        raise ValueError("SVG does not contain vector bead cells.")
    if expected_total is not None and len(cells) != expected_total:
        raise ValueError(f"SVG contains {len(cells)} cells; expected {expected_total}.")

    result = {"cell_count": len(cells), "legend_count": 0}
    if grid is None or palette is None:
        return result
    stats = validate_pattern(grid=grid, palette=palette, max_colors=len(palette))
    if len(cells) != stats["total_beads"]:
        raise ValueError("SVG bead-cell count does not match the pattern grid.")
    expected_by_coordinate = {
        (row + 1, column + 1): palette[int(grid[row, column])]
        for row in range(grid.shape[0])
        for column in range(grid.shape[1])
    }
    observed_coordinates: set[tuple[int, int]] = set()
    observed_counts: Counter[str] = Counter()
    for cell in cells:
        try:
            coordinate = (int(cell.attrib["data-row"]), int(cell.attrib["data-column"]))
        except (KeyError, ValueError) as error:
            raise ValueError("Every bead cell must expose integer data-row and data-column coordinates.") from error
        if coordinate in observed_coordinates or coordinate not in expected_by_coordinate:
            raise ValueError("SVG bead coordinates are duplicated or outside the expected grid.")
        observed_coordinates.add(coordinate)
        expected = expected_by_coordinate[coordinate]
        if cell.attrib["data-color-id"] != expected["id"]:
            raise ValueError(f"Cell {coordinate} has a colour ID inconsistent with the grid.")
        if rgb_to_hex(hex_to_rgb(cell.attrib.get("fill", ""))) != rgb_to_hex(hex_to_rgb(expected["hex"])):
            raise ValueError(f"Cell {coordinate} fill does not match its palette HEX value.")
        observed_counts[expected["id"]] += 1
    if observed_coordinates != set(expected_by_coordinate):
        raise ValueError("SVG does not cover every expected grid coordinate exactly once.")
    if dict(observed_counts) != {colour_id: count for colour_id, count in stats["colour_counts"].items() if count}:
        raise ValueError("SVG per-colour bead counts do not match the pattern grid.")

    legends = [element for element in root.iter() if "data-legend-color-id" in element.attrib]
    if require_legend and not legends:
        raise ValueError("Construction-plan SVG is missing its colour legend.")
    if legends:
        if len(legends) != len(palette):
            raise ValueError("SVG legend does not contain exactly one entry per palette colour.")
        for legend in legends:
            colour_id = legend.attrib["data-legend-color-id"]
            if colour_id not in stats["colour_counts"]:
                raise ValueError("SVG legend references an unknown colour ID.")
            if int(legend.attrib.get("data-legend-count", "-1")) != stats["colour_counts"][colour_id]:
                raise ValueError("SVG legend count does not match the pattern grid.")
        if {legend.attrib["data-legend-color-id"] for legend in legends} != set(stats["colour_counts"]):
            raise ValueError("SVG legend IDs do not match the palette.")
    result["legend_count"] = len(legends)
    return result
