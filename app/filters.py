from __future__ import annotations

from collections.abc import Iterable


def build_endee_filter(
    *,
    entity_type: str = "candidate",
    role: str = "all",
    location: str = "all",
    stage: str = "all",
) -> list[dict[str, dict[str, str]]] | None:
    clauses: list[dict[str, dict[str, str]]] = []
    if entity_type and entity_type != "all":
        clauses.append({"entity_type": {"$eq": entity_type}})
    if role and role != "all":
        clauses.append({"target_role": {"$eq": role}})
    if location and location != "all":
        clauses.append({"location": {"$eq": location}})
    if stage and stage != "all":
        clauses.append({"stage": {"$eq": stage}})
    return clauses or None


def dedupe_sorted(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})
