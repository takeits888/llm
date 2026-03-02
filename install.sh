#!/bin/bash

# Stock Screener Service Installation Script
# 주식 스크리너 서비스 설치 스크립트

set -e

echo "========================================="
echo "Stock Screener Service Installation"
echo "========================================="

# Python 버전 확인
echo "Checking Python version..."
python3 --version

# pip 업그레이드
echo "Upgrading pip..."
pip install --upgrade pip

# 가상환경 생성 (선택사항)
if [ "$1" == "--venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Virtual environment activated"
fi

# 의존성 설치
echo "Installing Python dependencies..."
pip install -r requirements.txt

# google-genai 최신 버전 확인 (file_search_stores API 지원 필요)
echo "Ensuring google-genai is up to date for file_search_stores API..."
pip install --upgrade google-genai

# Redis 설치 확인 및 시작 (선택사항)
echo "Checking Redis installation..."
if command -v redis-server &> /dev/null; then
    echo "Redis is installed"
    # Redis 서버 시작 (백그라운드)
    if ! pgrep -x "redis-server" > /dev/null; then
        echo "Starting Redis server..."
        redis-server --daemonize yes
        sleep 2
        echo "Redis server started"
    else
        echo "Redis server is already running"
    fi
else
    echo "Redis is not installed (optional for multi-turn conversations)"
    echo "To install Redis:"
    echo "  Ubuntu/Debian: sudo apt-get install -y redis-server"
    echo "  macOS: brew install redis"
fi

# 디렉토리 구조 확인
echo "Checking directory structure..."
if [ ! -d "data" ]; then
    echo "Error: data directory not found"
    exit 1
fi

if [ ! -d "config" ]; then
    echo "Error: config directory not found"
    exit 1
fi

if [ ! -d "agents" ]; then
    mkdir -p agents
    echo "Created agents directory"
fi

if [ ! -d "mcp_filesearch_server" ]; then
    mkdir -p mcp_filesearch_server
    echo "Created mcp_filesearch_server directory"
fi

# 설정 파일 확인
if [ ! -f "config/config.yaml" ]; then
    echo "Error: config/config.yaml not found"
    exit 1
fi

echo ""
echo "========================================="
echo "Installation completed successfully!"
echo "========================================="
echo ""
echo "To start the service:"
echo ""
echo "  Step 1: Start the MCP File Search server"
echo "    python3 mcp_filesearch_server/server.py"
echo ""
echo "  Step 2: In a new terminal, start the agent"
echo "    python3 agents/gemini_filesearch.py"
echo ""
echo "Or run the test suite:"
echo "  python3 test_agent.py"
echo ""
echo "MCP Server URL: http://localhost:8000/mcp"
echo ""
echo "Available MCP Tools:"
echo "  - search_financial_data: Search using Gemini File Search (cross-table queries)"
echo "  - get_company_info: Get company information"
echo "  - get_company_metrics: Get company metrics"
echo "  - get_income_statement: Get income statements"
echo "  - get_market_data: Get OHLCV market data"
echo "  - list_available_sectors: List all sectors"
echo "  - get_top_companies_by_market_cap: Get top companies"
echo "  - compare_companies: Compare multiple companies"
echo ""
