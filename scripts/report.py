"""Machine-readable conversion report generation."""

from __future__ import annotations

import json
from pathlib import Path


def write_report(report: dict, output_path: str | Path) -> Path:
    """Write a UTF-8 JSON conversion report with an actionable destination error."""
    destination = Path(output_path)
    if destination.suffix.lower() != ".json":
        raise ValueError("Report output must use a .json filename.")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        raise OSError(f"Cannot write report to {destination}. Choose a writable --report path.") from error
    return destination
