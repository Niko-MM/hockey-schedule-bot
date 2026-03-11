"""Resolve worker schedule slots to person IDs and collect validation errors."""
from __future__ import annotations

from typing import Any

from db.crud import get_all_workers, _normalize_for_search  # type: ignore[attr-defined]


ROLE_FIELD_KEYS = [
    ("operator", "Оператор"),
    ("camera", "Камера"),
    ("camera_c", "Ц.Камера"),
    ("commentator", "Комментатор"),
    ("referee", "Судьи"),
]


async def resolve_worker_slots(
    slots: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve surnames in slots to worker person IDs.

    - Uses only active, not banned workers (get_all_workers).
    - If surname is empty for a role -> skipped (no error).
    - If surname not found among workers -> error.
    - If multiple workers share surname -> error.
    - Break slots (is_break=True) are allowed to have empty roles.

    Returns (resolved_slots, errors). If errors is not empty, resolved_slots
    should not be used for DB writes.
    """
    resolved: list[dict[str, Any]] = []
    errors: list[str] = []

    if not slots:
        return resolved, errors

    workers = await get_all_workers()
    # Build index by normalized surname
    by_surname: dict[str, list[Any]] = {}
    for w in workers:
        key = _normalize_for_search(w.surname)
        by_surname.setdefault(key, []).append(w)

    for idx, slot in enumerate(slots, start=1):
        time_slot = slot.get("time_slot") or ""
        is_break = bool(slot.get("is_break"))

        resolved_slot: dict[str, Any] = {
            "time_slot": time_slot,
            "is_break": is_break,
        }

        # Default all *_id to None
        for field_key, _ in ROLE_FIELD_KEYS:
            resolved_slot[f"{field_key}_id"] = None

        for field_key, role_label in ROLE_FIELD_KEYS:
            surname_raw = (slot.get(field_key) or "").strip()
            if not surname_raw:
                # Empty role cell is allowed (especially for breaks)
                continue

            norm = _normalize_for_search(surname_raw)
            candidates = by_surname.get(norm, [])

            if not candidates:
                errors.append(
                    f"Время {time_slot or '—'}: фамилия «{surname_raw}» для роли "
                    f"«{role_label}» не найдена среди работников."
                )
                continue

            if len(candidates) > 1:
                # Multiple workers with same surname
                names = ", ".join(f"{p.surname} {p.name}" for p in candidates)
                errors.append(
                    f"Время {time_slot or '—'}: фамилия «{surname_raw}» для роли "
                    f"«{role_label}» встречается у нескольких работников: {names}. "
                    "Уточните в БД или в таблице."
                )
                continue

            person = candidates[0]
            resolved_slot[f"{field_key}_id"] = person.id

        resolved.append(resolved_slot)

    return resolved, errors

