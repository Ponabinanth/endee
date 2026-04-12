from __future__ import annotations

from collections.abc import Iterable


def build_endee_filter(
    *,
    department: str = "all",
    doc_type: str = "all",
    audience: str = "all",
) -> list[dict[str, dict[str, str]]] | None:
    clauses: list[dict[str, dict[str, str]]] = []
    if department and department != "all":
        clauses.append({"department": {"$eq": department}})
    if doc_type and doc_type != "all":
        clauses.append({"doc_type": {"$eq": doc_type}})
    if audience and audience != "all":
        clauses.append({"audience": {"$eq": audience}})
    return clauses or None


def dedupe_sorted(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})

