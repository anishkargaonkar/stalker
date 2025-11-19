"""
Configuration settings for Stalker Engine
Using Pydantic for validation and environment management
"""

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from typing import Optional, List
import os
from pathlib import Path

class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application
    app_name: str = "Stalker Engine"
    app_version: str = "0.1.0"
    debug: bool = True
    api_port: int = 8000
    ui_port: int = 8501

    # LLM Configuration
    llm_provider: str = "openai"  # openai, anthropic, groq
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    llm_model: str = "gpt-4-turbo-preview"  # Default model
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000

    # LangSmith Tracing (Optional)
    langchain_tracing_v2: bool = False
    langchain_api_key: Optional[str] = None
    langchain_project: str = "stalker-engine"

    # Database
    database_url: str = "sqlite:///./stalker.db"

    # Redis (Optional)
    redis_url: Optional[str] = None
    use_cache: bool = True
    cache_ttl: int = 3600  # 1 hour

    # Email Configuration
    email_provider: str = "smtp"  # smtp or sendgrid
    sendgrid_api_key: Optional[str] = None
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: str = "noreply@stalker-engine.com"

    # Scraping Configuration
    firecrawl_api_key: Optional[str] = None
    use_firecrawl: bool = False
    scraping_timeout: int = 30
    max_concurrent_scrapers: int = 5

    # Search Configuration
    search_providers: List[str] = ["duckduckgo", "google"]
    max_search_results: int = 10

    # Research Settings
    research_depth: str = "medium"  # light, medium, deep
    max_research_time: int = 60  # seconds per lead
    enable_social_search: bool = True
    enable_news_search: bool = True

    # Generation Settings
    personalization_level: str = "high"  # low, medium, high
    message_style: str = "professional"  # casual, professional, formal
    include_social_proof: bool = True
    include_value_props: bool = True

    # Campaign Settings
    max_emails_per_day: int = 100
    delay_between_emails: int = 5  # seconds
    follow_up_intervals: List[int] = [3, 7, 14]  # days

    # Paths
    data_dir: Path = Path("./data")
    uploads_dir: Path = Path("./data/uploads")
    exports_dir: Path = Path("./data/exports")
    logs_dir: Path = Path("./logs")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from .env

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories if they don't exist
        for dir_path in [self.data_dir, self.uploads_dir, self.exports_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_llm_config(self):
        """Get LLM configuration based on provider"""
        if self.llm_provider == "openai":
            return {
                "api_key": self.openai_api_key,
                "model": self.llm_model or "gpt-4-turbo-preview",
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens
            }
        elif self.llm_provider == "anthropic":
            return {
                "api_key": self.anthropic_api_key,
                "model": self.llm_model or "claude-3-opus-20240229",
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens
            }
        elif self.llm_provider == "groq":
            return {
                "api_key": self.groq_api_key,
                "model": self.llm_model or "mixtral-8x7b-32768",
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens
            }
        elif self.llm_provider == "mock":
            return {
                "api_key": "mock_key",
                "model": "mock_model",
                "temperature": 0.7,
                "max_tokens": 1000
            }
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")

# Create global settings instance
settings = Settings()