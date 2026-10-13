#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "perler-svg-pattern>=0.2.1",
# ]
# ///
"""Run the perler-svg-pattern MCP server with uvx.

This is a PEP 723 inline-metadata script.  Install uv and run::

    uvx perler-svg-pattern

Or point uvx at this file directly::

    uvx --from perler-svg-pattern perler-svg-pattern
    uv run uvx-perler-svg-pattern.py

The script boots the same stdio MCP server shipped in the package, so any
MCP client that can launch a stdio command can use it without a pre-installed
virtual environment.
"""

from __future__ import annotations

from perler_svg_pattern.mcp_server import main


if __name__ == "__main__":
    main()