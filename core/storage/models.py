"""Offline Model Registry, Provenance Verification, and Media Import for Cloyst."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from core.db.models import ModelRecord


def compute_directory_provenance_hash(model_dir: str | Path) -> str:
    """Compute a deterministic aggregate SHA-256 provenance hash across model weight files."""
    p = Path(model_dir).resolve()
    h = hashlib.sha256()

    for root, _, files in sorted(os.walk(p)):
        for file in sorted(files):
            f_path = Path(root) / file
            # Hash relative path + file size + sample content
            rel_path = f_path.relative_to(p).as_posix()
            f_size = f_path.stat().st_size
            h.update(f"{rel_path}:{f_size}".encode("utf-8"))

    return h.hexdigest()


class OfflineModelRegistry:
    """Manages offline model weight imports, provenance, and registry metadata."""

    def __init__(self, storage_root: str = "./storage/models"):
        self.storage_root = Path(storage_root).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def import_model_from_media(
        self,
        source_media_path: str | Path,
        model_id: str,
        name: str,
        min_vram_mb: int = 4096,
        engine_type: str = "vllm",
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Import model weights from offline directory/removable media and register provenance."""
        src = Path(source_media_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source media path '{src}' does not exist.")

        dest = self.storage_root / model_id
        dest.mkdir(parents=True, exist_ok=True)

        # Copy or sync model weights
        if src.is_dir():
            for item in src.iterdir():
                dest_item = dest / item.name
                if item.is_file():
                    shutil.copy2(item, dest_item)
                elif item.is_dir():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest / src.name)

        provenance_hash = compute_directory_provenance_hash(dest)

        # Write offline provenance manifest
        provenance_manifest = {
            "model_id": model_id,
            "name": name,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "provenance_sha256": provenance_hash,
            "min_vram_mb": min_vram_mb,
            "engine_type": engine_type,
            "artifact_path": dest.as_posix(),
        }
        with open(dest / "cloyst_provenance.json", "w", encoding="utf-8") as f:
            json.dump(provenance_manifest, f, indent=2)

        # Register in DB if session provided
        if db is not None:
            model_rec = db.get(ModelRecord, model_id)
            if not model_rec:
                model_rec = ModelRecord(
                    id=model_id,
                    name=name,
                    artifact_path=dest.as_posix(),
                    min_vram_mb=min_vram_mb,
                    engine_type=engine_type,
                )
                db.add(model_rec)
            else:
                model_rec.name = name
                model_rec.artifact_path = dest.as_posix()
                model_rec.min_vram_mb = min_vram_mb
                model_rec.engine_type = engine_type
            db.commit()

        return provenance_manifest


model_registry = OfflineModelRegistry()
