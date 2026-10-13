"""Run the perler-svg-pattern MCP server as a module.

Usage::

    python -m perler_svg_pattern
    uvx perler-svg-pattern
"""

from __future__ import annotations

from perler_svg_pattern.mcp_server import main


if __name__ == "__main__":
    main()