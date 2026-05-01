from __future__ import annotations

import re
import time
from typing import Any

from app.embeddings import HashEmbedder
from app.schemas import ChatResponse, ChatTurn, Citation
from app.vector_store import LocalVectorStore


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "what",
    "when", "where", "which", "with", "you", "your",
}


def tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9_]+", text.lower())
        if token not in STOPWORDS and len(token) > 2
    }


def sentence_split(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def truncate(text: str, limit: int = 240) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


class RagChain:
    def __init__(self, *, store: LocalVectorStore, embedder: HashEmbedder, openai_api_key: str = "", openai_model: str = "gpt-4o-mini") -> None:
        self.store = store
        self.embedder = embedder
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model

    def answer(self, question: str, *, top_k: int = 5, history: list[ChatTurn] | None = None) -> ChatResponse:
        started = time.perf_counter()
        retrieval_query = self._retrieval_query(question, history or [])
        retrieval_started = time.perf_counter()
        hits = self.store.search(self.embedder.embed(retrieval_query), top_k=top_k)
        retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
        citations = [
            Citation(
                label=f"[{index}]",
                document_id=hit["document"].document_id,
                title=hit["document"].title,
                source=hit["document"].source,
                chunk_index=hit["chunk"].chunk_index,
                score=float(hit["score"]),
                excerpt=truncate(hit["chunk"].text),
            )
            for index, hit in enumerate(hits, start=1)
        ]

        if self.openai_api_key and hits:
            answer, mode = self._openai_answer(question, hits, history or []), "openai"
        else:
            answer, mode = self._extractive_answer(question, hits), "extractive"

        return ChatResponse(
            question=question,
            answer=answer,
            mode=mode,
            citations=citations,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            retrieval_ms=retrieval_ms,
        )

    def _retrieval_query(self, question: str, history: list[ChatTurn]) -> str:
        if not history:
            return question
        recent_user_turns = [
            turn.content.strip()
            for turn in history[-6:]
            if turn.role == "user" and turn.content.strip()
        ]
        return "\n".join([*recent_user_turns[-3:], question])

    def _extractive_answer(self, question: str, hits: list[dict[str, Any]]) -> str:
        if not hits:
            return "I could not find relevant context in the indexed documents."

        query_terms = tokenize(question)
        scored_sentences: list[tuple[int, str, int]] = []
        for hit_index, hit in enumerate(hits):
            for sentence in sentence_split(hit["chunk"].text):
                overlap = len(query_terms & tokenize(sentence))
                if overlap:
                    scored_sentences.append((overlap, sentence, hit_index + 1))

        scored_sentences.sort(key=lambda item: item[0], reverse=True)
        selected = scored_sentences[:4]
        if not selected:
            selected = [(1, truncate(hits[0]["chunk"].text), 1)]

        lines = ["Here is the best grounded answer from your documents:"]
        for _, sentence, citation_index in selected:
            lines.append(f"- {sentence} [{citation_index}]")
        return "\n".join(lines)

    def _openai_answer(self, question: str, hits: list[dict[str, Any]], history: list[ChatTurn]) -> str:
        try:
            from openai import OpenAI

            context = "\n\n".join(
                f"[{index}] {hit['document'].title} ({hit['document'].source})\n{hit['chunk'].text}"
                for index, hit in enumerate(hits, start=1)
            )
            conversation = "\n".join(
                f"{turn.role}: {truncate(turn.content, 500)}"
                for turn in history[-6:]
            )
            client = OpenAI(api_key=self.openai_api_key)
            response = client.chat.completions.create(
                model=self.openai_model,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": "Answer only from the provided context. Cite sources with bracket labels like [1].",
                    },
                    {
                        "role": "user",
                        "content": f"Conversation so far:\n{conversation or 'None'}\n\nQuestion:\n{question}\n\nContext:\n{context}",
                    },
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            return f"OpenAI generation failed, so I fell back to retrieved context. Error: {exc}\n\n{self._extractive_answer(question, hits)}"
