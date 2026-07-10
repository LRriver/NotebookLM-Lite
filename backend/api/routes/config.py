"""Runtime model configuration routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...config import (
    ModelProfile,
    ModelProfiles,
    get_settings,
    model_profile_identity,
    update_runtime_model_profiles,
)
from ...dependencies import DependencyContainer
from ..schemas.config import PublicModelProfile, RuntimeConfigResponse, RuntimeConfigUpdate

router = APIRouter(prefix="/config", tags=["Config"])


def _public_profile(profile: ModelProfile) -> PublicModelProfile:
    return PublicModelProfile(
        model=profile.model,
        base_url=profile.base_url,
        adapter=profile.adapter,
        thinking=profile.thinking.model_dump() if profile.thinking else None,
        voice=profile.voice,
        response_format=profile.response_format,
        stream=profile.stream,
        api_key_set=bool(profile.api_key),
    )


async def _response(message: str = "") -> RuntimeConfigResponse:
    settings = get_settings()
    models = settings.api.models
    vector_store = DependencyContainer.get_vector_store(settings=settings)
    stats = await vector_store.get_stats()
    storage_status = stats.get("storage", {})
    return RuntimeConfigResponse(
        models={
            name: _public_profile(getattr(models, name))
            for name in ModelProfiles.model_fields
        },
        chunking={
            "provider": settings.chunking.provider,
            "tokenizer": settings.chunking.tokenizer,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        },
        storage={
            "vector_store_type": settings.vector_store_type,
            "configured_vector_store_type": settings.vector_store_type,
            "seekdb_path": settings.seekdb_path,
            "seekdb_allow_sqlite_fallback": settings.seekdb_allow_sqlite_fallback,
            "actual_vector_backend": storage_status.get("vector_backend", stats.get("backend", "unknown")),
            "native_available": storage_status.get("native_available", False),
            "embedding_required": (
                settings.vector_store_type == "seekdb"
                and not settings.seekdb_allow_sqlite_fallback
            ),
            "embedding_configured": bool(
                models.embedding_model.model and models.embedding_model.api_key
            ),
        },
        message=message,
    )


@router.get("", response_model=RuntimeConfigResponse)
async def get_runtime_config() -> RuntimeConfigResponse:
    return await _response()


@router.post("", response_model=RuntimeConfigResponse)
async def update_runtime_config(request: RuntimeConfigUpdate) -> RuntimeConfigResponse:
    requested_embedding = request.models.get("embedding_model")
    if requested_embedding is not None:
        settings = get_settings()
        current_profile = settings.api.models.embedding_model
        requested_values = requested_embedding.model_dump(exclude_none=True)
        if requested_values.get("api_key") == "":
            requested_values.pop("api_key")
        next_profile = current_profile.model_copy(update=requested_values)
        if model_profile_identity(next_profile) != model_profile_identity(current_profile):
            vector_store = DependencyContainer.get_vector_store(settings=settings)
            stats = await vector_store.get_stats()
            indexed_vector_chunks = stats.get(
                "indexed_vector_chunks",
                stats.get("total_chunks", 0),
            )
            if indexed_vector_chunks > 0:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The embedding model, adapter, or base URL cannot change while indexed "
                        "sources exist. Delete and re-index the sources first."
                    ),
                )
    profile_data = {
        name: profile.model_dump(exclude_none=True)
        for name, profile in request.models.items()
    }
    update_runtime_model_profiles(profile_data)
    DependencyContainer.reset_runtime_caches(preserve_repository=True)
    return await _response("Runtime model configuration updated.")
