#!/usr/bin/env python3
"""
Stop all services for Financial Analysis System
"""

import os
import sys
import signal
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = Path(__file__).parent
PID_FILE = WORKSPACE / ".service_pids"


def read_pids() -> dict:
    """Read PIDs from file"""
    pids = {}
    if PID_FILE.exists():
        with open(PID_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    name, pid = line.split(':', 1)
                    pids[name] = int(pid)
    return pids


def stop_process(name: str, pid: int) -> bool:
    """Stop a process by PID"""
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info(f"Stopped {name} (PID: {pid})")
        return True
    except ProcessLookupError:
        logger.info(f"{name} (PID: {pid}) already stopped")
        return True
    except PermissionError:
        logger.error(f"Permission denied stopping {name} (PID: {pid})")
        return False
    except Exception as e:
        logger.error(f"Error stopping {name}: {e}")
        return False


def main():
    """Stop all services"""
    print("=" * 60)
    print("Stopping Financial Analysis Services")
    print("=" * 60)
    
    pids = read_pids()
    
    if not pids:
        logger.info("No services found to stop")
        
        import subprocess
        result = subprocess.run(
            ["pgrep", "-f", "mcp_filesearch_server/server.py"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            for pid in result.stdout.strip().split('\n'):
                if pid:
                    stop_process("mcp_server", int(pid))
        
        result = subprocess.run(
            ["pgrep", "-f", "gateway/kong_gateway.py"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            for pid in result.stdout.strip().split('\n'):
                if pid:
                    stop_process("gateway", int(pid))
    else:
        for name, pid in pids.items():
            stop_process(name, pid)
    
    if PID_FILE.exists():
        PID_FILE.unlink()
        logger.info(f"Removed PID file: {PID_FILE}")
    
    print("\n" + "=" * 60)
    print("All services stopped")
    print("=" * 60)


if __name__ == "__main__":
    main()
