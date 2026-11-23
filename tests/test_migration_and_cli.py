import json
import subprocess
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.cli import cmd_audit_verify, cmd_bundle_create, cmd_bundle_verify
from core.db.models import Base
from core.db.session import init_db
from core.migration.litellm import LiteLLMImporter
from core.storage.models import compute_directory_provenance_hash, model_registry


def test_litellm_importer_parses_models_and_detects_cloud_dependencies():
    litellm_yaml = """
model_list:
  - model_name: local-llama3
    litellm_params:
      model: vllm/meta-llama/Meta-Llama-3-8B-Instruct
      api_base: http://localhost:8000
  - model_name: cloud-azure-gpt4
    litellm_params:
      model: azure/gpt-4
      api_base: https://my-resource.openai.azure.com
router_settings:
  routing_strategy: latency-based-routing
"""
    config, unsupported = LiteLLMImporter.import_config(litellm_yaml)

    assert config["version"] == "1.0"
    assert config["routing"]["default_strategy"] == "latency-based-routing"
    assert len(config["models"]) == 2
    assert config["models"][0]["model_id"] == "local-llama3"

    assert len(unsupported) == 1
    assert "cloud-azure-gpt4" in unsupported[0]
    assert "pure air-gap mode" in unsupported[0]


def test_offline_model_registry_import_and_provenance(tmp_path):
    media_dir = tmp_path / "media_weights"
    media_dir.mkdir()
    (media_dir / "config.json").write_text('{"architectures": ["Qwen2ForCausalLM"]}', encoding="utf-8")
    (media_dir / "model.safetensors").write_bytes(b"MODEL_WEIGHT_BINARY_DATA_BLOCK")

    prov_hash = compute_directory_provenance_hash(media_dir)
    assert len(prov_hash) == 64

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(target_engine=engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)

    reg = model_registry
    reg.storage_root = tmp_path / "storage" / "models"

    with session_factory() as db:
        manifest = reg.import_model_from_media(
            source_media_path=media_dir,
            model_id="qwen-provenance-test",
            name="Qwen Provenance Test",
            min_vram_mb=4096,
            engine_type="vllm",
            db=db,
        )
        assert manifest["model_id"] == "qwen-provenance-test"
        assert manifest["provenance_sha256"] == prov_hash
        assert Path(manifest["artifact_path"]).exists()


def test_cli_subcommands():
    # Test --help invocation
    res = subprocess.run([sys.executable, "-m", "core.cli", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "bundle" in res.stdout
    assert "audit" in res.stdout
    assert "keys" in res.stdout
    assert "models" in res.stdout

    # Test audit verify
    res_audit = subprocess.run([sys.executable, "-m", "core.cli", "audit", "verify"], capture_output=True, text=True)
    assert res_audit.returncode == 0
    assert "Audit log integrity VERIFIED" in res_audit.stdout
