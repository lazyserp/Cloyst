from unittest.mock import MagicMock, patch
import httpx
import pytest

from core.agents.client import NodeAgent
from core.preflight.models import CheckItem, PreflightResult


def test_agent_inspect_hardware():
    """Verify agent inspects hardware and maps preflight results to registration payload."""
    agent = NodeAgent(node_id="test-node-01")

    mock_gpu_check = CheckItem(
        name="nvidia_gpu",
        passed=True,
        message="GPU Verified",
        details={
            "gpu_name": "NVIDIA GeForce RTX 3050 Laptop GPU",
            "total_vram_mb": 4096,
            "free_vram_mb": 3962,
        },
    )
    mock_preflight = PreflightResult(passed=True, checks=[mock_gpu_check])

    with patch("core.agents.client.run_preflight", return_value=mock_preflight):
        payload = agent.inspect_hardware()
        assert payload.id == "test-node-01"
        assert payload.gpu_name == "NVIDIA GeForce RTX 3050 Laptop GPU"
        assert payload.total_vram_mb == 4096
        assert payload.free_vram_mb == 3962
        assert len(payload.ip_address) > 0


def test_agent_register_success():
    """Verify agent returns True when registration succeeds."""
    agent = NodeAgent(control_plane_url="http://control-plane:8000")
    mock_res = MagicMock(status_code=200)

    with patch("httpx.Client.post", return_value=mock_res), \
         patch.object(agent, "inspect_hardware"):
        assert agent.register() is True


def test_agent_register_network_error():
    """Verify agent returns False instead of crashing when Control Plane is offline."""
    agent = NodeAgent(control_plane_url="http://offline-server:8000")

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")), \
         patch.object(agent, "inspect_hardware"):
        assert agent.register() is False


def test_agent_send_heartbeat_success():
    """Verify agent sends periodic telemetry."""
    agent = NodeAgent(control_plane_url="http://control-plane:8000", node_id="node-test")
    mock_res = MagicMock(status_code=200)

    with patch("httpx.Client.post", return_value=mock_res):
        assert agent.send_heartbeat(free_vram_mb=3500) is True


def test_agent_live_hardware_inspection():
    """Live verification that the agent can inspect the local machine hardware."""
    agent = NodeAgent()
    payload = agent.inspect_hardware()
    assert payload.id.startswith("node-")
    assert len(payload.hostname) > 0
    assert payload.ip_address != ""
    assert isinstance(payload.total_vram_mb, int)
    assert payload.total_vram_mb >= 0


def test_agent_sample_free_vram():
    """Verify sample_free_vram_mb returns a non-negative integer."""
    agent = NodeAgent()
    free_mb = agent.sample_free_vram_mb()
    assert isinstance(free_mb, int)
    assert free_mb >= 0


def test_agent_run_daemon_max_iterations():
    """Verify daemon executes the specified number of cycles and exits cleanly."""
    import threading
    agent = NodeAgent(control_plane_url="http://control-plane:8000", node_id="node-test")

    with patch.object(agent, "register", return_value=True) as mock_reg, \
         patch.object(agent, "send_heartbeat", return_value=True) as mock_hb:
        agent.run_daemon(interval_seconds=0.01, max_iterations=3)
        assert mock_reg.call_count == 1
        assert mock_hb.call_count == 3


def test_agent_run_daemon_stop_event():
    """Verify daemon honors a threading.Event stop signal."""
    import threading
    agent = NodeAgent(control_plane_url="http://control-plane:8000", node_id="node-test")
    stop_event = threading.Event()
    stop_event.set()  # Stop immediately

    with patch.object(agent, "register", return_value=True) as mock_reg, \
         patch.object(agent, "send_heartbeat", return_value=True) as mock_hb:
        agent.run_daemon(interval_seconds=0.01, stop_event=stop_event)
        # Should exit immediately without hanging
        assert mock_hb.call_count == 0


