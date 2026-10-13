"""Image-to-pattern pipeline modules for perler-svg-pattern.

Modules:
- ``image_to_pattern``: CLI orchestration and conversion pipeline.
- ``palette``: verified palette loading, colour distance, inventory, shopping lists.
- ``cleanup``: grid cleanup utilities for physically buildable patterns.
- ``svg_renderer``: standalone SVG, preview, and A4 tile renderers.
- ``validate_pattern``: grid and SVG artifact validation.
- ``report``: machine-readable conversion report generation.
"""

from __future__ import annotations

__all__ = [
    "image_to_pattern",
    "palette",
    "cleanup",
    "svg_renderer",
    "validate_pattern",
    "report",
]