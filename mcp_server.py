"""MCP entry point for generating verified Perler bead SVG patterns.

The server is intentionally a thin integration layer.  The image-processing
pipeline remains in ``scripts/`` so the CLI and MCP tools generate identical,
validated artifacts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

from scripts.image_to_pattern import build_parser, run_conversion
from scripts.palette import PALETTE_DIR, builtin_palette_names, load_builtin_palette
from scripts.validate_pattern import validate_svg


mcp = MCPServer(
    name="perler-svg-pattern",
    title="Perler SVG Pattern",
    description="柯影数智团队：将现有图片转换为经过校验、可购买配色的拼豆 SVG 施工图。",
    instructions=(
        "Use convert_image for a complete pattern conversion. Source images stay in place; "
        "the caller explicitly selects an output directory. Use list_brand_palettes or "
        "get_brand_palette before requesting a physical palette, and validate_svg_artifact "
        "to independently audit an SVG created by this server."
    ),
    version="0.2.0",
)


def _existing_file(value: str, *, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} not found: {path}. Provide an existing file path.")
    return path


def _output_file(output_dir: str, filename: str) -> Path:
    directory = Path(output_dir).expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise ValueError(f"Output directory is not a directory: {directory}.")
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OSError(f"Cannot create output directory {directory}. Choose a writable directory.") from error
    if not os.access(directory, os.W_OK):
        raise PermissionError(f"Output directory is not writable: {directory}. Choose a writable directory.")
    name = Path(filename)
    if name.name != filename or filename in {"", ".", ".."}:
        raise ValueError("filename must be a bare file name, not a path.")
    if name.suffix.lower() != ".svg":
        raise ValueError("filename must end in .svg.")
    return directory / name


def _palette_document(name: str) -> dict:
    if name not in builtin_palette_names():
        raise ValueError(f"Unknown brand palette {name!r}. Use list_brand_palettes to see available names.")
    return json.loads((PALETTE_DIR / f"{name}.json").read_text(encoding="utf-8"))


@mcp.tool()
def list_brand_palettes() -> list[dict]:
    """List the shipped, source-documented physical bead palettes."""
    result = []
    for name in builtin_palette_names():
        document = _palette_document(name)
        result.append({
            "name": name,
            "brand": document.get("brand"),
            "series": document.get("series"),
            "color_count": len(document.get("colors", [])),
            "source": document.get("source", {}),
        })
    return result


@mcp.tool()
def get_brand_palette(name: str) -> dict:
    """Return every purchase-ready colour in one built-in Perler, Hama, or Artkal palette."""
    document = _palette_document(name)
    return {
        "name": name,
        "brand": document.get("brand"),
        "series": document.get("series"),
        "source": document.get("source", {}),
        "colors": load_builtin_palette(name),
    }


@mcp.tool()
def convert_image(
    input_path: str,
    output_dir: str,
    filename: str | None = None,
    mode: Literal["auto", "portrait", "pet", "logo", "landscape", "illustration", "art"] = "auto",
    width: int = 56,
    height: int = 56,
    auto_size: bool = False,
    max_colors: int = 20,
    brand: str | None = None,
    palette_path: str | None = None,
    color_distance: Literal["lab", "rgb"] = "lab",
    inventory: str | None = None,
    inventory_only: bool = False,
    remove_background: bool = False,
    background_color: str = "#FFFFFF",
    bead_shape: Literal["circle", "square"] = "circle",
    bead_size_mm: float = 5.0,
    preview: bool = False,
    a4_pages: bool = False,
    shopping_format: Literal["csv", "json"] = "csv",
) -> dict:
    """Convert an existing image to SVG plus shopping list and JSON report.

    ``filename`` is an SVG file name only (not a path); all output artifacts are
    placed under ``output_dir``.  Set ``brand`` to a name returned by
    ``list_brand_palettes`` to match purchasable beads strictly, or pass a
    verified JSON/CSV ``palette_path``.  The returned report is concise; the
    on-disk JSON artifact retains the complete grid manifest.
    """
    source = _existing_file(input_path, label="Input image")
    output_name = filename or f"{source.stem}_perler.svg"
    output = _output_file(output_dir, output_name)
    if brand and palette_path:
        raise ValueError("Specify either brand or palette_path, not both.")
    if palette_path:
        _existing_file(palette_path, label="Palette file")

    shopping_path = output.with_name(f"{output.stem}_shopping.{shopping_format}")
    report_path = output.with_name(f"{output.stem}_report.json")
    arguments = [
        "--input", str(source), "--output", str(output),
        "--width", str(width), "--height", str(height),
        "--mode", mode, "--max-colors", str(max_colors),
        "--color-distance", color_distance,
        "--background-color", background_color,
        "--bead-shape", bead_shape, "--bead-size-mm", str(bead_size_mm),
        "--shopping-list", str(shopping_path), "--report", str(report_path),
    ]
    if auto_size:
        arguments.append("--auto-size")
    if brand:
        arguments.extend(("--brand", brand))
    if palette_path:
        arguments.extend(("--palette", str(Path(palette_path).expanduser().resolve())))
    if inventory:
        arguments.extend(("--inventory", inventory))
    if inventory_only:
        arguments.append("--inventory-only")
    if remove_background:
        arguments.append("--remove-background")
    if preview:
        arguments.append("--preview")
    if a4_pages:
        arguments.append("--a4-pages")

    report = run_conversion(build_parser().parse_args(arguments), emit=None)
    pattern = report["pattern"]
    return {
        "status": "ok",
        "artifacts": report["artifacts"],
        "processing": report["processing"],
        "pattern": {
            "grid_size": pattern["grid_size"],
            "physical_size_mm": pattern["physical_size_mm"],
            "total_beads": pattern["total_beads"],
            "colour_counts": pattern["colour_counts"],
            "palette": pattern["palette"],
        },
    }


@mcp.tool()
def validate_svg_artifact(svg_path: str) -> dict:
    """Audit a generated SVG for vector-only, opaque bead cells and basic counts."""
    return validate_svg(_existing_file(svg_path, label="SVG artifact"))


def main() -> None:
    """Serve MCP over stdio (the transport expected by desktop MCP clients)."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
