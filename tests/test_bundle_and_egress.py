import os
import tarfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from core.bundle.manager import BundleManager
from core.config import settings
from core.control_plane.app import app as cp_app
from core.gateway.app import app as gw_app
from core.observability.metrics import global_metrics
from core.security.egress import EgressBlockedError, EgressGuard


# 1. Egress Guard Air-Gap Tests
def test_egress_guard_allows_local_and_blocks_external():
    guard = EgressGuard(allowlist=["127.0.0.1", "localhost"])
    settings.air_gap_mode = True

    # Local is permitted
    assert guard.is_destination_allowed("127.0.0.1") is True
    assert guard.is_destination_allowed("http://localhost:8000/v1/models") is True

    # External internet destinations must be rejected
    assert guard.is_destination_allowed("https://api.openai.com/v1/chat") is False
    assert guard.is_destination_allowed("https://telemetry.segment.io") is False
    assert guard.is_destination_allowed("8.8.8.8") is False

    with pytest.raises(EgressBlockedError, match="Air-Gap Policy Violation"):
        guard.assert_destination_allowed("https://cdn.external.com/bundle.js")


def test_egress_guard_self_test():
    guard = EgressGuard()
    settings.air_gap_mode = True
    assert guard.run_startup_self_test() is True


# 2. Bundle Manager Packaging and Verification Tests
def test_bundle_creation_verification_and_install(tmp_path):
    # Setup sample files to package
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "config.yaml").write_text("env: airgap\n", encoding="utf-8")
    (src_dir / "model.spec").write_text("qwen-7b-int4\n", encoding="utf-8")

    bundle_tar = tmp_path / "cloyst_release_0.1.0.tar.gz"

    # Create bundle
    manifest = BundleManager.create_bundle(
        output_tar_gz=bundle_tar,
        source_paths=[src_dir / "config.yaml", src_dir / "model.spec"],
        version="0.1.0",
    )
    assert bundle_tar.exists()
    assert manifest["file_count"] == 2
    assert "config.yaml" in manifest["files"]

    # Verify bundle
    is_valid, err = BundleManager.verify_bundle(bundle_tar)
    assert is_valid is True
    assert err is None

    # Install bundle
    dest_dir = tmp_path / "installed"
    install_ok, install_err = BundleManager.install_offline(bundle_tar, dest_dir)
    assert install_ok is True
    assert install_err is None
    assert (dest_dir / "config.yaml").read_text(encoding="utf-8") == "env: airgap\n"


def test_bundle_detects_file_tampering(tmp_path):
    src_file = tmp_path / "app.conf"
    src_file.write_text("original_content", encoding="utf-8")
    bundle_tar = tmp_path / "tampered_bundle.tar.gz"

    BundleManager.create_bundle(bundle_tar, [src_file])

    # Tamper with archive by modifying file content inside
    tampered_tar = tmp_path / "tampered_mod.tar.gz"
    with tarfile.open(bundle_tar, "r:gz") as tar_in:
        manifest_f = tar_in.extractfile("manifest.json")
        manifest_data = manifest_f.read()

    with tarfile.open(tampered_tar, "w:gz") as tar_out:
        # Write modified app.conf
        bad_f = tmp_path / "bad.conf"
        bad_f.write_text("malicious_tampered_content", encoding="utf-8")
        tar_out.add(bad_f, arcname="app.conf")

        # Keep original manifest with original hash
        m_tmp = tmp_path / "manifest.json"
        m_tmp.write_bytes(manifest_data)
        tar_out.add(m_tmp, arcname="manifest.json")

    # Verification must catch checksum mismatch
    is_valid, err = BundleManager.verify_bundle(tampered_tar)
    assert is_valid is False
    assert "Checksum mismatch" in err


# 3. Prometheus Metrics Exposition Tests
def test_prometheus_metrics_endpoints():
    global_metrics.record_request_start()
    global_metrics.record_tokens("qwen-7b", 120, 45)
    global_metrics.record_request_end("qwen-7b", 200, 0.15)
    global_metrics.record_cache_hit()

    # Gateway metrics
    with TestClient(gw_app) as client:
        res = client.get("/metrics")
        assert res.status_code == 200
        text = res.text
        assert "cloyst_requests_total" in text
        assert "cloyst_tokens_total" in text
        assert "cloyst_cache_hits_total" in text

    # Control plane metrics
    with TestClient(cp_app) as client:
        res = client.get("/metrics")
        assert res.status_code == 200
        assert "cloyst_requests_total" in res.text
