from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.chat import get_chat_llm_factory, router as chat_router
from backend.core.services.source_service import SourceService
from backend.domain.source import KnowledgeChunk, KnowledgeSource, SourceKind, SourceStatus
from backend.dependencies import get_source_service, get_vector_store
from backend.infrastructure.parsers.docling_parser import DoclingParser
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository
from backend.infrastructure.vector_stores.seekdb_vector_store import SeekDBVectorStore


def sqlite_fallback_repo(path) -> SeekDBRepository:
    return SeekDBRepository(path, native_chunk_index=None, allow_sqlite_vector_fallback=True)


class EchoLLM:
    async def generate_with_context(self, query, context, system_prompt=None, **kwargs):
        return f"answer: {query} :: {context[0]}"

    async def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=4096, **kwargs):
        return "contextualized"


class RecordingLLM(EchoLLM):
    def __init__(self):
        self.context = []

    async def generate_with_context(self, query, context, system_prompt=None, **kwargs):
        self.context = context
        return "ok"


class ContextualizingLLM(EchoLLM):
    def __init__(self):
        self.answer_queries = []

    async def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=4096, **kwargs):
        return "Alpha standalone retrieval"

    async def generate_with_context(self, query, context, system_prompt=None, **kwargs):
        self.answer_queries.append(query)
        return f"answered original: {query}"


class StreamingLLM(EchoLLM):
    async def stream_generate_with_context(self, query, context, system_prompt=None, **kwargs):
        for token in ["## 流式回答\n\n", "TLS ", "来自资料。"]:
            yield token


class BadStreamingContextualizer(StreamingLLM):
    async def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=4096, **kwargs):
        return "unmatched rewritten query"

    async def stream_generate_with_context(self, query, context, system_prompt=None, **kwargs):
        yield f"streamed original: {query}"


@pytest.mark.asyncio
async def test_rag_retrieval_is_restricted_to_selected_sources(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "rag.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    first = await service.create_text_source("First", "Alpha selected material.")
    second = await service.create_text_source("Second", "Alpha forbidden material.")
    store = SeekDBVectorStore(repo)

    from backend.core.services.rag_service import RAGService

    result = await RAGService(store, EchoLLM()).query("Alpha", source_ids=[first.id])

    assert "selected" in result["answer"]
    assert all(citation["source_id"] == first.id for citation in result["citations"])
    assert second.id not in {citation["source_id"] for citation in result["citations"]}


def test_chat_api_rejects_empty_sources_and_can_save_answer(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "api-rag.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    store = SeekDBVectorStore(repo)

    app = FastAPI()
    app.include_router(chat_router, prefix="/api")
    app.dependency_overrides[get_source_service] = lambda: service
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_chat_llm_factory] = lambda: (lambda **kwargs: EchoLLM())
    client = TestClient(app)

    rejected = client.post("/api/chat/", json={"query": "Alpha", "source_ids": []})
    assert rejected.status_code == 400


def test_chat_api_returns_citations_and_save_answer_as_source(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "api-rag-save.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    store = SeekDBVectorStore(repo)
    source = asyncio.run(asyncio_create_source(service))

    app = FastAPI()
    app.include_router(chat_router, prefix="/api")
    app.dependency_overrides[get_source_service] = lambda: service
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_chat_llm_factory] = lambda: (lambda **kwargs: EchoLLM())
    client = TestClient(app)

    response = client.post("/api/chat/", json={"query": "Alpha", "source_ids": [source.id]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"][0]["source_id"] == source.id

    saved = client.post(
        "/api/chat/save-answer",
        json={"title": "Saved answer", "answer": payload["answer"], "source_ids": [source.id]},
    )
    assert saved.status_code == 200
    assert saved.json()["title"] == "Saved answer"


def test_chat_api_streams_answer_deltas_and_final_citations(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "api-rag-stream.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    store = SeekDBVectorStore(repo)
    source = asyncio.run(asyncio_create_source(service))

    app = FastAPI()
    app.include_router(chat_router, prefix="/api")
    app.dependency_overrides[get_source_service] = lambda: service
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_chat_llm_factory] = lambda: (lambda **kwargs: StreamingLLM())
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"query": "Alpha 是什么？", "source_ids": [source.id]},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: delta" in body
    assert 'data: {"content": "TLS "}' in body
    assert "event: final" in body
    assert source.id in body


def test_chat_api_stream_falls_back_to_original_query_when_contextualized_retrieval_misses(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "api-rag-stream-fallback.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    store = SeekDBVectorStore(repo)
    source = asyncio.run(asyncio_create_source(service))

    app = FastAPI()
    app.include_router(chat_router, prefix="/api")
    app.dependency_overrides[get_source_service] = lambda: service
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_chat_llm_factory] = lambda: (lambda **kwargs: BadStreamingContextualizer())
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/chat/stream",
        json={
            "query": "Alpha 是什么？",
            "source_ids": [source.id],
            "history": [{"role": "user", "content": "前一轮"}],
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "streamed original: Alpha" in body
    assert "没有找到相关信息" not in body
    assert source.id in body


@pytest.mark.asyncio
async def test_rag_no_results_and_follow_up_stay_source_scoped(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "rag-follow-up.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    source = await service.create_text_source("Follow", "Beta follow up material.")
    await service.create_text_source("Other", "Beta forbidden follow up material.")
    store = SeekDBVectorStore(repo)

    from backend.core.services.rag_service import RAGService

    rag = RAGService(store, EchoLLM())
    no_results = await rag.query("MissingNeedle", source_ids=[source.id])
    follow_up = await rag.multi_turn_query(
        question="Beta",
        history=[{"role": "user", "content": "之前的问题"}],
        source_ids=[source.id],
    )

    assert no_results["citations"] == []
    assert "没有找到相关信息" in no_results["answer"]
    assert follow_up["citations"][0]["source_id"] == source.id


@pytest.mark.asyncio
async def test_rag_multi_turn_uses_contextualized_query_only_for_retrieval(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "rag-follow-up-original.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    source = await service.create_text_source("Follow", "Alpha standalone retrieval material.")
    store = SeekDBVectorStore(repo)
    llm = ContextualizingLLM()

    from backend.core.services.rag_service import RAGService

    result = await RAGService(store, llm).multi_turn_query(
        question="那它为什么安全？",
        history=[{"role": "user", "content": "HTTPS 是什么？"}],
        source_ids=[source.id],
    )

    assert result["citations"][0]["source_id"] == source.id
    assert llm.answer_queries == ["那它为什么安全？"]
    assert result["answer"] == "answered original: 那它为什么安全？"


@pytest.mark.asyncio
async def test_rag_context_labels_sources_for_normal_user_file_comparison(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "rag-source-labels.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    pdf_source = await service.create_text_source(
        "HTTPS.pdf",
        "HTTP transmits plaintext. HTTPS uses TLS certificates and encrypted transport.",
    )
    md_source = await service.create_text_source(
        "L9.md",
        "The L9 guide covers vehicle charging, cabin comfort, and roadside service.",
    )
    store = SeekDBVectorStore(repo)
    llm = RecordingLLM()

    from backend.core.services.rag_service import RAGService

    await RAGService(store, llm, top_k=4).query(
        "帮我概括一下这两个文件分别讲了什么",
        source_ids=[pdf_source.id, md_source.id],
    )

    joined_context = "\n".join(llm.context)
    assert "Source: HTTPS.pdf" in joined_context
    assert "Source: L9.md" in joined_context


@pytest.mark.asyncio
async def test_rag_file_overview_includes_every_selected_source_even_when_bm25_matches_one_source(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "rag-overview-balanced.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    pdf_source = await service.create_text_source(
        "HTTPS.pdf",
        "这个文件 文件 文件 主要内容 讲了 HTTP 明文传输和 HTTPS 证书加密。",
    )
    md_source = await service.create_text_source(
        "L9.md",
        "L9 手册覆盖车辆充电、用车服务、座舱舒适性和道路救援。",
    )
    store = SeekDBVectorStore(repo)
    llm = RecordingLLM()

    from backend.core.services.rag_service import RAGService

    await RAGService(store, llm, top_k=4).query(
        "帮我概括一下这两个文件分别讲了什么",
        source_ids=[pdf_source.id, md_source.id],
    )

    joined_context = "\n".join(llm.context)
    assert "Source: HTTPS.pdf" in joined_context
    assert "Source: L9.md" in joined_context


@pytest.mark.asyncio
async def test_rag_file_overview_includes_every_selected_source_when_top_k_is_smaller(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "rag-overview-all-sources.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    sources = [
        await service.create_text_source(f"Source {index}", f"Source {index} overview material.")
        for index in range(6)
    ]
    store = SeekDBVectorStore(repo)
    llm = RecordingLLM()

    from backend.core.services.rag_service import RAGService

    await RAGService(store, llm, top_k=5).query(
        "这些文件分别讲了什么",
        source_ids=[source.id for source in sources],
    )

    joined_context = "\n".join(llm.context)
    for source in sources:
        assert f"Source: {source.title}" in joined_context


@pytest.mark.asyncio
async def test_rag_balances_context_across_selected_sources_for_cross_source_questions(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "rag-cross-source-balanced.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    pdf_source = await service.create_text_source(
        "HTTPS.pdf",
        "HTTPS 安全 安全 安全 证书 校验 加密 传输 完整性 保护。",
    )
    md_source = await service.create_text_source(
        "L9.md",
        "理想 L9 智能驾驶 OTA 语音座舱 车机联网 都需要安全保护。",
    )
    store = SeekDBVectorStore(repo)
    llm = RecordingLLM()

    from backend.core.services.rag_service import RAGService

    await RAGService(store, llm, top_k=1).query(
        "结合 HTTPS 的安全保护思路，理想 L9 的智能驾驶和 OTA 应该注意什么？",
        source_ids=[pdf_source.id, md_source.id],
    )

    joined_context = "\n".join(llm.context)
    assert "Source: HTTPS.pdf" in joined_context
    assert "Source: L9.md" in joined_context


@pytest.mark.asyncio
async def test_rag_targeted_summary_uses_retrieval_instead_of_first_chunks(tmp_path):
    repo = sqlite_fallback_repo(tmp_path / "rag-targeted-summary.db")
    source = KnowledgeSource(
        kind=SourceKind.FILE,
        title="HTTPS.pdf",
        status=SourceStatus.READY,
        chunk_count=2,
        text="目录和版权信息。\n\nTLS 证书验证让 HTTPS 能确认服务器身份并建立加密传输。",
    )
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id=f"{source.id}_chunk_0",
                source_id=source.id,
                content="目录和版权信息。",
                chunk_index=0,
                metadata={"source_id": source.id, "source_title": source.title, "chunk_index": 0},
            ),
            KnowledgeChunk(
                id=f"{source.id}_chunk_1",
                source_id=source.id,
                content="TLS 证书验证让 HTTPS 能确认服务器身份并建立加密传输。",
                chunk_index=1,
                metadata={"source_id": source.id, "source_title": source.title, "chunk_index": 1},
            ),
        ],
    )
    store = SeekDBVectorStore(repo)
    llm = RecordingLLM()

    from backend.core.services.rag_service import RAGService

    await RAGService(store, llm, top_k=1).query(
        "总结 HTTPS 为什么安全",
        source_ids=[source.id],
    )

    joined_context = "\n".join(llm.context)
    assert "TLS 证书验证" in joined_context
    assert "目录和版权信息" not in joined_context


async def asyncio_create_source(service):
    return await service.create_text_source("Source", "Alpha source content.")
