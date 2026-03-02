"""
Kong-style API Gateway for MCP File Search Server
Provides API Key authentication and request proxying

Configuration loaded from config/config.yaml

Usage:
    python gateway/kong_gateway.py
"""

import sys
import time
import logging
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path

import yaml
import httpx
from fastapi import FastAPI, Request, Response, HTTPException, Header
import uvicorn

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config() -> Dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


# Load configuration
CONFIG = load_config()
GATEWAY_CONFIG = CONFIG.get("gateway", {})

# Gateway Configuration
GATEWAY_PORT = GATEWAY_CONFIG.get("port", 8001)
MCP_SERVER_URL = GATEWAY_CONFIG.get("upstream_url", "http://localhost:8000")

# API Key Store from config
API_KEYS: Dict[str, Dict] = {}
for api_key_config in GATEWAY_CONFIG.get("api_keys", []):
    key = api_key_config.get("key")
    if key:
        API_KEYS[key] = {
            "id": api_key_config.get("consumer_id", "unknown"),
            "name": api_key_config.get("name", "Unknown"),
            "api_key": key,
            "created_at": datetime.now().isoformat(),
            "requests_count": 0
        }

ADMIN_KEY = GATEWAY_CONFIG.get("admin_key", "admin-secret-key")

# Rate Limiting
RATE_LIMITS: Dict[str, Dict] = {}
RATE_LIMIT_CONFIG = GATEWAY_CONFIG.get("rate_limit", {})
RATE_LIMIT_REQUESTS = RATE_LIMIT_CONFIG.get("requests_per_minute", 100)
RATE_LIMIT_WINDOW = RATE_LIMIT_CONFIG.get("window_seconds", 60)


def validate_api_key(api_key: str) -> Optional[Dict]:
    """Validate an API key and return consumer info"""
    return API_KEYS.get(api_key)


def check_rate_limit(api_key: str) -> bool:
    """Check if the request is within rate limits"""
    now = time.time()
    
    if api_key not in RATE_LIMITS:
        RATE_LIMITS[api_key] = {"count": 0, "window_start": now}
    
    rate_info = RATE_LIMITS[api_key]
    
    if now - rate_info["window_start"] > RATE_LIMIT_WINDOW:
        rate_info["count"] = 0
        rate_info["window_start"] = now
    
    if rate_info["count"] >= RATE_LIMIT_REQUESTS:
        return False
    
    rate_info["count"] += 1
    return True


# Initialize FastAPI app
app = FastAPI(
    title="Kong-style API Gateway",
    description="API Gateway with authentication for MCP File Search Server",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    """Log startup info"""
    logger.info(f"Gateway starting on port {GATEWAY_PORT}")
    logger.info(f"Upstream: {MCP_SERVER_URL}")
    logger.info(f"Loaded {len(API_KEYS)} API keys from config")
    for key_id in API_KEYS.values():
        logger.info(f"  - Consumer: {key_id['id']} ({key_id['name']})")


@app.get("/")
async def root():
    """Gateway health check"""
    return {
        "service": "Kong-style API Gateway",
        "status": "running",
        "upstream": MCP_SERVER_URL,
        "auth": "API Key required (X-API-Key header)",
        "available_consumers": len(API_KEYS)
    }


@app.get("/consumers")
async def list_consumers(x_admin_key: str = Header(None)):
    """List all registered consumers (admin only)"""
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return {
        "consumers": [
            {"id": c["id"], "name": c["name"], "requests_count": c["requests_count"]}
            for c in API_KEYS.values()
        ]
    }


@app.api_route("/mcp{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_mcp(request: Request, path: str = "", x_api_key: str = Header(None)):
    """
    Proxy requests to MCP server with API key authentication
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header."
        )
    
    consumer = validate_api_key(x_api_key)
    if not consumer:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    if not check_rate_limit(x_api_key):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds."
        )
    
    consumer["requests_count"] += 1
    
    upstream_url = f"{MCP_SERVER_URL}/mcp{path}"
    body = await request.body()
    
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("x-api-key", None)
    headers["Accept"] = "application/json, text/event-stream"
    headers["X-Gateway"] = "Kong-style-Gateway"
    headers["X-Consumer-ID"] = consumer["id"]
    
    logger.info(f"Proxying {request.method} to {upstream_url} for consumer {consumer['id']}")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                content=body,
                params=request.query_params
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream server timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot connect to upstream server")
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=500, detail=f"Gateway error: {str(e)}")


@app.get("/status")
async def gateway_status(x_api_key: str = Header(None)):
    """Get gateway and upstream status"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    consumer = validate_api_key(x_api_key)
    if not consumer:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    upstream_healthy = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{MCP_SERVER_URL}/")
            upstream_healthy = response.status_code in [200, 404]
    except:
        pass
    
    return {
        "gateway": "healthy",
        "upstream": "healthy" if upstream_healthy else "unhealthy",
        "upstream_url": MCP_SERVER_URL,
        "consumer": {
            "id": consumer["id"],
            "name": consumer["name"],
            "requests_count": consumer["requests_count"]
        },
        "rate_limit": {
            "limit": RATE_LIMIT_REQUESTS,
            "window_seconds": RATE_LIMIT_WINDOW
        }
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Kong-style API Gateway")
    print("=" * 60)
    print(f"Gateway URL: http://localhost:{GATEWAY_PORT}")
    print(f"Upstream: {MCP_SERVER_URL}")
    print("")
    print("API Keys (from config.yaml):")
    for consumer in API_KEYS.values():
        print(f"  - {consumer['id']}: {consumer['api_key'][:20]}...")
    print("")
    print("Endpoints:")
    print("  GET  /           - Health check")
    print("  GET  /status     - Status (auth required)")
    print("  ANY  /mcp/*      - Proxy to MCP (auth required)")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)
