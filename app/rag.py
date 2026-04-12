from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "with",
    "you",
}


@dataclass(frozen=True)
class Citation:
    label: str
    title: str
    source: str
    department: str
    doc_type: str
    audience: str
    score: float
    excerpt: str


def sentence_split(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    return [piece.strip() for piece in pieces if piece.strip()]


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[A-Za-z0-9]+", text.lower())
        if token and token not in STOPWORDS and len(token) > 2
    ]


def truncate(text: str, limit: int = 180) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def build_context(hits: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[{index}] {hit['title']} ({hit['source']})",
                    f"Department: {hit['department']} | Doc Type: {hit['doc_type']} | Audience: {hit['audience']}",
                    hit["text"],
                ]
            )
        )
    return "\n\n".join(blocks)


def _sentence_score(question_terms: set[str], sentence: str, position_bonus: float) -> float:
    sentence_terms = set(tokenize(sentence))
    overlap = len(question_terms & sentence_terms)
    if not overlap:
        return 0.0
    length_bonus = min(len(sentence) / 240.0, 1.0) * 0.2
    return overlap + length_bonus + position_bonus


def extractive_answer(question: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    question_terms = set(tokenize(question))
    scored_sentences: list[tuple[float, str, dict[str, Any], int]] = []

    for hit_index, hit in enumerate(hits):
        position_bonus = max(0.0, 0.3 - hit_index * 0.05)
        for sentence in sentence_split(hit["text"]):
            score = _sentence_score(question_terms, sentence, position_bonus)
            if score > 0:
                scored_sentences.append((score, sentence, hit, hit_index))

    scored_sentences.sort(key=lambda item: item[0], reverse=True)

    selected: list[tuple[str, dict[str, Any], int]] = []
    seen: set[str] = set()
    for _, sentence, hit, hit_index in scored_sentences:
        normalized = sentence.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        selected.append((sentence, hit, hit_index))
        if len(selected) >= 4:
            break

    if not selected and hits:
        first_hit = hits[0]
        selected.append((truncate(first_hit["text"], 220), first_hit, 0))

    if not selected:
        return {
            "mode": "extractive",
            "answer": "I could not find enough grounded context to answer that question.",
            "citations": [],
            "context": "",
            "raw": {"reason": "no_hits"},
        }

    answer_lines = [
        "Here is the best grounded answer from the retrieved context:",
        "",
    ]
    citations: list[dict[str, Any]] = []
    for label_index, (sentence, hit, hit_index) in enumerate(selected, start=1):
        label = f"[{label_index}]"
        answer_lines.append(f"- {sentence} {label}")
        citations.append(
            {
                "label": label,
                "title": hit["title"],
                "source": hit["source"],
                "department": hit["department"],
                "doc_type": hit["doc_type"],
                "audience": hit["audience"],
                "score": float(hit["score"]),
                "excerpt": truncate(hit["text"], 220),
            }
        )

    answer_lines.extend(
        [
            "",
            "If you want a tighter answer, try adding a department filter or upload a more specific document.",
        ]
    )
    return {
        "mode": "extractive",
        "answer": "\n".join(answer_lines),
        "citations": citations,
        "context": build_context(hits),
        "raw": {"selected_sentences": len(selected)},
    }


def openai_answer(question: str, hits: list[dict[str, Any]], *, api_key: str, model: str) -> dict[str, Any]:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        context = build_context(hits)
        system_message = (
            "You are InsightForge, a retrieval-grounded assistant. "
            "Answer only from the provided context. "
            "Cite sources using bracketed labels like [1] or [2]. "
            "If the context is insufficient, say so clearly."
        )
        user_message = f"Question:\n{question}\n\nContext:\n{context}"
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        )
        answer = response.choices[0].message.content or ""
        citations = [
            {
                "label": f"[{index}]",
                "title": hit["title"],
                "source": hit["source"],
                "department": hit["department"],
                "doc_type": hit["doc_type"],
                "audience": hit["audience"],
                "score": float(hit["score"]),
                "excerpt": truncate(hit["text"], 220),
            }
            for index, hit in enumerate(hits[:5], start=1)
        ]
        return {
            "mode": "openai",
            "answer": answer.strip(),
            "citations": citations,
            "context": context,
            "raw": {"model": model},
        }
    except Exception as exc:  # pragma: no cover - depends on optional API access
        fallback = extractive_answer(question, hits)
        fallback["mode"] = "extractive_fallback"
        fallback["raw"] = {**fallback.get("raw", {}), "llm_error": str(exc), "model": model}
        return fallback

