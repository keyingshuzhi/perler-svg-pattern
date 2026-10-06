"""End-to-end tests for the public MCP interface."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp import Client

from mcp_server import mcp


FIXTURES = Path(__file__).parent / "fixtures"


def _structured(result):
    """Read either a v2 structured result or the JSON text MCP content item."""
    if result.structured_content is not None:
        return result.structured_content["result"]
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


def test_mcp_exposes_discoverable_tools_and_palettes():
    async def exercise() -> None:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "list_brand_palettes",
                "get_brand_palette",
                "convert_image",
                "validate_svg_artifact",
            }
            result = await client.call_tool("list_brand_palettes", {})
            palettes = _structured(result)
            assert {palette["name"] for palette in palettes} >= {
                "perler-midi-open-stock-2025",
                "hama-midi-official",
                "artkal-s-midi-official",
            }

    asyncio.run(exercise())


def test_mcp_converts_and_validates_an_artifact(tmp_path):
    async def exercise() -> None:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "convert_image",
                {
                    "input_path": str(FIXTURES / "few_colours.ppm"),
                    "output_dir": str(tmp_path),
                    "filename": "mcp-pattern.svg",
                    "mode": "logo",
                    "width": 24,
                    "height": 24,
                    "max_colors": 6,
                    "bead_shape": "square",
                    "preview": True,
                    "shopping_format": "json",
                },
            )
            manifest = _structured(result)
            assert manifest["status"] == "ok"
            assert manifest["pattern"]["total_beads"] == 576
            assert Path(manifest["artifacts"]["construction_plan"]).is_file()
            assert Path(manifest["artifacts"]["shopping_list"]).suffix == ".json"
            validation = await client.call_tool(
                "validate_svg_artifact",
                {"svg_path": manifest["artifacts"]["construction_plan"]},
            )
            assert _structured(validation)["cell_count"] == 576

    asyncio.run(exercise())
