"""Cloyst Node Agent Client & Daemon.

Runs on GPU compute nodes (Linux NVIDIA, Apple Silicon, etc.), registers hardware
specs with the Cloyst Control Plane, and publishes continuous heartbeat telemetry.
"""
from __future__ import annotations

import argparse
import logging
import os
import platform
import re
import socket
import subprocess
import sys
import threading
import time
from typing import Tuple

import httpx

from core.control_plane.schemas import NodeHeartbeatRequest, NodeRegisterRequest
from core.preflight.checker import run_preflight

logger = logging.getLogger("cloyst.agent")


def get_live_hardware_telemetry() -> Tuple[str, int, int]:
    """Inspect local hardware and return (gpu_name, total_vram_mb, free_vram_mb).

    Detection order:
    1. NVIDIA GPU via nvidia-smi
    2. Apple Silicon / Metal Unified Memory on macOS via sysctl & vm_stat
    3. Linux /proc/meminfo or system memory fallback
    """
    # 1. NVIDIA GPU
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            first_line = res.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first_line.split(",")]
            if len(parts) >= 3:
                return parts[0], int(parts[1]), int(parts[2])
    except Exception:
        pass

    # 2. Apple Silicon / macOS Metal Unified Memory
    if platform.system() == "Darwin":
        try:
            mem_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=3).strip())
            total_mb = mem_bytes // (1024 * 1024)

            free_mb = sample_apple_silicon_free_memory()
            return "Apple Silicon (Metal GPU / Unified Memory)", total_mb, free_mb
        except Exception:
            pass

    # 3. Linux /proc/meminfo fallback
    try:
        if os.path.exists("/proc/meminfo"):
            meminfo = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
            total_mb = meminfo.get("MemTotal", 0) // 1024
            free_mb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) // 1024
            return "Linux Host System Memory", total_mb, free_mb
    except Exception:
        pass

    return "Generic Compute Node", 0, 0


def sample_apple_silicon_free_memory() -> int:
    """Sample macOS virtual memory statistics to compute available unified memory in MB."""
    out = subprocess.check_output(["vm_stat"], timeout=3).decode("utf-8")
    page_size_match = re.search(r"page size of (\d+) bytes", out)
    page_size = int(page_size_match.group(1)) if page_size_match else 4096

    def _get_pages(pattern: str) -> int:
        m = re.search(rf"{pattern}:\s+(\d+)", out)
        return int(m.group(1)) if m else 0

    free_pages = _get_pages("Pages free")
    spec_pages = _get_pages("Pages speculative")
    inactive_pages = _get_pages("Pages inactive")

    free_bytes = (free_pages + spec_pages + inactive_pages) * page_size
    return free_bytes // (1024 * 1024)


def sample_live_free_vram_mb() -> int:
    """Fast, lightweight sampler to get current free VRAM/memory in MB."""
    # 1. NVIDIA
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return int(res.stdout.strip().splitlines()[0])
    except Exception:
        pass

    # 2. Apple Silicon
    if platform.system() == "Darwin":
        try:
            return sample_apple_silicon_free_memory()
        except Exception:
            pass

    # 3. Fallback
    _, _, free_mb = get_live_hardware_telemetry()
    return free_mb


class NodeAgent:
    """Agent running on GPU hosts that registers with and reports to the Control Plane."""

    def __init__(
        self,
        control_plane_url: str | None = None,
        node_id: str | None = None,
    ):
        self.control_plane_url = (
            control_plane_url
            or os.getenv("CLOYST_CONTROL_PLANE_URL")
            or "http://localhost:8001"
        )
        self.hostname = socket.gethostname()
        self.node_id = (
            node_id
            or os.getenv("CLOYST_NODE_ID")
            or f"node-{self.hostname.lower()}"
        )
        self.ip_address = self._get_local_ip()

    def _get_local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def inspect_hardware(self) -> NodeRegisterRequest:
        """Run preflight checks and convert hardware diagnostics into a registration payload."""
        preflight = run_preflight()

        gpu_name = None
        total_vram = 0
        free_vram = 0

        for check in preflight.checks:
            if check.name == "nvidia_gpu" and check.passed:
                gpu_name = check.details.get("gpu_name")
                total_vram = check.details.get("total_vram_mb", 0)
                free_vram = check.details.get("free_vram_mb", 0)

        # Fallback to dynamic hardware detection (e.g. Apple Silicon Metal or Generic Linux)
        if not gpu_name or total_vram == 0:
            gpu_name, total_vram, free_vram = get_live_hardware_telemetry()

        return NodeRegisterRequest(
            id=self.node_id,
            hostname=self.hostname,
            ip_address=self.ip_address,
            gpu_name=gpu_name,
            total_vram_mb=total_vram,
            free_vram_mb=free_vram,
        )

    def register(self) -> bool:
        """Register or update this node with the Control Plane."""
        payload = self.inspect_hardware()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{self.control_plane_url}/api/v1/nodes/register",
                    json=payload.model_dump(),
                )
                return res.status_code == 200
        except httpx.HTTPError:
            return False

    def sample_free_vram_mb(self) -> int:
        """Sample the current available VRAM or unified memory in MB."""
        return sample_live_free_vram_mb()

    def send_heartbeat(self, free_vram_mb: int | None = None) -> bool:
        """Send current health telemetry to the Control Plane."""
        if free_vram_mb is None:
            free_vram_mb = self.sample_free_vram_mb()

        payload = NodeHeartbeatRequest(free_vram_mb=free_vram_mb, status="online")
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(
                    f"{self.control_plane_url}/api/v1/nodes/{self.node_id}/heartbeat",
                    json=payload.model_dump(),
                )
                return res.status_code == 200
        except httpx.HTTPError:
            return False

    def run_daemon(
        self,
        interval_seconds: float = 5.0,
        max_iterations: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        """Continuously register and send periodic heartbeats to the Control Plane.

        Handles network dropouts with retry backoff and supports clean cancellation.
        """
        logger.info(
            "Starting Cloyst Node Agent [%s] connecting to %s (interval: %.1fs)",
            self.node_id,
            self.control_plane_url,
            interval_seconds,
        )

        # 1. Initial Registration Loop
        registered = False
        while not registered:
            if stop_event and stop_event.is_set():
                return
            registered = self.register()
            if not registered:
                logger.warning(
                    "Failed to register node with Control Plane at %s. Retrying in 5s...",
                    self.control_plane_url,
                )
                time.sleep(5.0)
            else:
                logger.info("Node [%s] successfully registered with Control Plane.", self.node_id)

        # 2. Periodic Telemetry Heartbeat Loop
        iterations = 0
        while True:
            if stop_event and stop_event.is_set():
                logger.info("Stop event received. Shutting down Node Agent.")
                break
            if max_iterations is not None and iterations >= max_iterations:
                break

            free_mb = self.sample_free_vram_mb()
            success = self.send_heartbeat(free_vram_mb=free_mb)
            if success:
                logger.info(
                    "Heartbeat acknowledged: node=%s | free_vram=%d MB",
                    self.node_id,
                    free_mb,
                )
            else:
                logger.warning(
                    "Heartbeat failed for node=%s. Control plane may be down. Retrying next cycle...",
                    self.node_id,
                )

            iterations += 1

            if stop_event:
                if stop_event.wait(timeout=interval_seconds):
                    break
            else:
                time.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloyst GPU Node Agent Daemon")
    parser.add_argument(
        "--url",
        default=os.getenv("CLOYST_CONTROL_PLANE_URL", "http://localhost:8001"),
        help="Cloyst Control Plane URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--node-id",
        default=os.getenv("CLOYST_NODE_ID", "node-local-pc"),
        help="Unique Node ID (default: node-local-pc)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Heartbeat interval in seconds (default: 5.0)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    agent = NodeAgent(control_plane_url=args.url, node_id=args.node_id)
    try:
        agent.run_daemon(interval_seconds=args.interval)
    except KeyboardInterrupt:
        logger.info("Node Agent daemon terminated by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
