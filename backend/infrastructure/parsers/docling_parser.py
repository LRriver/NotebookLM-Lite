"""Docling-backed parser facade with safe text fallbacks."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import Any


class ParsedDocument(dict):
    """Small typed alias for parsed content dictionaries."""


class DoclingParser:
    """Parse supported files to canonical Markdown/text.

    Docling is imported lazily so tests and text-only deployments can run before
    the optional native stack is installed. Plain text-like files always use a
    deterministic local fallback.
    """

    TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml"}

    async def parse_text(self, text: str, title: str = "Pasted text") -> ParsedDocument:
        return ParsedDocument(
            content=text,
            metadata={"title": title, "parser": "plain_text", "mime_type": "text/plain"},
        )

    async def parse_file(self, file_path: str | Path, filename: str | None = None) -> ParsedDocument:
        path = Path(file_path)
        display_name = filename or path.name
        suffix = path.suffix.lower()
        mime_type = mimetypes.guess_type(display_name)[0]

        if suffix in self.TEXT_EXTENSIONS:
            content = path.read_text(encoding="utf-8", errors="replace")
            return ParsedDocument(
                content=content,
                metadata={
                    "filename": display_name,
                    "parser": "plain_text",
                    "extension": suffix.lstrip("."),
                    "mime_type": mime_type,
                },
            )

        try:
            from docling.datamodel.accelerator_options import AcceleratorOptions
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except Exception as exc:  # pragma: no cover - covered by integration when installed
            raise RuntimeError(
                "Docling is required for this file type. Install the `docling` package "
                "or upload a text-like file."
            ) from exc

        # On Apple Silicon, Docling's auto accelerator may pick MPS. Some PDF
        # paths still request float64 tensors, which MPS cannot represent, so
        # default to CPU for predictable ingestion.
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=PdfPipelineOptions(
                        accelerator_options=AcceleratorOptions(device="cpu")
                    )
                )
            }
        )
        result = await asyncio.to_thread(converter.convert, str(path))
        document = result.document
        if hasattr(document, "export_to_markdown"):
            content = document.export_to_markdown()
        else:
            content = str(document)

        return ParsedDocument(
            content=content,
            metadata={
                "filename": display_name,
                "parser": "docling",
                "extension": suffix.lstrip("."),
                "mime_type": mime_type,
            },
        )
