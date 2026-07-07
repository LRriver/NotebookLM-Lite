"""Local file storage helpers for slide deck assets and exports."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from ..domain.slide_deck import SlideDeckFileKind


@dataclass(frozen=True)
class StoredSlideDeckFile:
    path: Path
    byte_size: int
    checksum: str
    download_ref: str


class SlideDeckFileStore:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)

    def save_file(
        self,
        deck_id: str,
        kind: SlideDeckFileKind,
        filename: str,
        content: bytes,
    ) -> StoredSlideDeckFile:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", deck_id):
            raise ValueError("deck_id must be a safe path segment")
        safe_name = Path(filename).name
        root = (self.output_dir / "slide_decks").resolve()
        folder = (root / deck_id / kind.value).resolve()
        if not folder.is_relative_to(root):
            raise ValueError("slide deck file path escapes output directory")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / safe_name
        path.write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()
        return StoredSlideDeckFile(
            path=path,
            byte_size=len(content),
            checksum=checksum,
            download_ref=f"slide_decks/{deck_id}/{kind.value}/{safe_name}",
        )
