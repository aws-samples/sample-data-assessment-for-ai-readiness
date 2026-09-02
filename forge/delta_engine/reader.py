"""JSONL history file reader for the Delta Engine.

Reads forge_history.jsonl and returns parsed records as a list of dicts.
Handles missing files, empty files, and malformed lines gracefully.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_history(path: "str | Path") -> list[dict]:
    """Parse forge_history.jsonl and return valid records in order.

    Args:
        path: Path to the forge_history.jsonl file (str or Path).

    Returns:
        List of parsed JSON dicts, one per valid line. Returns an empty
        list if the file does not exist or contains no valid records.

    Behavior:
        - Missing file → returns empty list
        - Empty file → returns empty list
        - Malformed lines → skipped with a warning log, valid lines still returned
    """
    path = Path(path)

    if not path.exists():
        logger.debug("History file not found: %s", path)
        return []

    records: list[dict] = []

    with open(path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                records.append(record)
            except json.JSONDecodeError as e:
                logger.warning(
                    "Skipping malformed line %d in %s: %s",
                    line_number,
                    path,
                    e,
                )

    return records
