#!/usr/bin/env python3
"""Run the Sovra Node Agent Daemon.

Usage:
    python scripts/run_agent.py [--url http://localhost:8001] [--node-id node-local-pc] [--interval 5]
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agents.client import main

if __name__ == "__main__":
    main()

