#!/usr/bin/env python3
"""
CLI for Financial Analysis System
Cross-table queries using MCP SQL and Agno Workflow
"""

import sys
import asyncio
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.screening_agent import StockScreeningWorkflow, run_query
from utils.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


CROSS_TABLE_TEST_QUERIES = [
    {
        "query": "Find Technology sector companies and their current market cap",
        "description": "Screening: sector + market_cap from company_master and metrics",
    },
    {
        "query": "Show me the price history for AAPL for the last 10 days",
        "description": "Market: Price history from market_data",
    },
    {
        "query": "Find Healthcare sector stocks with revenue over 30 billion",
        "description": "Screening: sector + revenue from master and income statements",
    },
    {
        "query": "Calculate PBR for all Technology companies",
        "description": "Screening: Cross-table PBR calculation",
    },
    {
        "query": "Find stocks with ROE over 15% and PER under 20",
        "description": "Screening: Complex metrics with cross-table joins",
    },
]


async def run_tests():
    """Run cross-table test queries"""
    print("=" * 60)
    print("Cross-Table Query Test Suite")
    print("=" * 60)
    
    config = Config()
    workflow = StockScreeningWorkflow(config)
    
    try:
        await workflow.initialize()
        
        passed = 0
        failed = 0
        
        for i, test_case in enumerate(CROSS_TABLE_TEST_QUERIES, 1):
            print(f"\n{'='*60}")
            print(f"Test {i}/{len(CROSS_TABLE_TEST_QUERIES)}: {test_case['description']}")
            print(f"Query: {test_case['query']}")
            print("-" * 60)
            
            try:
                result = await workflow.run(test_case['query'])
                
                if result and len(result) > 50:
                    print(f"\nResponse:\n{result[:1000]}...")
                    print("\n[PASS] Query returned substantive response")
                    passed += 1
                else:
                    print(f"\nResponse: {result}")
                    print("\n[FAIL] Response too short or empty")
                    failed += 1
                    
            except Exception as e:
                print(f"\n[FAIL] Error: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
            
            await asyncio.sleep(1)
        
        print("\n" + "=" * 60)
        print(f"Test Results: {passed} passed, {failed} failed")
        print("=" * 60)
        
        return failed == 0
        
    finally:
        await workflow.cleanup()


async def run_single_query(query: str):
    """Run a single query"""
    print("=" * 60)
    print("Stock Screening System - Single Query")
    print("=" * 60)
    print(f"\nQuery: {query}")
    print("-" * 60)
    
    try:
        result = await run_query(query)
        print(f"\nResponse:\n{result}")
        return True
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_interactive():
    """Run interactive mode"""
    print("=" * 60)
    print("Stock Screening System - Interactive Mode")
    print("=" * 60)
    print("\nCommands:")
    print("  Type your query to search")
    print("  'quit' or 'exit' to exit")
    print("-" * 60)
    
    config = Config()
    workflow = StockScreeningWorkflow(config)
    
    try:
        await workflow.initialize()
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if not query:
                    continue
                    
                if query.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye!")
                    break
                
                result = await workflow.run(query)
                print("\n" + "-" * 60)
                print(result)
                print("-" * 60)
                
            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
                
    finally:
        await workflow.cleanup()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Stock Screening CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --test
  python cli.py --query "Find Technology stocks with PBR under 3"
  python cli.py --query "Calculate ROE for Healthcare sector"
  python cli.py --interactive
  python cli.py -q "Show AAPL price history"
        """
    )
    
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Run cross-table query tests"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Run a single query"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive mode"
    )
    
    args = parser.parse_args()
    
    if args.test:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    elif args.query:
        success = asyncio.run(run_single_query(args.query))
        sys.exit(0 if success else 1)
    elif args.interactive:
        asyncio.run(run_interactive())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
