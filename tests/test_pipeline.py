"""Small end-to-end checks for the image-to-pattern pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cleanup import cleanup_grid
from image_to_pattern import choose_grid_size, crop_to_aspect, mode_settings, quantize_to_grid
from palette import build_shopping_list, load_builtin_palette, nearest_palette_indices, write_shopping_list
from svg_renderer import render_a4_pages, render_preview_svg, render_svg
from validate_pattern import validate_pattern, validate_svg


def test_cleanup_removes_an_isolated_interior_cell():
    grid = np.zeros((5, 5), dtype=np.int16)
    grid[2, 2] = 1
    assert cleanup_grid(grid)[2, 2] == 0


def test_auto_size_preserves_subject_orientation():
    assert choose_grid_size(200, 100, base_width=56, base_height=56, auto_size=True) == (112, 56)
    width, height = choose_grid_size(100, 200, base_width=56, base_height=56, auto_size=True)
    assert height > width


def test_pipeline_renders_vector_cells(tmp_path):
    image = Image.new("RGB", (120, 100), "white")
    drawing = ImageDraw.Draw(image)
    drawing.ellipse((35, 15, 85, 85), fill="#D97706")
    drawing.rectangle((50, 65, 70, 92), fill="#1D4ED8")
    prepared = crop_to_aspect(image, target_width=24, target_height=24, use_subject=True)
    grid, palette = quantize_to_grid(prepared, width=24, height=24, max_colours=6, palette=None)
    stats = validate_pattern(grid=grid, palette=palette, max_colors=6)
    output = tmp_path / "pattern.svg"
    render_svg(grid=grid, palette=palette, output_path=output)
    validate_svg(output, expected_total=576)
    root = ET.parse(output).getroot()
    assert len(root.findall(".//{http://www.w3.org/2000/svg}circle")) >= stats["total_beads"]


def test_preview_and_a4_pages_include_build_metadata(tmp_path):
    grid = np.array([[0, 1, 0], [1, 0, 1]], dtype=np.int16)
    palette = [
        {"id": "C01", "name": "Light", "hex": "#FFFFFF"},
        {"id": "C02", "name": "Dark", "hex": "#111111"},
    ]
    preview = tmp_path / "preview.svg"
    render_preview_svg(grid=grid, palette=palette, output_path=preview, bead_shape="square", bead_diameter_mm=4.8, bead_pitch_mm=5)
    validate_svg(preview, expected_total=6)
    pages = render_a4_pages(grid=grid, palette=palette, output_dir=tmp_path / "pages", base_name="sample", bead_shape="square", bead_diameter_mm=4.8, bead_pitch_mm=5)
    assert len(pages) == 1
    page = pages[0].read_text(encoding="utf-8")
    assert 'width="210mm"' in page
    assert 'data-page-row="1"' in page


def test_brand_palette_inventory_priority_and_shopping_list(tmp_path):
    hama = load_builtin_palette("hama-midi-official")
    assert {entry["id"] for entry in hama} >= {"01", "18", "28"}
    palette = [
        {"id": "A", "name": "Near red", "hex": "#F00000"},
        {"id": "B", "name": "Owned orange-red", "hex": "#F52010"},
    ]
    colour = np.array([[[244, 10, 5]]], dtype=np.uint8)
    preferred = nearest_palette_indices(colour, palette, metric="lab", inventory={"B": 3}, inventory_bias=1)
    assert int(preferred[0, 0]) == 1
    rows = build_shopping_list(np.array([[0, 1, 1]], dtype=np.int16), palette, {"A": 1, "B": 1})
    assert rows[0]["to_buy"] == 0 and rows[1]["to_buy"] == 1
    output = write_shopping_list(rows, tmp_path / "shopping.csv")
    assert "to_buy" in output.read_text(encoding="utf-8")


def test_image_modes_protect_edges_and_logo_skips_cleanup():
    portrait = mode_settings("portrait")
    logo = mode_settings("logo")
    landscape = mode_settings("landscape")
    assert portrait.prefer_face and portrait.edge_protection > 0
    assert logo.cleanup_passes == 0 and logo.resample == Image.Resampling.NEAREST
    assert landscape.max_colours < 20 and landscape.min_component_size > portrait.min_component_size
    grid = np.zeros((5, 5), dtype=np.int16)
    grid[2, 2] = 1
    protected = np.zeros((5, 5), dtype=bool)
    protected[2, 2] = True
    assert cleanup_grid(grid, min_component_size=3, passes=1, protected_mask=protected)[2, 2] == 1
    assert cleanup_grid(grid, min_component_size=1, passes=0)[2, 2] == 1
