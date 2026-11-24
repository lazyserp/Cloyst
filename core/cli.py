"""Cloyst Unified Operator Command Line Interface (CLI).

Provides parity with the admin API and offline management commands:
- bundle: create, verify, install offline archives
- audit: verify cryptographic hash-chain integrity
- keys: mint, revoke, and verify API keys
- models: import offline model weights and inspect provenance
- status: inspect system health and node hardware
"""
from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys

from core.bundle.manager import BundleManager
from core.db.session import SessionLocal, init_db
from core.security.audit import verify_audit_chain
from core.security.keys import generate_api_key
from core.storage.models import model_registry


def cmd_bundle_create(args):
    manifest = BundleManager.create_bundle(args.output, args.sources, version=args.version)
    print(f"✅ Offline bundle successfully created: {args.output}")
    print(f"   Files packaged: {manifest.get('file_count', 0)}")


def cmd_bundle_verify(args):
    valid, err = BundleManager.verify_bundle(args.bundle)
    if valid:
        print(f"✅ Bundle integrity VERIFIED: {args.bundle} matches cryptographic manifest.")
    else:
        print(f"❌ Bundle integrity check FAILED: {err}")
        sys.exit(1)


def cmd_bundle_install(args):
    success, err = BundleManager.install_offline(args.bundle, args.dest)
    if success:
        print(f"✅ Successfully installed offline bundle into: {args.dest}")
    else:
        print(f"❌ Bundle installation failed: {err}")
        sys.exit(1)


def cmd_audit_verify(args):
    init_db()
    with SessionLocal() as db:
        valid, count, err = verify_audit_chain(db)
        if valid:
            print(f"✅ Audit log integrity VERIFIED: {count} chained records cryptographically intact.")
        else:
            print(f"❌ Audit log TAMPERING DETECTED: {err}")
            sys.exit(1)


def cmd_keys_create(args):
    init_db()
    plain, key_hash, prefix = generate_api_key()
    from core.db.models import ApiKeyRecord

    with SessionLocal() as db:
        rec = ApiKeyRecord(
            name=args.name,
            key_hash=key_hash,
            prefix=prefix,
            role=args.role,
            is_active=True,
        )
        db.add(rec)
        db.commit()

    print("✅ New API Key created successfully:")
    print(f"   Key:    {plain}")
    print(f"   Prefix: {prefix}...")
    print(f"   Role:   {args.role}")
    print("   ⚠️  Store this key securely. It will not be shown again.")


def cmd_models_import(args):
    init_db()
    with SessionLocal() as db:
        manifest = model_registry.import_model_from_media(
            source_media_path=args.source,
            model_id=args.id,
            name=args.name,
            min_vram_mb=args.min_vram,
            engine_type=args.engine,
            db=db,
        )
    print("✅ Model imported successfully:")
    print(f"   ID:         {manifest['model_id']}")
    print(f"   Name:       {manifest['name']}")
    print(f"   Provenance: {manifest['provenance_sha256']}")
    print(f"   Path:       {manifest['artifact_path']}")


def cmd_up(args):
    """One-shot launcher for both Control Plane (:8001) and AI Gateway (:8000)."""
    token = args.token or os.getenv("CLOYST_ADMIN_TOKEN") or f"cloyst_{secrets.token_hex(12)}"
    env = os.environ.copy()
    env["CLOYST_ADMIN_TOKEN"] = token

    host = args.host
    cp_port = str(args.console_port)
    gw_port = str(args.gateway_port)

    print("=" * 64)
    print("  Cloyst — Private AI Control Plane & Gateway")
    print("=" * 64)
    print(f"  Console UI  : http://{host}:{cp_port}")
    print(f"  AI Gateway  : http://{host}:{gw_port}/v1")
    print(f"  Admin Token : {token}")
    print("  Press Ctrl+C to stop both services.")
    print("=" * 64)

    cp_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "core.control_plane.app:app", "--host", host, "--port", cp_port],
        env=env,
    )
    gw_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "core.gateway.app:app", "--host", host, "--port", gw_port],
        env=env,
    )

    try:
        cp_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down Cloyst services...")
    finally:
        for proc in (cp_proc, gw_proc):
            if proc.poll() is None:
                proc.terminate()
        for proc in (cp_proc, gw_proc):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main():
    parser = argparse.ArgumentParser(prog="cloyst", description="Cloyst AI Control Plane & Gateway CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # up (one-shot launcher)
    p_up = subparsers.add_parser("up", help="Start Control Plane and AI Gateway in one command")
    p_up.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_up.add_argument("--console-port", type=int, default=8001, help="Control Plane / UI port (default: 8001)")
    p_up.add_argument("--gateway-port", type=int, default=8000, help="AI Gateway port (default: 8000)")
    p_up.add_argument("--token", default=None, help="Admin token (auto-generated if omitted)")
    p_up.set_defaults(func=cmd_up)

    # bundle
    p_bundle = subparsers.add_parser("bundle", help="Manage signed offline bundles")
    b_sub = p_bundle.add_subparsers(dest="subcommand", required=True)

    # bundle create
    p_b_create = b_sub.add_parser("create", help="Create an offline bundle archive")
    p_b_create.add_argument("output", help="Output .tar.gz bundle path")
    p_b_create.add_argument("sources", nargs="+", help="Source files or directories to include")
    p_b_create.add_argument("--version", default="0.1.0", help="Bundle version")
    p_b_create.set_defaults(func=cmd_bundle_create)

    # bundle verify
    p_b_verify = b_sub.add_parser("verify", help="Verify bundle archive integrity")
    p_b_verify.add_argument("bundle", help="Path to .tar.gz bundle")
    p_b_verify.set_defaults(func=cmd_bundle_verify)

    # bundle install
    p_b_install = b_sub.add_parser("install", help="Extract and install offline bundle")
    p_b_install.add_argument("bundle", help="Path to .tar.gz bundle")
    p_b_install.add_argument("--dest", default="./", help="Destination directory")
    p_b_install.set_defaults(func=cmd_bundle_install)

    # audit
    p_audit = subparsers.add_parser("audit", help="Manage audit records")
    a_sub = p_audit.add_subparsers(dest="subcommand", required=True)
    p_a_verify = a_sub.add_parser("verify", help="Verify audit log hash-chain integrity")
    p_a_verify.set_defaults(func=cmd_audit_verify)

    # keys
    p_keys = subparsers.add_parser("keys", help="Manage API keys")
    k_sub = p_keys.add_subparsers(dest="subcommand", required=True)
    p_k_create = k_sub.add_parser("create", help="Mint a new API key")
    p_k_create.add_argument("--name", required=True, help="Key description name")
    p_k_create.add_argument("--role", default="inference", help="Key role")
    p_k_create.set_defaults(func=cmd_keys_create)

    # models
    p_models = subparsers.add_parser("models", help="Manage model registry")
    m_sub = p_models.add_subparsers(dest="subcommand", required=True)
    p_m_import = m_sub.add_parser("import", help="Import model weights from media")
    p_m_import.add_argument("--source", required=True, help="Source model weights path")
    p_m_import.add_argument("--id", required=True, help="Model ID")
    p_m_import.add_argument("--name", required=True, help="Display name")
    p_m_import.add_argument("--min-vram", type=int, default=4096, help="Min VRAM in MB")
    p_m_import.add_argument("--engine", default="vllm", help="Engine type")
    p_m_import.set_defaults(func=cmd_models_import)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
