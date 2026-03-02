#!/usr/bin/env python3
"""
Start all services for Financial Analysis System
- MCP Server (market data SQL)
- Kong Gateway
"""

import os
import sys
import time
import signal
import subprocess
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = Path(__file__).parent
PID_FILE = WORKSPACE / ".service_pids"


def write_pids(pids: dict):
    """Write PIDs to file"""
    with open(PID_FILE, 'w') as f:
        for name, pid in pids.items():
            f.write(f"{name}:{pid}\n")


def start_mcp_server() -> subprocess.Popen:
    """Start MCP server"""
    logger.info("Starting MCP Market Data Server...")
    
    process = subprocess.Popen(
        [sys.executable, str(WORKSPACE / "mcp_filesearch_server" / "server.py")],
        cwd=str(WORKSPACE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )
    
    time.sleep(3)
    
    if process.poll() is None:
        logger.info(f"MCP Server started (PID: {process.pid})")
        return process
    else:
        logger.error("MCP Server failed to start")
        return None


def start_gateway() -> subprocess.Popen:
    """Start Kong Gateway"""
    logger.info("Starting Kong Gateway...")
    
    process = subprocess.Popen(
        [sys.executable, str(WORKSPACE / "gateway" / "kong_gateway.py")],
        cwd=str(WORKSPACE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )
    
    time.sleep(2)
    
    if process.poll() is None:
        logger.info(f"Kong Gateway started (PID: {process.pid})")
        return process
    else:
        logger.error("Kong Gateway failed to start")
        return None


def check_redis():
    """Check if Redis is running"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379)
        r.ping()
        logger.info("Redis is running")
        return True
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        logger.info("Starting Redis server...")
        subprocess.run(["redis-server", "--daemonize", "yes"], capture_output=True)
        time.sleep(1)
        try:
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            logger.info("Redis started successfully")
            return True
        except:
            logger.error("Failed to start Redis")
            return False


def main():
    """Start all services"""
    print("=" * 60)
    print("Starting Financial Analysis Services")
    print("=" * 60)
    
    if not check_redis():
        logger.error("Redis is required. Please start Redis first.")
        sys.exit(1)
    
    pids = {}
    processes = []
    
    mcp_process = start_mcp_server()
    if mcp_process:
        pids["mcp_server"] = mcp_process.pid
        processes.append(mcp_process)
    else:
        logger.error("Failed to start MCP server")
        sys.exit(1)
    
    gateway_process = start_gateway()
    if gateway_process:
        pids["gateway"] = gateway_process.pid
        processes.append(gateway_process)
    else:
        logger.warning("Gateway failed to start (optional)")
    
    write_pids(pids)
    
    print("\n" + "=" * 60)
    print("Services Started:")
    print(f"  MCP Server: http://localhost:8000 (PID: {pids.get('mcp_server', 'N/A')})")
    if "gateway" in pids:
        print(f"  Kong Gateway: http://localhost:8001 (PID: {pids['gateway']})")
    print(f"\nPID file: {PID_FILE}")
    print("\nTo stop services: python stop_services.py")
    print("To test: python cli.py --test")
    print("=" * 60)
    
    def signal_handler(sig, frame):
        print("\nShutting down services...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except:
                p.kill()
        if PID_FILE.exists():
            PID_FILE.unlink()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\nServices running. Press Ctrl+C to stop.")
    
    try:
        for process in processes:
            for line in iter(process.stdout.readline, b''):
                if line:
                    print(line.decode().strip())
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
