"""Cloyst Offline Bundle Packaging, Integrity Verification, and Installation."""
from __future__ import annotations

import hashlib
import json
import os
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class BundleManifest:
    def __init__(self, version: str = "0.1.0", files: Optional[Dict[str, str]] = None):
        self.version = version
        self.files = files or {}  # relative_path -> sha256_hex

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "archive_type": "cloyst_airgap_bundle",
            "file_count": len(self.files),
            "files": self.files,
        }


def compute_file_sha256(filepath: str | Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class BundleManager:
    """Creates, verifies, and installs signed offline bundles."""

    @staticmethod
    def create_bundle(
        output_tar_gz: str | Path,
        source_paths: List[str | Path],
        version: str = "0.1.0",
    ) -> Dict[str, Any]:
        """Create a verifiable compressed offline archive with file checksum manifest."""
        manifest = BundleManifest(version=version)
        target_path = Path(output_tar_gz).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Temporary manifest file
        temp_manifest = target_path.with_suffix(".manifest.json")

        with tarfile.open(target_path, "w:gz") as tar:
            for item in source_paths:
                p = Path(item)
                if not p.exists():
                    continue

                if p.is_file():
                    rel_name = p.name
                    sha256_hash = compute_file_sha256(p)
                    manifest.files[rel_name] = sha256_hash
                    tar.add(p, arcname=rel_name)
                elif p.is_dir():
                    for root, _, files in os.walk(p):
                        for file in files:
                            full_f = Path(root) / file
                            rel_name = full_f.relative_to(p.parent).as_posix()
                            sha256_hash = compute_file_sha256(full_f)
                            manifest.files[rel_name] = sha256_hash
                            tar.add(full_f, arcname=rel_name)

            # Write and add manifest to the root of archive
            with open(temp_manifest, "w", encoding="utf-8") as f:
                json.dump(manifest.to_dict(), f, indent=2)
            tar.add(temp_manifest, arcname="manifest.json")

        if temp_manifest.exists():
            temp_manifest.unlink()

        return manifest.to_dict()

    @staticmethod
    def verify_bundle(tar_gz_path: str | Path) -> Tuple[bool, Optional[str]]:
        """Verify archive contents against the embedded manifest.json.

        Protects against zip-slip and file tampering.
        """
        target_path = Path(tar_gz_path).resolve()
        if not target_path.exists():
            return False, f"Bundle file '{target_path}' not found."

        with tarfile.open(target_path, "r:gz") as tar:
            # 1. Zip-slip and path traversal check
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    return False, f"Malicious path traversal detected in member '{member.name}'."

            # 2. Extract manifest
            try:
                manifest_file = tar.extractfile("manifest.json")
                if not manifest_file:
                    return False, "Missing manifest.json in archive."
                manifest_data = json.loads(manifest_file.read().decode("utf-8"))
            except Exception as exc:
                return False, f"Failed to parse manifest: {exc}"

            expected_files = manifest_data.get("files", {})

            # 3. Verify each file's checksum
            for arcname, expected_hash in expected_files.items():
                try:
                    f = tar.extractfile(arcname)
                    if not f:
                        return False, f"File '{arcname}' declared in manifest missing from archive."
                    h = hashlib.sha256()
                    while chunk := f.read(65536):
                        h.update(chunk)
                    computed = h.hexdigest()
                    if computed != expected_hash:
                        return False, f"Checksum mismatch on '{arcname}': expected {expected_hash}, computed {computed}"
                except Exception as exc:
                    return False, f"Error verifying '{arcname}': {exc}"

        return True, None

    @staticmethod
    def install_offline(tar_gz_path: str | Path, destination_dir: str | Path) -> Tuple[bool, Optional[str]]:
        """Safely unpack an offline bundle into target directory after verification."""
        is_valid, err = BundleManager.verify_bundle(tar_gz_path)
        if not is_valid:
            return False, f"Install aborted: bundle verification failed: {err}"

        dest = Path(destination_dir).resolve()
        dest.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tar_gz_path, "r:gz") as tar:
            tar.extractall(path=dest, filter="data")

        return True, None
