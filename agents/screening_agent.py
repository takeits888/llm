"""
Stock Screening Agent using Agno Framework
- All data access through MCP tool calling
- MCP server provides tools for: company_master, company_metrics, company_income, market_data
- Agno Workflow with Router for intelligent query routing
- LLM calculates derived metrics (PER, PBR, ROE, etc.)
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.mcp import MCPTools
from agno.workflow import Workflow, Router, Step

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MCP_SERVER_URL = "http://localhost:8000/mcp"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    """Load prompt from MD file"""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {prompt_path}")
        return ""
    return prompt_path.read_text()


class ScreeningDataAgent:
    """Stock screening agent using MCP tools for data access"""
    
    def __init__(self, config: Config):
        self.config = config
        self._agent: Optional[Agent] = None
        self._mcp_tools: Optional[MCPTools] = None
    
    async def initialize(self) -> Agent:
        """Initialize agent with MCP tools"""
        self._mcp_tools = MCPTools(
            transport="streamable-http",
            url=MCP_SERVER_URL,
            timeout_seconds=60,
        )
        
        await self._mcp_tools.connect()
        logger.info(f"Connected to MCP server at {MCP_SERVER_URL}")
        
        instructions = load_prompt("screening_data_agent.md")
        
        self._agent = Agent(
            id="screening-data-agent",
            name="Screening Data Agent",
            model=Gemini(
                id=self.config.base_model,
                api_key=self.config.gemini_api_key
            ),
            tools=[self._mcp_tools],
            instructions=instructions,
            markdown=True,
            debug_mode=False,
        )
        
        logger.info("Screening Data Agent initialized with MCP tools")
        return self._agent
    
    async def cleanup(self):
        """Cleanup MCP connection"""
        if self._mcp_tools:
            try:
                await self._mcp_tools.close()
            except Exception:
                pass
    
    @property
    def agent(self) -> Optional[Agent]:
        return self._agent


class MarketDataAgent:
    """Agent for market OHLCV data queries"""
    
    def __init__(self, config: Config):
        self.config = config
        self._agent: Optional[Agent] = None
        self._mcp_tools: Optional[MCPTools] = None
    
    async def initialize(self) -> Agent:
        """Initialize market data agent with MCP tools"""
        self._mcp_tools = MCPTools(
            transport="streamable-http",
            url=MCP_SERVER_URL,
            timeout_seconds=60,
        )
        
        await self._mcp_tools.connect()
        logger.info(f"Connected to MCP server at {MCP_SERVER_URL}")
        
        instructions = load_prompt("market_data_agent.md")
        
        self._agent = Agent(
            id="market-data-agent",
            name="Market Data Agent",
            model=Gemini(
                id=self.config.base_model,
                api_key=self.config.gemini_api_key
            ),
            tools=[self._mcp_tools],
            instructions=instructions,
            markdown=True,
            debug_mode=False,
        )
        
        logger.info("Market Data Agent initialized")
        return self._agent
    
    async def cleanup(self):
        """Cleanup MCP connection"""
        if self._mcp_tools:
            try:
                await self._mcp_tools.close()
            except Exception:
                pass
    
    @property
    def agent(self) -> Optional[Agent]:
        return self._agent


async def create_routing_agent(config: Config) -> Agent:
    """Create routing agent to determine query type"""
    instructions = load_prompt("routing_agent.md")
    
    return Agent(
        id="routing-agent",
        name="Query Router",
        model=Gemini(
            id=config.base_model,
            api_key=config.gemini_api_key
        ),
        instructions=instructions,
        markdown=False,
        debug_mode=False,
    )


async def create_synthesizer_agent(config: Config) -> Agent:
    """Create synthesizer agent to combine results"""
    instructions = load_prompt("synthesizer_agent.md")
    
    return Agent(
        id="synthesizer-agent",
        name="Result Synthesizer",
        model=Gemini(
            id=config.base_model,
            api_key=config.gemini_api_key
        ),
        instructions=instructions,
        markdown=True,
        debug_mode=False,
    )


class StockScreeningWorkflow:
    """Stock Screening System using Agno Workflow with Router"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.screening_agent_wrapper = ScreeningDataAgent(self.config)
        self.market_agent_wrapper = MarketDataAgent(self.config)
        self.routing_agent: Optional[Agent] = None
        self.synthesizer_agent: Optional[Agent] = None
        self.workflow: Optional[Workflow] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize all agents and workflow"""
        if self._initialized:
            return
        
        logger.info("Initializing Stock Screening Workflow...")
        
        # Initialize agents
        await self.screening_agent_wrapper.initialize()
        await self.market_agent_wrapper.initialize()
        self.routing_agent = await create_routing_agent(self.config)
        self.synthesizer_agent = await create_synthesizer_agent(self.config)
        
        # Create Steps
        routing_step = Step(
            name="routing_step",
            agent=self.routing_agent
        )
        
        screening_step = Step(
            name="screening_step",
            agent=self.screening_agent_wrapper.agent
        )
        
        market_step = Step(
            name="market_step",
            agent=self.market_agent_wrapper.agent
        )
        
        synthesizer_step = Step(
            name="synthesizer_step",
            agent=self.synthesizer_agent
        )
        
        # Router selector function
        def route_selector(response):
            """Extract routing decision from response"""
            if hasattr(response, 'messages') and response.messages:
                content = response.messages[-1].content.strip().upper()
            elif hasattr(response, 'get_content_as_string'):
                content = response.get_content_as_string().strip().upper()
            elif hasattr(response, 'content'):
                content = response.content.strip().upper()
            else:
                content = str(response).strip().upper()
            
            logger.info(f"Router decision: {content}")
            
            # Return Step object based on routing decision
            if "SCREENING" in content and "MARKET" not in content and "BOTH" not in content:
                return screening_step
            elif "MARKET" in content and "SCREENING" not in content and "BOTH" not in content:
                return market_step
            else:
                return screening_step  # Default to screening for BOTH
        
        # Create Workflow with synthesizer at the end
        self.workflow = Workflow(
            id="stock-screening-workflow",
            name="Stock Screening Workflow",
            description="Routes queries to appropriate agents for stock screening and analysis",
            steps=[
                routing_step,
                Router(
                    name="query_router",
                    selector=route_selector,
                    choices=[screening_step, market_step],
                    description="Routes to screening or market data agent based on query type",
                ),
                synthesizer_step,  # Add synthesizer at the end
            ],
            debug_mode=False,
            store_events=True,
        )
        
        self._initialized = True
        logger.info("Stock Screening Workflow initialized")
    
    async def run(self, query: str) -> str:
        """Run query through the workflow"""
        if not self._initialized:
            await self.initialize()
        
        logger.info(f"Running query: {query}")
        
        # Run workflow
        result = await self.workflow.arun(query)
        
        # Extract result
        if hasattr(result, 'get_content_as_string'):
            return result.get_content_as_string()
        elif hasattr(result, 'content'):
            return result.content
        else:
            return str(result)
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.screening_agent_wrapper.cleanup()
        await self.market_agent_wrapper.cleanup()
        self._initialized = False


async def run_query(query: str, config: Optional[Config] = None) -> str:
    """Run a single query through the workflow"""
    workflow = StockScreeningWorkflow(config)
    try:
        await workflow.initialize()
        return await workflow.run(query)
    finally:
        await workflow.cleanup()


async def run_interactive():
    """Run interactive CLI session"""
    print("=" * 60)
    print("Stock Screening System - Interactive Mode")
    print("=" * 60)
    print("\nThis system uses MCP tools for all data access:")
    print("  - Company info, sector, industry (company_master)")
    print("  - Metrics: price, market_cap, beta (company_metrics)")
    print("  - Income: revenue, net_income, EPS (company_income)")
    print("  - Market data: OHLCV prices (market_data)")
    print("\nDerived metrics: PER, PBR, ROE, margins, growth rates")
    print("\nType 'quit' to exit.\n")
    
    workflow = StockScreeningWorkflow()
    await workflow.initialize()
    
    try:
        while True:
            try:
                query = input("\nYour query: ").strip()
                
                if not query:
                    continue
                    
                if query.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye!")
                    break
                
                print("\n" + "-" * 60)
                result = await workflow.run(query)
                print(result)
                print("-" * 60)
                
            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
                
    finally:
        await workflow.cleanup()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Stock Screening System")
    parser.add_argument("--query", "-q", type=str, help="Run a single query")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    print("\n" + "!" * 60)
    print("IMPORTANT: Make sure MCP server is running first!")
    print("Run: python mcp_filesearch_server/server.py")
    print("!" * 60 + "\n")
    
    if args.query:
        result = asyncio.run(run_query(args.query))
        print(result)
    else:
        asyncio.run(run_interactive())
