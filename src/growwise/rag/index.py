from __future__ import annotations

import json
import math
import sqlite3
from datetime import date
from pathlib import Path

from .chunking import ResourceChunk
from .embeddings import EmbeddingProvider
from .temporal import hierarchical_temporal_order, temporal_tier


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class HybridRagIndex:
    """SQLite-backed resource chunk index with lexical + optional vector scoring.

    Relevance is calculated first. Relevant evidence is then exposed through a deterministic
    temporal hierarchy: the current month is filled first, then the rest of the current year,
    then older archive material. This matches how a parent usually asks about an evolving child
    context while still allowing older evidence to fill gaps.
    """

    def __init__(self, path: Path, embedding: EmbeddingProvider | None = None) -> None:
        self.path = path
        self.embedding = embedding
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    child_id TEXT,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_url TEXT,
                    source_name TEXT,
                    tags_json TEXT NOT NULL,
                    embedding_json TEXT,
                    recorded_at TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(rag_chunks)").fetchall()
            }
            if "recorded_at" not in columns:
                connection.execute("ALTER TABLE rag_chunks ADD COLUMN recorded_at TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_resource ON rag_chunks(resource_id)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_rag_child ON rag_chunks(child_id)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_child_time "
                "ON rag_chunks(child_id, recorded_at DESC)"
            )
            connection.commit()
        finally:
            connection.close()

    def reset(self) -> None:
        """Clear the rebuildable RAG projection without replacing the SQLite file."""
        connection = self._connect()
        try:
            connection.execute("DELETE FROM rag_chunks")
            connection.commit()
        finally:
            connection.close()

    def delete_resource(self, resource_id: str) -> int:
        connection = self._connect()
        try:
            cursor = connection.execute(
                "DELETE FROM rag_chunks WHERE resource_id = ?", (resource_id,)
            )
            connection.commit()
            return cursor.rowcount
        finally:
            connection.close()

    def delete_child(self, child_id: str) -> int:
        """Delete every private RAG chunk belonging to one child."""
        connection = self._connect()
        try:
            cursor = connection.execute("DELETE FROM rag_chunks WHERE child_id = ?", (child_id,))
            connection.commit()
            return cursor.rowcount
        finally:
            connection.close()

    def replace_resource(self, chunks: list[ResourceChunk]) -> int:
        if not chunks:
            return 0
        resource_id = chunks[0].resource_id
        if any(chunk.resource_id != resource_id for chunk in chunks):
            raise ValueError("replace_resource expects chunks from exactly one resource")

        vectors: list[list[float] | None] = [None] * len(chunks)
        if self.embedding is not None:
            try:
                embedded = self.embedding.embed_documents([chunk.text for chunk in chunks])
                vectors = list(embedded)
            except Exception:
                vectors = [None] * len(chunks)
        if len(vectors) != len(chunks):
            vectors = [None] * len(chunks)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM rag_chunks WHERE resource_id = ?", (resource_id,))
            for chunk, vector in zip(chunks, vectors, strict=True):
                connection.execute(
                    """
                    INSERT INTO rag_chunks (
                        chunk_id, resource_id, child_id, title, text,
                        source_url, source_name, tags_json, embedding_json, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.resource_id,
                        chunk.child_id,
                        chunk.title,
                        chunk.text,
                        chunk.source_url,
                        chunk.source_name,
                        json.dumps(list(chunk.tags), ensure_ascii=False),
                        json.dumps(vector) if vector is not None else None,
                        chunk.recorded_at,
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return len(chunks)

    def search(
        self,
        *,
        query: str,
        child_id: str | None,
        limit: int = 8,
        reference_date: date | None = None,
    ) -> list[dict]:
        if limit <= 0:
            return []
        query_terms = [term.casefold() for term in query.split() if len(term.strip()) >= 2]
        query_vector: list[float] | None = None
        if self.embedding is not None:
            try:
                query_vector = self.embedding.embed_query(query)
            except Exception:
                query_vector = None

        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM rag_chunks
                WHERE child_id IS NULL OR child_id = ?
                """,
                (child_id,),
            ).fetchall()
        finally:
            connection.close()

        ranked: list[tuple[float, dict]] = []
        for row in rows:
            haystack = f"{row['title']} {row['text']} {row['tags_json']}".casefold()
            lexical = float(sum(haystack.count(term) for term in query_terms))
            vector_score = 0.0
            if query_vector is not None and row["embedding_json"]:
                try:
                    stored_vector = json.loads(row["embedding_json"])
                except (TypeError, json.JSONDecodeError):
                    stored_vector = []
                if isinstance(stored_vector, list):
                    vector_score = cosine_similarity(query_vector, stored_vector)
            if lexical <= 0 and vector_score <= 0:
                continue
            score = lexical + max(vector_score, 0.0) * 3.0
            payload = {
                "chunk_id": row["chunk_id"],
                "resource_id": row["resource_id"],
                "child_id": row["child_id"],
                "title": row["title"],
                "text": row["text"],
                "source_url": row["source_url"],
                "source_name": row["source_name"],
                "tags": json.loads(row["tags_json"]),
                "recorded_at": row["recorded_at"],
                "temporal_tier": temporal_tier(
                    row["recorded_at"], reference_date=reference_date
                ).name.lower(),
                "score": score,
                "lexical_score": lexical,
                "vector_score": vector_score,
            }
            ranked.append((score, payload))

        # Relevance order is preserved inside each time tier. A very recent irrelevant chunk never
        # enters this list in the first place, so temporal preference cannot manufacture relevance.
        ranked.sort(key=lambda item: item[0], reverse=True)
        relevant = [payload for _, payload in ranked]
        return hierarchical_temporal_order(
            relevant,
            timestamp=lambda item: item.get("recorded_at"),
            limit=limit,
            reference_date=reference_date,
        )
