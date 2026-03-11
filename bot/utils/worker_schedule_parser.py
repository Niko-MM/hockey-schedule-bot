"""Parse worker schedule from CSV exported Google Sheet.

Input: raw CSV text with columns:
0: time_slot
1: operator
2: camera
3: camera_c
4: commentator
5: referee

Output: (slots, errors)
- slots: list of dicts with fixed keys and optional is_break flag
- errors: list of human-readable error messages
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import csv
import io


@dataclass
class WorkerSlot:
    """One worker slot parsed from sheet."""

    time_slot: str
    operator: str
    camera: str
    camera_c: str
    commentator: str
    referee: str
    is_break: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_slot": self.time_slot,
            "operator": self.operator,
            "camera": self.camera,
            "camera_c": self.camera_c,
            "commentator": self.commentator,
            "referee": self.referee,
            "is_break": self.is_break,
        }


def parse_worker_schedule_csv(csv_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse CSV text into worker slots and collect format errors only.

    Rules:
    - First row is treated as header and skipped.
    - Completely empty rows are ignored.
    - If time_slot is empty and rest are empty -> ignore row.
    - If time_slot is not empty and all role cells are empty -> is_break=True.
    - If row has fewer than 6 columns -> error.
    """
    slots: list[dict[str, Any]] = []
    errors: list[str] = []

    if not csv_text.strip():
        return slots, errors

    reader = csv.reader(io.StringIO(csv_text))

    row_index = 0
    for raw_row in reader:
        row_index += 1

        # Skip header row
        if row_index == 1:
            continue

        # Normalize row length (pad with empty strings)
        row = list(raw_row)
        # Completely empty row
        if not any(cell.strip() for cell in row):
            continue

        if len(row) < 6:
            errors.append(
                f"Строка {row_index}: ожидается минимум 6 столбцов "
                f"(время + 5 ролей), получено {len(row)}."
            )
            # We still try to pad and parse what we can
            row.extend([""] * (6 - len(row)))

        time_slot = row[0].strip()
        operator = row[1].strip()
        camera = row[2].strip()
        camera_c = row[3].strip()
        commentator = row[4].strip()
        referee = row[5].strip()

        # If time and all roles are empty – ignore
        if not time_slot and not any(
            [operator, camera, camera_c, commentator, referee]
        ):
            continue

        # If time exists but all roles empty -> break slot (for image only)
        is_break = False
        if time_slot and not any(
            [operator, camera, camera_c, commentator, referee]
        ):
            is_break = True

        slot = WorkerSlot(
            time_slot=time_slot,
            operator=operator,
            camera=camera,
            camera_c=camera_c,
            commentator=commentator,
            referee=referee,
            is_break=is_break,
        )
        slots.append(slot.to_dict())

    return slots, errors

