"""perler_svg_pattern: convert images into validated Perler Beads SVG patterns.

Public surface:
- ``perler_svg_pattern.mcp_server``: the MCP server (stdio transport).
- ``perler_svg_pattern.scripts.image_to_pattern``: the CLI entry point.
- ``perler_svg_pattern.scripts.palette``: palette / inventory / shopping-list tools.
- ``perler_svg_pattern.scripts.cleanup``: grid cleanup utilities.
- ``perler_svg_pattern.scripts.svg_renderer``: SVG, preview, and A4 tile renderers.
- ``perler_svg_pattern.scripts.validate_pattern``: grid and SVG artifact validation.
- ``perler_svg_pattern.scripts.report``: JSON conversion report writer.
"""

from __future__ import annotations

__version__ = "0.2.1"

__all__ = ["__version__"]