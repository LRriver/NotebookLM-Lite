from __future__ import annotations

import asyncio
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domain.source import KnowledgeChunk, KnowledgeSource, SourceKind
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        warning_messages: list[str] = []

        class WarningCapture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if record.levelno >= logging.WARNING:
                    warning_messages.append(record.getMessage())

        warning_capture = WarningCapture()
        root_logger = logging.getLogger()
        root_logger.addHandler(warning_capture)
        repo = SeekDBRepository(Path(tmp) / "knowledge.db", allow_sqlite_vector_fallback=False)
        try:
            source = KnowledgeSource(id="verify-source", kind=SourceKind.TEXT, title="Verify")
            await repo.save_source(source)
            await repo.save_chunks(
                source.id,
                [
                    KnowledgeChunk(
                        id="verify-chunk",
                        source_id=source.id,
                        content="SeekDB native vector retrieval verification",
                        chunk_index=0,
                        embedding=[0.1, 0.2, 0.3],
                        metadata={"source_id": source.id},
                    )
                ],
            )
            results = await repo.search_chunks(
                "SeekDB native retrieval",
                source_ids=[source.id],
                top_k=1,
                query_embedding=[0.1, 0.2, 0.3],
            )
            if not results:
                raise RuntimeError("expected at least one native SeekDB result")
            if results[0]["chunk"].id != "verify-chunk":
                raise RuntimeError("native SeekDB returned the wrong chunk")
            if results[0].get("backend") != "seekdb":
                raise RuntimeError("retrieval did not use the native SeekDB backend")
            text_results = await repo.search_chunks(
                "native vector retrieval verification",
                source_ids=[source.id],
                top_k=1,
            )
            if not text_results or text_results[0].get("backend") != "seekdb":
                raise RuntimeError("full-text retrieval did not use the native SeekDB backend")
            if text_results[0]["chunk"].id != "verify-chunk":
                raise RuntimeError("native SeekDB full-text search returned the wrong chunk")
            if repo.storage_status()["vector_backend"] != "seekdb":
                raise RuntimeError("repository did not report the native SeekDB backend")
            loaded_chunks = await repo.get_chunks(source.id)
            if len(loaded_chunks) != 1 or loaded_chunks[0].embedding != [0.1, 0.2, 0.3]:
                raise RuntimeError("repository did not read the stored chunk back from SeekDB")
            sqlite_row = repo._conn.execute(
                "SELECT embedding, payload, vector_state FROM chunks WHERE source_id = ?",
                (source.id,),
            ).fetchone()
            if sqlite_row is None:
                raise RuntimeError("SQLite chunk metadata row is missing")
            if sqlite_row["embedding"] is not None or '"embedding":null' not in sqlite_row["payload"]:
                raise RuntimeError("SQLite retained a chunk vector in strict SeekDB mode")
            if sqlite_row["vector_state"] != "seekdb":
                raise RuntimeError("SQLite chunk metadata does not mark SeekDB as vector authority")
            if any("Skipping optional pyseekdb chunk mirror" in message for message in warning_messages):
                raise RuntimeError("legacy optional pyseekdb mirror warning was emitted")
        finally:
            await repo.close()
            root_logger.removeHandler(warning_capture)
    print("SeekDB native vector verification passed")


if __name__ == "__main__":
    asyncio.run(main())
