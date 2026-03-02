"""
Configuration module for Stock Screener Agent
Loads all configuration from config/config.yaml
"""

import logging
from pathlib import Path
from dataclasses import dataclass

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration loaded from config/config.yaml"""
    
    # API Configuration
    gemini_api_key: str = ""
    
    # Model Configuration
    base_model: str = ""
    temperature: float = 0.0
    max_tokens: int = 0
    timeout: int = 0
    
    # Server Configuration
    server_host: str = ""
    server_port: int = 0
    log_level: str = ""
    
    # Redis Configuration
    redis_host: str = ""
    redis_port: int = 0
    redis_db: int = 0
    conversation_ttl: int = 0
    screening_ttl: int = 0
    
    # Data Configuration
    data_dir: str = ""
    company_master_file: str = ""
    income_statements_file: str = ""
    metrics_daily_file: str = ""
    market_data_file: str = ""
    summary_file: str = ""
    
    # File Search Configuration
    file_search_store_name: str = ""
    upload_timeout: int = 0
    poll_interval: int = 0
    
    def __post_init__(self):
        self._load_from_yaml()
    
    def _load_from_yaml(self):
        """Load all configuration from config.yaml"""
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # API configuration
        api_config = config_data.get('api', {})
        self.gemini_api_key = api_config.get('gemini_api_key', '')
        
        # Model configuration
        model_config = config_data.get('models', {})
        self.base_model = model_config.get('base_model', 'gemini-2.5-flash')
        self.temperature = model_config.get('temperature', 0.3)
        self.max_tokens = model_config.get('max_tokens', 10000)
        self.timeout = model_config.get('timeout', 600)
        
        # Server configuration
        server_config = config_data.get('server', {})
        self.server_host = server_config.get('host', '0.0.0.0')
        self.server_port = server_config.get('port', 7778)
        self.log_level = server_config.get('log_level', 'info')
        
        # Redis configuration
        redis_config = config_data.get('redis', {})
        self.redis_host = redis_config.get('host', 'localhost')
        self.redis_port = redis_config.get('port', 6379)
        self.redis_db = redis_config.get('db', 0)
        self.conversation_ttl = redis_config.get('conversation_ttl', 3600)
        self.screening_ttl = redis_config.get('screening_ttl', 86400)
        
        # Data configuration
        data_config = config_data.get('data', {})
        self.data_dir = data_config.get('data_dir', 'data')
        self.company_master_file = data_config.get('company_master_file', 'company_master.csv')
        self.income_statements_file = data_config.get('income_statements_file', 'company_income_statements.csv')
        self.metrics_daily_file = data_config.get('metrics_daily_file', 'company_metrics_daily.csv')
        self.market_data_file = data_config.get('market_data_file', 'market_data_daily.csv')
        self.summary_file = data_config.get('summary_file', 'financial_data_summary.txt')
        
        # File Search configuration
        file_search_config = config_data.get('file_search', {})
        self.file_search_store_name = file_search_config.get('store_name', 'financial-data-store')
        self.upload_timeout = file_search_config.get('upload_timeout', 120)
        self.poll_interval = file_search_config.get('poll_interval', 5)
        
        # Reconfigure logging based on config
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)
        
        logger.info(f"Configuration loaded: model={self.base_model}, port={self.server_port}")
