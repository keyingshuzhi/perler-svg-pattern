"""Verified palette loading, colour distance, inventory, and shopping-list tools."""

from __future__ import annotations

from collections import Counter
import csv
import json
import re
from pathlib import Path

import numpy as np


HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
PALETTE_DIR = Path(__file__).resolve().parents[1] / "assets" / "palettes"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert a six-digit HEX colour to an RGB tuple."""
    if not isinstance(value, str) or not HEX_RE.fullmatch(value):
        raise ValueError(f"Invalid HEX colour: {value!r}")
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def rgb_to_hex(rgb: np.ndarray | tuple[int, int, int] | list[int]) -> str:
    red, green, blue = (int(channel) for channel in rgb)
    return f"#{red:02X}{green:02X}{blue:02X}"


def _normalise_entry(entry: dict, index: int, *, brand: str | None = None, series: str | None = None) -> dict:
    colour = entry.get("hex") or entry.get("color") or entry.get("colour")
    if colour is None:
        raise ValueError(f"Palette entry {index} is missing a hex field.")
    result = {
        "id": str(entry.get("id") or f"C{index:02d}"),
        "name": str(entry.get("name") or entry.get("id") or f"Colour {index}"),
        "hex": rgb_to_hex(hex_to_rgb(str(colour))),
    }
    if entry.get("brand") or brand:
        result["brand"] = str(entry.get("brand") or brand)
    if entry.get("series") or series:
        result["series"] = str(entry.get("series") or series)
    return result


def _load_entries(path: Path) -> tuple[list[dict], dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Palette file not found: {path}")
    document: dict = {}
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Palette JSON is invalid: {path}. Expected a JSON array or an object with a 'colors' array.") from error
        entries = payload.get("colors", payload) if isinstance(payload, dict) else payload
        document = payload if isinstance(payload, dict) else {}
    elif path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not {"hex", "color", "colour"}.intersection(reader.fieldnames):
                raise ValueError(f"Palette CSV is missing a hex column: {path}. Expected columns: id,name,hex.")
            entries = list(reader)
    else:
        raise ValueError("Palette must be a JSON or CSV file.")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Palette must contain at least one colour entry.")
    result = [_normalise_entry(entry, index, brand=document.get("brand"), series=document.get("series")) for index, entry in enumerate(entries, start=1)]
    if len({entry["id"] for entry in result}) != len(result):
        raise ValueError("Palette colour IDs must be unique.")
    return result, document


def load_palette(path: str | None = None) -> list[dict] | None:
    """Load an external JSON/CSV palette, or use adaptive colours when omitted."""
    if path is None:
        return None
    return _load_entries(Path(path).expanduser().resolve())[0]


def builtin_palette_names() -> tuple[str, ...]:
    """Return shipped palette keys without claiming unshipped brand completeness."""
    return tuple(sorted(path.stem for path in PALETTE_DIR.glob("*.json") if path.name != "README.json"))


def load_builtin_palette(name: str) -> list[dict]:
    """Load one of the maintained, source-documented physical bead palettes."""
    if name not in builtin_palette_names():
        choices = ", ".join(builtin_palette_names()) or "none"
        raise ValueError(f"Unknown built-in palette {name!r}. Available: {choices}.")
    return _load_entries(PALETTE_DIR / f"{name}.json")[0]


def adaptive_palette(colours: np.ndarray) -> list[dict]:
    return [{"id": f"C{index:02d}", "name": f"Colour {index}", "hex": rgb_to_hex(colour)} for index, colour in enumerate(colours, start=1)]


def palette_rgb(palette: list[dict]) -> np.ndarray:
    return np.asarray([hex_to_rgb(entry["hex"]) for entry in palette], dtype=np.uint8)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert sRGB to CIE Lab using D65 white; supports arbitrary leading axes."""
    values = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)
    matrix = np.array(((0.4124564, 0.3575761, 0.1804375), (0.2126729, 0.7151522, 0.0721750), (0.0193339, 0.1191920, 0.9503041)))
    xyz = linear @ matrix.T / np.array((0.95047, 1.0, 1.08883))
    epsilon, kappa = 216 / 24389, 24389 / 27
    transformed = np.where(xyz > epsilon, np.cbrt(xyz), (kappa * xyz + 16) / 116)
    return np.stack((116 * transformed[..., 1] - 16, 500 * (transformed[..., 0] - transformed[..., 1]), 200 * (transformed[..., 1] - transformed[..., 2])), axis=-1)


def colour_distances(rgb: np.ndarray, palette: list[dict], *, metric: str = "lab") -> np.ndarray:
    """Return RGB Euclidean or CIE76 Delta E distances to every palette colour."""
    if metric not in {"rgb", "lab"}:
        raise ValueError("Colour distance metric must be 'rgb' or 'lab'.")
    source = np.asarray(rgb, dtype=np.float64)
    candidates = palette_rgb(palette).astype(np.float64)
    if metric == "lab":
        source, candidates = rgb_to_lab(source), rgb_to_lab(candidates)
    return np.linalg.norm(source[..., None, :] - candidates, axis=-1)


def nearest_palette_indices(rgb: np.ndarray, palette: list[dict], *, metric: str = "lab", inventory: dict[str, int | None] | None = None, inventory_bias: float = 0.12, inventory_only: bool = False) -> np.ndarray:
    """Match colours to purchase-ready swatches, optionally preferring owned IDs.

    With an inventory, a stocked colour may win when it is close enough to the
    global best match. ``inventory_only`` makes the palette a strict subset.
    """
    if not 0 <= inventory_bias <= 1:
        raise ValueError("Inventory bias must be between 0 and 1.")
    distances = colour_distances(rgb, palette, metric=metric)
    inventory_ids = set((inventory or {}).keys())
    stocked = np.array([index for index, entry in enumerate(palette) if entry["id"] in inventory_ids], dtype=np.int16)
    if inventory_only:
        if not len(stocked):
            raise ValueError("Inventory-only matching requires at least one inventory ID in the selected palette.")
        subset = distances[..., stocked]
        return stocked[subset.argmin(axis=-1)].astype(np.int16)
    result = distances.argmin(axis=-1).astype(np.int16)
    if len(stocked) and inventory_bias:
        stocked_distances = distances[..., stocked]
        stock_choice = stocked[stocked_distances.argmin(axis=-1)]
        stock_distance = stocked_distances.min(axis=-1)
        best_distance = distances.min(axis=-1)
        absolute_allowance = 2.0 if metric == "lab" else 8.0
        prefer_stock = stock_distance <= best_distance * (1 + inventory_bias) + absolute_allowance * inventory_bias
        result = np.where(prefer_stock, stock_choice, result).astype(np.int16)
    return result


def load_inventory(value: str | None) -> dict[str, int | None]:
    """Load owned IDs from CSV/JSON or a compact ``ID[:quantity],...`` string."""
    if not value:
        return {}
    path = Path(value).expanduser()
    entries: list[dict] = []
    if path.is_file():
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and "colors" not in payload:
                entries = [{"id": identifier, "quantity": quantity} for identifier, quantity in payload.items()]
            else:
                entries = payload.get("colors", payload) if isinstance(payload, dict) else payload
        elif path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8-sig") as handle:
                entries = list(csv.DictReader(handle))
        else:
            raise ValueError("Inventory file must be JSON or CSV.")
    else:
        for token in value.split(","):
            identifier, separator, quantity = token.strip().partition(":")
            entries.append({"id": identifier, "quantity": quantity if separator else None})
    result: dict[str, int | None] = {}
    for entry in entries:
        identifier = str(entry.get("id", "")).strip()
        if not identifier:
            raise ValueError("Every inventory entry needs an id.")
        quantity = entry.get("quantity", entry.get("count"))
        if quantity in (None, ""):
            result[identifier] = None
        else:
            parsed = int(quantity)
            if parsed < 0:
                raise ValueError("Inventory quantities cannot be negative.")
            result[identifier] = parsed
    return result


def build_shopping_list(grid: np.ndarray, palette: list[dict], inventory: dict[str, int | None] | None = None) -> list[dict]:
    """Build order-ready rows with required, owned, and remaining bead counts."""
    counts = Counter(int(value) for value in np.asarray(grid).ravel())
    stock = inventory or {}
    rows = []
    for index, entry in enumerate(palette):
        required = counts.get(index, 0)
        if not required:
            continue
        known_stock = entry["id"] in stock
        on_hand = stock.get(entry["id"]) if known_stock else 0
        rows.append({"id": entry["id"], "name": entry["name"], "hex": entry["hex"], "brand": entry.get("brand", "Adaptive"), "series": entry.get("series", ""), "required": required, "on_hand": on_hand, "to_buy": max(0, required - on_hand) if on_hand is not None else None})
    return rows


def write_shopping_list(rows: list[dict], output_path: str | Path) -> Path:
    """Write an order-ready CSV or JSON shopping list based on its extension."""
    destination = Path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix.lower() == ".json":
            destination.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            if destination.suffix.lower() != ".csv":
                raise ValueError("Shopping list output must end in .csv or .json.")
            with destination.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=("id", "name", "hex", "brand", "series", "required", "on_hand", "to_buy"))
                writer.writeheader()
                writer.writerows(rows)
    except OSError as error:
        raise OSError(f"Cannot write shopping list to {destination}. Choose a writable --shopping-list path.") from error
    return destination


def compact_palette(grid: np.ndarray, palette: list[dict]) -> tuple[np.ndarray, list[dict]]:
    """Drop colours removed during cleanup and reindex the grid contiguously."""
    indices = np.asarray(grid, dtype=np.int16)
    used = sorted(int(index) for index in np.unique(indices))
    remap = {old_index: new_index for new_index, old_index in enumerate(used)}
    compacted = np.vectorize(remap.__getitem__, otypes=[np.int16])(indices)
    return compacted, [palette[index] for index in used]
