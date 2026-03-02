"""
MCP Server for Financial Data SQL Queries
Uses SQLite for all 4 CSV files:
- company_master.csv
- company_metrics_daily.csv
- company_income_statements.csv
- market_data_daily.csv
"""

import sys
import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

mcp = FastMCP("financial_data_server")

_config: Optional[Config] = None
_db_path: str = ""
_initialized = False


def ensure_initialized():
    """Initialize SQLite database with all 4 CSV files"""
    global _config, _db_path, _initialized
    
    if _initialized:
        return
    
    _config = Config()
    _db_path = str(Path(_config.data_dir) / "financial_data.db")
    
    logger.info("Loading CSV files into SQLite...")
    
    conn = sqlite3.connect(_db_path)
    
    # Load company_master
    master_path = Path(_config.data_dir) / _config.company_master_file
    if master_path.exists():
        df = pd.read_csv(master_path)
        df.to_sql('company_master', conn, if_exists='replace', index=False)
        logger.info(f"Loaded {len(df)} rows into company_master")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_master_symbol ON company_master(symbol)")
    
    # Load company_metrics_daily
    metrics_path = Path(_config.data_dir) / _config.metrics_daily_file
    if metrics_path.exists():
        df = pd.read_csv(metrics_path)
        df.to_sql('company_metrics', conn, if_exists='replace', index=False)
        logger.info(f"Loaded {len(df)} rows into company_metrics")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_symbol ON company_metrics(symbol)")
    
    # Load company_income_statements
    income_path = Path(_config.data_dir) / _config.income_statements_file
    if income_path.exists():
        df = pd.read_csv(income_path)
        df.to_sql('company_income', conn, if_exists='replace', index=False)
        logger.info(f"Loaded {len(df)} rows into company_income")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_income_symbol ON company_income(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_income_year ON company_income(fiscal_year)")
    
    # Load market_data_daily
    market_path = Path(_config.data_dir) / _config.market_data_file
    if market_path.exists():
        df = pd.read_csv(market_path)
        df.to_sql('market_data', conn, if_exists='replace', index=False)
        logger.info(f"Loaded {len(df)} rows into market_data")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_market_symbol ON market_data(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_market_date ON market_data(date)")
    
    conn.commit()
    conn.close()
    
    logger.info(f"SQLite database created at {_db_path}")
    _initialized = True


def execute_sql(query: str) -> list:
    """Execute SQL query and return results"""
    ensure_initialized()
    
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        results = [dict(row) for row in cursor.fetchall()]
        return results
    finally:
        conn.close()


@mcp.tool()
def get_database_schema() -> str:
    """
    Get database schema for all tables.
    
    Returns:
        Complete schema information for all tables
    """
    ensure_initialized()
    
    schema = {
        "tables": {
            "company_master": {
                "description": "Company basic information",
                "columns": {
                    "symbol": "Stock ticker symbol",
                    "company_name": "Company name",
                    "isin": "International Securities Identification Number",
                    "sector": "Business sector",
                    "industry": "Industry classification",
                    "country": "Country of incorporation",
                    "exchange": "Stock exchange",
                    "description": "Company description",
                    "ceo": "CEO name"
                }
            },
            "company_metrics": {
                "description": "Daily company metrics",
                "columns": {
                    "symbol": "Stock ticker symbol",
                    "date": "Date (YYYY-MM-DD)",
                    "price": "Stock price",
                    "market_cap": "Market capitalization",
                    "beta": "Beta coefficient",
                    "last_dividend": "Last dividend amount",
                    "volume": "Trading volume"
                }
            },
            "company_income": {
                "description": "Income statements",
                "columns": {
                    "symbol": "Stock ticker symbol",
                    "date": "Statement date",
                    "period": "Period (FY=Full Year, Q1-Q4=Quarters)",
                    "fiscal_year": "Fiscal year",
                    "revenue": "Total revenue",
                    "gross_profit": "Gross profit",
                    "net_income": "Net income",
                    "eps": "Earnings per share",
                    "ebitda": "EBITDA"
                }
            },
            "market_data": {
                "description": "Daily OHLCV market data",
                "columns": {
                    "symbol": "Stock ticker symbol",
                    "date": "Trading date (YYYY-MM-DD)",
                    "open": "Opening price",
                    "high": "Highest price",
                    "low": "Lowest price",
                    "close": "Closing price",
                    "volume": "Trading volume",
                    "vwap": "Volume weighted average price",
                    "change": "Price change",
                    "change_percent": "Price change percentage"
                }
            }
        },
        "derived_metrics": {
            "PER": "price / eps (JOIN company_metrics and company_income)",
            "dividend_yield": "(last_dividend / price) * 100",
            "net_margin": "(net_income / revenue) * 100",
            "revenue_growth": "((revenue_current - revenue_prev) / revenue_prev) * 100",
            "eps_growth": "((eps_current - eps_prev) / abs(eps_prev)) * 100"
        }
    }
    
    return json.dumps(schema, indent=2)


@mcp.tool()
def query_financial_data(sql_query: str) -> str:
    """
    Execute SQL query across all financial tables.
    Supports JOINs, aggregations, and complex queries.
    
    Tables: company_master, company_metrics, company_income, market_data
    
    Examples:
    - SELECT * FROM company_master WHERE sector = 'Technology' LIMIT 10
    - SELECT m.symbol, m.price, i.eps, (m.price/i.eps) as PER 
      FROM company_metrics m JOIN company_income i ON m.symbol = i.symbol
      WHERE i.period='FY' AND (m.price/i.eps) < 15
    
    Args:
        sql_query: SQL SELECT query
    
    Returns:
        JSON formatted query results
    """
    ensure_initialized()
    
    if not sql_query.strip().upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are allowed"})
    
    try:
        results = execute_sql(sql_query)
        return json.dumps({
            "success": True,
            "count": len(results),
            "data": results[:100],
            "note": "Limited to 100 results" if len(results) > 100 else None
        }, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"SQL error: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def search_companies(query: str, limit: int = 20) -> str:
    """
    Search companies by name, sector, or industry.
    
    Args:
        query: Search term
        limit: Maximum results (default 20)
    
    Returns:
        List of matching companies
    """
    ensure_initialized()
    
    try:
        sql = f"""
        SELECT symbol, company_name, sector, industry, country, exchange
        FROM company_master
        WHERE LOWER(company_name) LIKE LOWER('%{query}%')
           OR LOWER(sector) LIKE LOWER('%{query}%')
           OR LOWER(industry) LIKE LOWER('%{query}%')
           OR LOWER(symbol) LIKE LOWER('%{query}%')
        LIMIT {limit}
        """
        results = execute_sql(sql)
        return json.dumps({
            "query": query,
            "count": len(results),
            "companies": results
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_company_info(symbol: str) -> str:
    """
    Get complete company information by symbol.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Company details from all tables
    """
    ensure_initialized()
    
    try:
        # Get master info
        master = execute_sql(f"SELECT * FROM company_master WHERE UPPER(symbol) = UPPER('{symbol}') LIMIT 1")
        if not master:
            return json.dumps({"error": f"Company '{symbol}' not found"})
        
        # Get metrics
        metrics = execute_sql(f"SELECT * FROM company_metrics WHERE UPPER(symbol) = UPPER('{symbol}') LIMIT 1")
        
        # Get latest income statement
        income = execute_sql(f"""
            SELECT * FROM company_income 
            WHERE UPPER(symbol) = UPPER('{symbol}') AND period='FY'
            ORDER BY fiscal_year DESC LIMIT 1
        """)
        
        return json.dumps({
            "symbol": symbol.upper(),
            "master": master[0] if master else None,
            "metrics": metrics[0] if metrics else None,
            "income": income[0] if income else None
        }, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def list_sectors() -> str:
    """
    List all sectors with company counts.
    
    Returns:
        List of sectors
    """
    ensure_initialized()
    
    try:
        results = execute_sql("""
            SELECT sector, COUNT(*) as company_count
            FROM company_master
            GROUP BY sector
            ORDER BY company_count DESC
        """)
        return json.dumps({
            "sectors": results,
            "total_sectors": len(results)
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_stock_price_history(symbol: str, limit: int = 30) -> str:
    """
    Get price history for a stock.
    
    Args:
        symbol: Stock ticker symbol
        limit: Number of records (default 30)
    
    Returns:
        Price history data
    """
    ensure_initialized()
    
    try:
        results = execute_sql(f"""
            SELECT symbol, date, open, high, low, close, volume, vwap, change, change_percent
            FROM market_data
            WHERE UPPER(symbol) = UPPER('{symbol}')
            ORDER BY date DESC
            LIMIT {limit}
        """)
        
        if not results:
            return json.dumps({"error": f"No data found for '{symbol}'"})
        
        return json.dumps({
            "symbol": symbol.upper(),
            "count": len(results),
            "data": results
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_market_summary(date: str = None) -> str:
    """
    Get market summary statistics.
    
    Args:
        date: Optional date (YYYY-MM-DD), uses latest if not provided
    
    Returns:
        Market summary with top gainers, losers, and volume leaders
    """
    ensure_initialized()
    
    try:
        if not date:
            latest = execute_sql("SELECT MAX(date) as max_date FROM market_data")[0]['max_date']
            date = latest
        
        date_filter = f"WHERE date = '{date}'"
        
        gainers = execute_sql(f"""
            SELECT symbol, close, change_percent
            FROM market_data {date_filter}
            ORDER BY change_percent DESC LIMIT 5
        """)
        
        losers = execute_sql(f"""
            SELECT symbol, close, change_percent
            FROM market_data {date_filter}
            ORDER BY change_percent ASC LIMIT 5
        """)
        
        volume_leaders = execute_sql(f"""
            SELECT symbol, close, volume
            FROM market_data {date_filter}
            ORDER BY volume DESC LIMIT 5
        """)
        
        return json.dumps({
            "date": date,
            "top_gainers": gainers,
            "top_losers": losers,
            "volume_leaders": volume_leaders
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_available_symbols() -> str:
    """
    Get list of all available stock symbols.
    
    Returns:
        List of symbols
    """
    ensure_initialized()
    
    try:
        results = execute_sql("SELECT DISTINCT symbol FROM company_master ORDER BY symbol")
        symbols = [r['symbol'] for r in results]
        return json.dumps({
            "count": len(symbols),
            "symbols": symbols
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    ensure_initialized()
    
    print("=" * 60)
    print("MCP Financial Data Server (SQLite)")
    print("=" * 60)
    
    # Show table counts
    tables = ['company_master', 'company_metrics', 'company_income', 'market_data']
    for table in tables:
        try:
            count = execute_sql(f"SELECT COUNT(*) as cnt FROM {table}")[0]['cnt']
            print(f"{table}: {count} rows")
        except:
            pass
    
    print(f"Database: {_db_path}")
    print("=" * 60)
    
    mcp.run(transport="streamable-http")
