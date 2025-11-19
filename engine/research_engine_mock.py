"""
Mock Research Engine for testing without external APIs
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from dataclasses import dataclass
from engine.research_engine import CompanyIntelligence, LeadProfile

logger = logging.getLogger(__name__)

class MockResearchEngine:
    """
    Mock research engine that returns sample data for testing
    """

    def __init__(self):
        logger.info("Using Mock Research Engine (no external APIs)")

    async def initialize_browser(self):
        """Mock browser initialization"""
        pass

    async def close_browser(self):
        """Mock browser cleanup"""
        pass

    async def research_company(self, company_name: str, website: Optional[str] = None) -> CompanyIntelligence:
        """Return mock company intelligence"""
        logger.info(f"[MOCK] Researching company: {company_name}")

        return CompanyIntelligence(
            company_name=company_name,
            website=website or f"https://{company_name.lower().replace(' ', '')}.com",
            description=f"{company_name} is a leading technology company focused on innovation.",
            industry="Technology",
            size="100-500 employees",
            location="San Francisco, CA",
            recent_news=[
                f"{company_name} announces new product launch",
                f"{company_name} reports record Q3 revenue",
                f"{company_name} expands to new markets"
            ],
            technologies=["Python", "React", "AWS", "Docker", "Kubernetes"],
            pain_points=[
                "Scaling infrastructure to meet demand",
                "Improving customer retention",
                "Streamlining operations"
            ],
            growth_signals=[
                "Hiring 50+ engineers",
                "Opened new office",
                "Series B funding round"
            ],
            decision_makers=[
                {"name": "John Doe", "title": "VP of Engineering"},
                {"name": "Jane Smith", "title": "Head of Sales"}
            ],
            buying_signals=[
                "Recent funding announcement",
                "Rapid headcount growth",
                "Technology stack expansion"
            ],
            competitor_mentions=["Competitor A", "Competitor B"],
            budget_indicators=["Well-funded", "High growth trajectory"],
            confidence_score=0.85,
            sources=["Mock Web Search", "Mock News API", "Mock Company Database"]
        )

    async def research_lead(self, lead: LeadProfile) -> LeadProfile:
        """Return mock enriched lead"""
        logger.info(f"[MOCK] Researching lead: {lead.name}")

        lead.bio = f"{lead.name} is an experienced professional in {lead.title or 'technology'}"
        lead.recent_activity = [
            "Posted about industry trends on LinkedIn",
            "Attended recent tech conference",
            "Shared article about innovation"
        ]
        lead.interests = ["Technology", "Innovation", "Leadership"]
        lead.engagement_score = 0.75

        return lead

    async def search_company_info(self, company_name: str) -> Dict[str, Any]:
        """Mock company search"""
        return {
            "search_results": [
                {"title": f"About {company_name}", "snippet": f"{company_name} company information"}
            ],
            "query": company_name
        }

    async def search_recent_news(self, company_name: str) -> List[Dict[str, Any]]:
        """Mock news search"""
        return [
            {
                "title": f"{company_name} Announces New Partnership",
                "body": "Breaking news about the company's latest developments",
                "url": "https://news.example.com/article1",
                "date": datetime.now().isoformat()
            }
        ]