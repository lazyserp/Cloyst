"""Helper script to register a locally running Ollama model into Sovra's database.

Usage:
    python scripts/register_ollama.py [model_name] [port]
Example:
    python scripts/register_ollama.py qwen2.5:0.5b 11434
"""
import platform
import subprocess
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db.models import DeploymentRecord, ModelRecord, NodeRecord
from core.db.session import SessionLocal, init_db

def get_system_specs():
    """Detect local hardware: Apple Silicon / Metal unified memory or Linux fallback."""
    if platform.system() == "Darwin":
        try:
            mem_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
            total_mb = mem_bytes // (1024 * 1024)
        except Exception:
            total_mb = 16384
        # Assume ~5.2 GB used by 7B model and system cache
        return "Apple Silicon (Metal GPU / Unified Memory)", total_mb, max(0, total_mb - 5200)

    return "Generic Linux Node", 8192, 4096

def register_ollama(model_name: str = "qwen2.5:0.5b", port: int = 11434):
    init_db()
    gpu_name, total_vram, free_vram = get_system_specs()
    hostname = platform.node() or "local-rig"

    with SessionLocal() as db:
        # 1. Register or update the local compute node
        node = db.get(NodeRecord, "node-local-pc")
        if not node:
            node = NodeRecord(
                id="node-local-pc",
                hostname=hostname,
                ip_address="127.0.0.1",
                gpu_name=gpu_name,
                total_vram_mb=total_vram,
                free_vram_mb=free_vram,
                status="online",
            )
            db.add(node)
        else:
            node.hostname = hostname
            node.gpu_name = gpu_name
            node.total_vram_mb = total_vram
            node.free_vram_mb = free_vram
            node.status = "online"

        # 2. Register the model metadata
        model = db.get(ModelRecord, model_name)
        if not model:
            model = ModelRecord(
                id=model_name,
                name="Qwen 2.5 (Local Engine)",
                artifact_path=f"ollama://{model_name}",
                min_vram_mb=5500 if "7b" in model_name else 400,
                engine_type="ollama",
            )
            db.add(model)
        else:
            if "7b" in model_name:
                model.min_vram_mb = 5500

        # 3. Register or activate the deployment
        deploy = db.get(DeploymentRecord, f"deploy-{model_name.replace(':', '-')}")
        if not deploy:
            deploy = DeploymentRecord(
                id=f"deploy-{model_name.replace(':', '-')}",
                model_id=model_name,
                node_id="node-local-pc",
                port=port,
                status="running",
            )
            db.add(deploy)
        else:
            deploy.status = "running"
            deploy.port = port

        db.commit()
        print("✅ Successfully registered deployment in Sovra:")
        print(f"   Model: {model_name}")
        print(f"   Port:  {port}")
        print(f"   Node:  node-local-pc ({gpu_name})")
        print(f"   VRAM:  {total_vram - free_vram} / {total_vram} MB")
        print("   Status: running")

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:0.5b"
    p = int(sys.argv[2]) if len(sys.argv) > 2 else 11434
    register_ollama(m, p)
