"""Artifact validation, acceptance fixtures, end-to-end, and visual-regression tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cleanup import cleanup_grid
from image_to_pattern import crop_to_aspect, detect_face_bbox, detect_subject_bbox, edge_protection_mask, load_image, mode_settings, quantize_to_grid
from palette import compact_palette
from svg_renderer import render_svg
from validate_pattern import validate_svg


FIXTURES = Path(__file__).parent / "fixtures"
BASELINES = json.loads((FIXTURES / "regression_baselines.json").read_text(encoding="utf-8"))["cases"]


def _pattern_for_fixture(filename: str, mode: str) -> tuple[np.ndarray, list[dict]]:
    """Exercise the same mode-specific image pipeline used by the CLI."""
    settings = mode_settings(mode)
    source = load_image(FIXTURES / filename)
    use_subject_crop = settings.use_subject_crop
    bbox = (detect_face_bbox(source) or detect_subject_bbox(source)) if settings.prefer_face else (detect_subject_bbox(source) if use_subject_crop else (0, 0, source.width, source.height))
    prepared = crop_to_aspect(source, target_width=24, target_height=24, use_subject=use_subject_crop, subject_bbox=bbox, resample=settings.resample)
    edge_mask = edge_protection_mask(prepared, width=24, height=24, strength=settings.edge_protection, resample=settings.resample)
    grid, palette = quantize_to_grid(prepared, width=24, height=24, max_colours=settings.max_colours, palette=None, resample=settings.resample)
    grid = cleanup_grid(grid, min_component_size=settings.min_component_size, passes=settings.cleanup_passes, protected_mask=edge_mask)
    return compact_palette(grid, palette)


@pytest.mark.parametrize(("filename", "mode"), [
    ("horizontal.ppm", "landscape"),
    ("vertical.ppm", "portrait"),
    ("few_colours.ppm", "logo"),
    ("no_subject.ppm", "auto"),
])
def test_reference_fixtures_have_valid_grid_and_svg(filename, mode, tmp_path):
    grid, palette = _pattern_for_fixture(filename, mode)
    output = tmp_path / f"{Path(filename).stem}-{mode}.svg"
    render_svg(grid=grid, palette=palette, output_path=output)
    audit = validate_svg(output, grid=grid, palette=palette, require_legend=True)
    assert audit["cell_count"] == 24 * 24
    assert audit["legend_count"] == len(palette)


def test_transparent_png_end_to_end(tmp_path):
    source = tmp_path / "transparent.png"
    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    drawing = ImageDraw.Draw(image)
    drawing.ellipse((20, 10, 76, 66), fill=(218, 119, 6, 255))
    drawing.rectangle((35, 58, 61, 90), fill=(29, 78, 216, 255))
    image.save(source)
    output = tmp_path / "transparent.svg"
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "image_to_pattern.py"), "--input", str(source), "--output", str(output), "--width", "24", "--height", "24", "--mode", "portrait", "--preview"]
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    assert "Generated construction plan" in completed.stdout
    assert output.is_file() and output.with_name("transparent_preview.svg").is_file()
    assert output.with_name("transparent_shopping.csv").is_file()
    report = json.loads(output.with_name("transparent_report.json").read_text(encoding="utf-8"))
    assert report["input"]["original_size_px"] == {"width": 96, "height": 96}
    assert report["processing"]["cleanup"]["beads_before"] == report["processing"]["cleanup"]["beads_after"] == 576
    assert report["pattern"]["total_beads"] == 576
    validate_svg(output, expected_total=576)


def test_cli_art_alias_bead_size_and_json_shopping_list(tmp_path):
    output = tmp_path / "art.svg"
    shopping = tmp_path / "shopping.json"
    report_path = tmp_path / "conversion.json"
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "image_to_pattern.py"), "--input", str(FIXTURES / "few_colours.ppm"), "--output", str(output), "--width", "24", "--height", "24", "--mode", "art", "--bead-size-mm", "5", "--shopping-list", str(shopping), "--report", str(report_path)]
    subprocess.run(command, text=True, capture_output=True, check=True)
    assert isinstance(json.loads(shopping.read_text(encoding="utf-8")), list)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["processing"]["mode"] == "art"
    assert report["pattern"]["physical_size_mm"]["width"] == 120


def test_cli_reports_actionable_small_image_and_bad_palette_errors(tmp_path):
    tiny = tmp_path / "tiny.png"
    Image.new("RGB", (1, 1), "white").save(tiny)
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "image_to_pattern.py"), "--input", str(tiny), "--output", str(tmp_path / "tiny.svg")]
    completed = subprocess.run(command, text=True, capture_output=True)
    assert completed.returncode != 0 and "at least 2x2" in completed.stderr
    bad_palette = tmp_path / "bad.json"
    bad_palette.write_text("{ broken", encoding="utf-8")
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "image_to_pattern.py"), "--input", str(FIXTURES / "few_colours.ppm"), "--output", str(tmp_path / "bad.svg"), "--palette", str(bad_palette)]
    completed = subprocess.run(command, text=True, capture_output=True)
    assert completed.returncode != 0 and "Palette JSON is invalid" in completed.stderr


def test_validator_rejects_non_vector_or_transparent_svg(tmp_path):
    image_svg = tmp_path / "embedded-image.svg"
    image_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,AA=="/></svg>', encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden image"):
        validate_svg(image_svg)
    transparent_svg = tmp_path / "transparent.svg"
    transparent_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle data-color-id="C01" data-row="1" data-column="1" fill="#000000" opacity="0.5"/></svg>', encoding="utf-8")
    with pytest.raises(ValueError, match="transparency"):
        validate_svg(transparent_svg)
    gradient_svg = tmp_path / "gradient.svg"
    gradient_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="g"/></defs><circle data-color-id="C01" data-row="1" data-column="1" fill="url(#g)"/></svg>', encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden linearGradient"):
        validate_svg(gradient_svg)


def test_validator_detects_legend_count_mismatch(tmp_path):
    grid = np.array([[0, 1]], dtype=np.int16)
    palette = [{"id": "C01", "name": "Light", "hex": "#FFFFFF"}, {"id": "C02", "name": "Dark", "hex": "#111111"}]
    output = tmp_path / "plan.svg"
    render_svg(grid=grid, palette=palette, output_path=output)
    corrupted = output.read_text(encoding="utf-8").replace('data-legend-count="1"', 'data-legend-count="99"', 1)
    output.write_text(corrupted, encoding="utf-8")
    with pytest.raises(ValueError, match="legend count"):
        validate_svg(output, grid=grid, palette=palette, require_legend=True)


def test_visual_regression_grid_and_palette_are_stable():
    for case_name, baseline in BASELINES.items():
        grid, palette = _pattern_for_fixture(baseline["input"], baseline["mode"])
        grid_hash = hashlib.sha256(np.asarray(grid, dtype=np.int16).tobytes()).hexdigest()
        assert grid_hash == baseline["grid_sha256"], f"{case_name}: grid changed; visually review before updating baseline."
        assert palette == baseline["palette"], f"{case_name}: palette changed; visually review before updating baseline."
