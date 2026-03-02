# 📊 KP - 주식 스크리닝 분석 시스템

> Agno 프레임워크 기반의 멀티에이전트 주식 분석 시스템.  
> MCP(Model Context Protocol) 서버를 통한 SQL 데이터 접근과 Gemini LLM을 활용한 지능형 쿼리 라우팅을 제공합니다.

---

## 🏗️ 시스템 아키텍처

```
                        ┌─────────────────────────┐
                        │     사용자 질의 (CLI)     │
                        │  --query / --interactive  │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │    ① 라우팅 에이전트      │
                        │  (SCREENING/MARKET/BOTH)  │
                        │  routing_agent.md 프롬프트  │
                        └───────────┬─────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
┌─────────▼──────────┐   ┌─────────▼──────────┐   ┌─────────▼──────────┐
│ ② 스크리닝 에이전트 │   │ ③ 마켓 데이터 에이전트│   │  ④ 통합 에이전트    │
│ (기업 정보 + 재무)  │   │   (시세 OHLCV 데이터) │   │ (결과 종합 분석)    │
│ screening_data_     │   │ market_data_         │   │ synthesizer_       │
│ agent.md 프롬프트   │   │ agent.md 프롬프트    │   │ agent.md 프롬프트   │
└─────────┬──────────┘   └─────────┬──────────┘   └────────────────────┘
          │                         │
          └────────────┬────────────┘
                       │
            ┌──────────▼──────────┐
            │   MCP 서버 (FastMCP) │
            │   Port: 8000        │
            │   Streamable HTTP   │
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │   SQLite 데이터베이스 │
            │  (CSV → DB 자동 변환) │
            │  data/financial_data │
            │        .db          │
            └─────────────────────┘

            ┌─────────────────────┐
            │  Kong 게이트웨이     │
            │  Port: 8001         │
            │  (API Key 인증 +    │
            │   Rate Limiting)    │
            └─────────────────────┘
```

---

## 🔄 전체 처리 흐름

### 1단계: 서비스 시작 (`start_services.py`)

```
Redis 실행 확인 → MCP 서버 기동 → Kong 게이트웨이 기동
```

- **Redis**: 대화 이력 및 스크리닝 결과 캐싱 (TTL: 대화 1시간, 스크리닝 24시간)
- **MCP 서버**: CSV 4개 파일을 SQLite DB로 자동 로드, 인덱스 생성
- **Kong 게이트웨이**: MCP 서버 앞단에서 API Key 인증 및 요청 제한 처리

### 2단계: 질의 처리 파이프라인

사용자의 자연어 질의가 아래 단계를 거쳐 처리됩니다:

| 단계 | 컴포넌트 | 역할 |
|------|----------|------|
| **① 라우팅** | `routing_agent` | 질의 유형을 `SCREENING` / `MARKET` / `BOTH` 중 하나로 분류 |
| **② 데이터 조회** | `screening_agent` 또는 `market_agent` | MCP 도구를 호출하여 SQLite에서 데이터 조회 |
| **③ 결과 통합** | `synthesizer_agent` | 조회 결과를 종합하여 마크다운 테이블·분석 결과로 정리 |

### 3단계: 에이전트별 상세 로직

#### ① 라우팅 에이전트 (Query Router)
- **입력**: 사용자 자연어 질의
- **출력**: `SCREENING`, `MARKET`, `BOTH` 중 하나의 단어
- **판단 기준**:
  - `SCREENING`: 기업 정보, 섹터, 재무지표(PER, PBR, ROE) 관련 질의
  - `MARKET`: 주가 이력, OHLCV, 일간 등락, 시장 요약 관련 질의
  - `BOTH`: 스크리닝 데이터와 시세 데이터 모두 필요한 복합 질의

#### ② 스크리닝 데이터 에이전트 (Screening Data Agent)
- MCP 도구를 사용하여 `company_master`, `company_metrics`, `company_income` 테이블에서 SQL 쿼리 실행
- **파생 지표 계산** (SQL 내에서 직접 계산):
  - **PER** = `price / eps`
  - **PBR** = `price / (net_income / shares)`
  - **ROE** = `(net_income / revenue) × 100`
  - **배당수익률** = `(last_dividend / price) × 100`
  - **순이익률** = `(net_income / revenue) × 100`
  - **매출총이익률** = `(gross_profit / revenue) × 100`
  - **매출 성장률** = YoY 비교 (LAG 또는 서브쿼리)
  - **EPS 성장률** = YoY 비교

#### ③ 마켓 데이터 에이전트 (Market Data Agent)
- `market_data` 테이블에서 OHLCV 시세 데이터 조회
- 주가 이력, 상승률 상위, 하락률 상위, 거래량 상위 분석

#### ④ 통합 에이전트 (Result Synthesizer)
- 심볼(symbol)을 키로 여러 테이블의 결과를 결합
- 마크다운 테이블로 정리, 계산 공식 표시
- 데이터 없는 항목은 추정하지 않음 (팩트 기반)

---

## 📁 프로젝트 구조

```
kp/
├── agents/
│   └── screening_agent.py          # 4개 에이전트 + Agno Workflow 정의
├── config/
│   └── config.yaml                 # API 키, 모델, 서버, Redis 등 전체 설정
├── data/
├── gateway/
│   └── kong_gateway.py             # API 게이트웨이 (인증/제한/프록시)
├── mcp_filesearch_server/
│   └── server.py                   # MCP 서버 (FastMCP + SQLite)
├── prompts/
│   ├── routing_agent.md            # 라우팅 에이전트 프롬프트
│   ├── screening_data_agent.md     # 스크리닝 에이전트 프롬프트
│   ├── market_data_agent.md        # 마켓 데이터 에이전트 프롬프트
│   └── synthesizer_agent.md        # 통합 에이전트 프롬프트
├── utils/
│   └── config.py                   # YAML 설정 로더 (dataclass)
├── cli.py                          # CLI 인터페이스 (테스트/질의/대화형)
├── start_services.py               # 전체 서비스 시작
├── stop_services.py                # 전체 서비스 중지
└── requirements.txt                # Python 의존성
```

---

## 📊 데이터 소스

| 테이블 | CSV 파일 | 건수 | 주요 컬럼 |
|--------|----------|------|-----------|
| `company_master` | `company_master.csv` | 142 | symbol, company_name, sector, industry, country, exchange, ceo |
| `company_metrics` | `company_metrics_daily.csv` | 142 | symbol, price, market_cap, beta, last_dividend, volume |
| `company_income` | `company_income_statements.csv` | 3,523 | symbol, fiscal_year, period(FY/Q1-Q4), revenue, net_income, eps, ebitda |
| `market_data` | `market_data_daily.csv` | 45,958 | symbol, date, open, high, low, close, volume, vwap, change_percent |

---

## 🛠️ MCP 서버 제공 도구 (7개)

MCP 서버는 SQLite 기반으로 아래 7개 도구를 에이전트에 제공합니다:

| 도구명 | 기능 |
|--------|------|
| `get_database_schema` | 전체 테이블 스키마 및 파생지표 공식 조회 |
| `query_financial_data` | SQL SELECT 쿼리 실행 (JOIN, 집계 지원, 100건 제한) |
| `search_companies` | 이름/섹터/산업/심볼로 기업 검색 |
| `get_company_info` | 심볼로 기업 전체 정보 조회 (master + metrics + income) |
| `get_stock_price_history` | 특정 종목 시세 이력 조회 (기본 30일) |
| `get_market_summary` | 시장 요약 (상승 상위, 하락 상위, 거래량 상위) |
| `get_available_symbols` | 사용 가능한 전체 심볼 목록 |

---

## 🌐 API 엔드포인트

### MCP 서버 (Port 8000)
| 경로 | 설명 |
|------|------|
| `/mcp` | MCP Streamable HTTP 엔드포인트 (에이전트가 직접 연결) |

### Kong 게이트웨이 (Port 8001)
| 경로 | 메서드 | 인증 | 설명 |
|------|--------|------|------|
| `/` | GET | 불필요 | 헬스 체크 |
| `/status` | GET | `X-API-Key` | 게이트웨이 + 업스트림 상태 |
| `/consumers` | GET | `X-Admin-Key` | 등록된 소비자 목록 (관리자) |
| `/mcp/*` | ANY | `X-API-Key` | MCP 서버 프록시 (인증 + 요청 제한) |

**요청 제한**: 분당 100건 (설정 변경 가능)

---

## 🚀 설치 및 실행 방법

### 1. 의존성 설치

```bash
# 가상환경 생성
python3 -m venv kp-env
source kp-env/bin/activate

# 패키지 설치
pip install -r requirements.txt

# Redis 설치 (Ubuntu)
sudo apt install -y redis-server
redis-server --daemonize yes
```

### 2. 설정 (`config/config.yaml`)

```yaml
api:
  gemini_api_key: "YOUR_GEMINI_API_KEY"

models:
  base_model: "gemini-2.5-flash"
  temperature: 0.3
```

### 3. 서비스 시작

```bash
# 전체 서비스 한번에 시작 (MCP 서버 + 게이트웨이)
python start_services.py
```

### 4. 사용 방법

```bash
# 단일 질의
python cli.py --query "Technology 섹터 기업 목록과 시가총액"

# 대화형 모드
python cli.py --interactive

# 테스트 실행
python cli.py --test
```

### 5. 서비스 중지

```bash
python stop_services.py
```

---

## 💡 예시 질의 및 기대 결과

### 스크리닝 질의 (기업 데이터)

| 질의 | 사용 에이전트 | 결과 |
|------|---------------|------|
| "Technology 섹터 기업 목록과 시가총액" | Screening | 기업명, 심볼, 시가총액 테이블 |
| "PER 15 미만이고 ROE 15% 이상인 종목" | Screening | 3테이블 JOIN 후 파생지표 계산 |
| "Healthcare 섹터의 PBR 계산" | Screening | master+metrics+income JOIN |
| "매출액 300억 달러 이상 Healthcare 종목" | Screening | 섹터+매출 필터링 |

### 시세 질의 (마켓 데이터)

| 질의 | 사용 에이전트 | 결과 |
|------|---------------|------|
| "AAPL 최근 10일 시세" | Market | 날짜별 OHLCV 테이블 |
| "오늘 상승률 상위 종목" | Market | 상위 5개 종목 (등락률 순) |
| "시장 요약" | Market | 상승/하락/거래량 상위 종목 |

### 복합 질의 (Both)

| 질의 | 사용 에이전트 | 결과 |
|------|---------------|------|
| "베타 1 이상 종목의 최근 가격 변동" | Both | 스크리닝+시세 결합 분석 |
| "Tech 고거래량 종목의 가격 추세" | Both | 펀더멘털+시세 종합 |

---

## ⚙️ 핵심 기술 스택

| 구분 | 기술 |
|------|------|
| **AI 프레임워크** | Agno (Agent, Workflow, Router, Step) |
| **LLM** | Google Gemini 2.5 Flash |
| **데이터 프로토콜** | MCP (Model Context Protocol) - Streamable HTTP |
| **MCP 서버** | FastMCP (SQLite 기반) |
| **API 게이트웨이** | FastAPI 기반 Kong-style Gateway |
| **데이터베이스** | SQLite (CSV 자동 변환) |
| **캐시** | Redis (대화 이력 + 결과 캐싱) |
| **비동기 처리** | asyncio, uvicorn |

---

## 📝 설정 전체 항목 (`config/config.yaml`)

| 섹션 | 항목 | 기본값 | 설명 |
|------|------|--------|------|
| `api` | `gemini_api_key` | - | Gemini API 키 |
| `models` | `base_model` | `gemini-2.5-flash` | 사용할 LLM 모델 |
| `models` | `temperature` | `0.3` | 생성 온도 |
| `models` | `max_tokens` | `10000` | 최대 토큰 수 |
| `models` | `timeout` | `600` | 요청 타임아웃(초) |
| `server` | `port` | `7778` | 메인 서버 포트 |
| `redis` | `host` / `port` | `localhost:6379` | Redis 연결 정보 |
| `redis` | `conversation_ttl` | `3600` | 대화 이력 TTL(초) |
| `redis` | `screening_ttl` | `86400` | 스크리닝 결과 TTL(초) |
| `gateway` | `port` | `8001` | 게이트웨이 포트 |
| `gateway` | `rate_limit` | `100/60s` | 요청 제한 (분당) |

