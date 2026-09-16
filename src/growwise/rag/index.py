from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from .chunking import ResourceChunk
from .embeddings import EmbeddingProvider


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _fts_query(terms: list[str]) -> str:
    # Treat user input as literal text and use token-prefix matching. Prefix matching matters for
    # Korean because SQLite's unicode tokenizer sees forms such as "고양이를" as one token while a
    # parent naturally searches for the stem "고양이".
    return " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"*' for term in terms)


class HybridRagIndex:
    """SQLite-backed resource chunk index with lexical + optional vector scoring.

    Core-only lexical search uses an FTS5 candidate set instead of loading every chunk into Python.
    When a vector provider is active we retain the full scoped scan to preserve semantic recall
    until a dedicated vector index is enabled; WAL and busy-timeout settings keep concurrent
    desktop reads and writes from failing on short-lived SQLite locks.
    """

    def __init__(self, path: Path, embedding: EmbeddingProvider | None = None) -> None:
        self.path = path
        self.embedding = embedding
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_available = False
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
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
                    embedding_json TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_resource ON rag_chunks(resource_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_child ON rag_chunks(child_id)"
            )
            try:
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
                        chunk_id UNINDEXED,
                        resource_id UNINDEXED,
                        child_id UNINDEXED,
                        title,
                        text,
                        tags
                    )
                    """
                )
                # RAG is disposable; rebuilding this small lexical projection on schema/open keeps
                # migrations simple and guarantees it cannot drift from rag_chunks.
                connection.execute("DELETE FROM rag_chunks_fts")
                connection.execute(
                    """
                    INSERT INTO rag_chunks_fts (
                        chunk_id, resource_id, child_id, title, text, tags
                    )
                    SELECT chunk_id, resource_id, child_id, title, text, tags_json
                    FROM rag_chunks
                    """
                )
                self._fts_available = True
            except sqlite3.OperationalError:
                # Some embedded SQLite builds omit FTS5. Search safely falls back to the original
                # scoped scan rather than making the application fail to start.
                self._fts_available = False
            connection.commit()
        finally:
            connection.close()

    def reset(self) -> None:
        """Clear the rebuildable RAG projection without replacing the SQLite file."""
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            connection.execute("DELETE FROM rag_chunks")
            if self._fts_available:
                connection.execute("DELETE FROM rag_chunks_fts")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def delete_resource(self, resource_id: str) -> int:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            cursor = connection.execute(
                "DELETE FROM rag_chunks WHERE resource_id = ?", (resource_id,)
            )
            if self._fts_available:
                connection.execute(
                    "DELETE FROM rag_chunks_fts WHERE resource_id = ?", (resource_id,)
                )
            connection.commit()
            return cursor.rowcount
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def replace_resource(self, chunks: list[ResourceChunk]) -> int:
        if not chunks:
            return 0
        resource_id = chunks[0].resource_id
        if any(chunk.resource_id != resource_id for chunk in chunks):
            raise ValueError("all replacement chunks must belong to the same resource")

        vectors: list[list[float] | None] = [None] * len(chunks)
        if self.embedding is not None:
            try:
                embedded = self.embedding.embed_documents([chunk.text for chunk in chunks])
                vectors = list(embedded)
                if len(vectors) != len(chunks):
                    vectors = [None] * len(chunks)
            except Exception:
                vectors = [None] * len(chunks)

        connection = self._connect()
        try:
            connection.execute("BEGIN")
            connection.execute("DELETE FROM rag_chunks WHERE resource_id = ?", (resource_id,))
            if self._fts_available:
                connection.execute(
                    "DELETE FROM rag_chunks_fts WHERE resource_id = ?", (resource_id,)
                )
            for chunk, vector in zip(chunks, vectors, strict=True):
                tags_json = json.dumps(list(chunk.tags), ensure_ascii=False)
                connection.execute(
                    """
                    INSERT INTO rag_chunks (
                        chunk_id, resource_id, child_id, title, text,
                        source_url, source_name, tags_json, embedding_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.resource_id,
                        chunk.child_id,
                        chunk.title,
                        chunk.text,
                        chunk.source_url,
                        chunk.source_name,
                        tags_json,
                        json.dumps(vector) if vector is not None else None,
                    ),
                )
                if self._fts_available:
                    connection.execute(
                        """
                        INSERT INTO rag_chunks_fts (
                            chunk_id, resource_id, child_id, title, text, tags
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.chunk_id,
                            chunk.resource_id,
                            chunk.child_id,
                            chunk.title,
                            chunk.text,
                            tags_json,
                        ),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return len(chunks)

    @staticmethod
    def _scoped_rows(
        connection: sqlite3.Connection,
        child_id: str | None,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_chunks WHERE child_id IS NULL OR child_id = ?",
            (child_id,),
        ).fetchall()

    def _lexical_candidates(
        self,
        connection: sqlite3.Connection,
        *,
        query_terms: list[str],
        child_id: str | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        if not self._fts_available or not query_terms:
            return self._scoped_rows(connection, child_id)
        candidate_limit = max(200, limit * 20)
        try:
            rows = connection.execute(
                """
                SELECT c.*
                FROM rag_chunks AS c
                JOIN rag_chunks_fts AS f ON f.chunk_id = c.chunk_id
                WHERE rag_chunks_fts MATCH ?
                  AND (c.child_id IS NULL OR c.child_id = ?)
                LIMIT ?
                """,
                (_fts_query(query_terms), child_id, candidate_limit),
            ).fetchall()
            if rows:
                return rows
            # FTS token boundaries are language-dependent. Preserve the previous substring-search
            # recall when FTS returns no candidate (for example Korean stems embedded in a token).
            return self._scoped_rows(connection, child_id)
        except sqlite3.OperationalError:
            # Query tokenization/SQLite build differences must never make search unavailable.
            return self._scoped_rows(connection, child_id)

    def search(
        self,
        *,
        query: str,
        child_id: str | None,
        limit: int = 8,
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

        if not query_terms and query_vector is None:
            return []

        connection = self._connect()
        try:
            # Semantic ranking still needs all scoped vectors. Without a query vector, FTS5 reduces
            # the Python ranking set from O(all chunks) to O(lexical candidates).
            if query_vector is not None:
                rows = self._scoped_rows(connection, child_id)
            else:
                rows = self._lexical_candidates(
                    connection,
                    query_terms=query_terms,
                    child_id=child_id,
                    limit=limit,
                )
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
                except (TypeError, ValueError, json.JSONDecodeError):
                    stored_vector = []
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
                "score": score,
                "lexical_score": lexical,
                "vector_score": vector_score,
            }
            ranked.append((score, payload))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [payload for _, payload in ranked[:limit]]
