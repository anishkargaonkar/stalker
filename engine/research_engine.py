"""
Research Engine combining approaches from:
- AI Company Researcher (mayooear)
- GPT-Researcher (assafelovic)
- Sales Outreach Automation (kaymen99)
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from dataclasses import dataclass, asdict

# Web scraping
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
from bs4 import BeautifulSoup
try:
    import newspaper
except ImportError:
    newspaper = None
try:
    from trafilatura import fetch_url, extract
except ImportError:
    fetch_url = None
    extract = None

# Search
try:
    from duckduckgo_search import AsyncDDGS
except ImportError:
    from duckduckgo_search import DDGS
    AsyncDDGS = None
import httpx

# LangChain
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from engine.llm_manager import get_llm_manager

logger = logging.getLogger(__name__)

class CompanyIntelligence(BaseModel):
    """Structure for company research output"""
    company_name: str = Field(description="Company name")
    website: str = Field(description="Company website")
    description: str = Field(description="Company description")
    industry: str = Field(description="Industry/vertical")
    size: str = Field(description="Company size/employees")
    location: str = Field(description="Headquarters location")

    # Intelligence
    recent_news: List[str] = Field(default_factory=list, description="Recent news and announcements")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")
    pain_points: List[str] = Field(default_factory=list, description="Potential pain points")
    growth_signals: List[str] = Field(default_factory=list, description="Growth indicators")

    # Key people
    decision_makers: List[Dict[str, str]] = Field(default_factory=list, description="Key decision makers")

    # Sales intelligence
    buying_signals: List[str] = Field(default_factory=list, description="Buying signals detected")
    competitor_mentions: List[str] = Field(default_factory=list, description="Competitor mentions")
    budget_indicators: List[str] = Field(default_factory=list, description="Budget/funding indicators")

    # Metadata
    research_date: str = Field(default_factory=lambda: datetime.now().isoformat())
    confidence_score: float = Field(default=0.0, description="Research confidence 0-1")
    sources: List[str] = Field(default_factory=list, description="Data sources used")

@dataclass
class LeadProfile:
    """Individual lead profile"""
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None

    # Enriched data
    bio: Optional[str] = None
    recent_activity: List[str] = None
    interests: List[str] = None
    engagement_score: float = 0.0

class ResearchEngine:
    """
    Multi-source research engine inspired by top OSS projects
    Combines web scraping, search, and LLM analysis
    """

    def __init__(self):
        self.llm_manager = get_llm_manager()
        if AsyncDDGS:
            self.ddgs = AsyncDDGS()
        else:
            self.ddgs = DDGS()
        self.browser = None
        self.context = None
        self.page = None

    async def initialize_browser(self):
        """Initialize Playwright browser for dynamic scraping"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available, skipping browser initialization")
            return
        if not self.browser:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self.page = await self.context.new_page()

    async def close_browser(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
            self.browser = None

    async def research_company(self, company_name: str, website: Optional[str] = None) -> CompanyIntelligence:
        """
        Deep research on a company using multiple sources
        Inspired by AI Company Researcher approach
        """
        logger.info(f"Starting research on {company_name}")

        # Parallel research tasks
        tasks = [
            self.search_company_info(company_name),
            self.search_recent_news(company_name),
            self.scrape_website(website) if website else asyncio.create_task(self._empty_dict()),
            self.search_social_mentions(company_name),
            self.search_job_postings(company_name),
            self.search_funding_info(company_name)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine all research data
        combined_data = {
            "company_info": results[0] if not isinstance(results[0], Exception) else {},
            "recent_news": results[1] if not isinstance(results[1], Exception) else [],
            "website_data": results[2] if not isinstance(results[2], Exception) else {},
            "social_mentions": results[3] if not isinstance(results[3], Exception) else [],
            "job_postings": results[4] if not isinstance(results[4], Exception) else [],
            "funding_info": results[5] if not isinstance(results[5], Exception) else {}
        }

        # Analyze with LLM
        intelligence = await self.analyze_company_data(company_name, combined_data)

        # Calculate confidence score
        intelligence.confidence_score = self._calculate_confidence(combined_data)

        return intelligence

    async def search_company_info(self, company_name: str) -> Dict[str, Any]:
        """Search for basic company information"""
        try:
            query = f"{company_name} company profile overview headquarters employees"
            results = await self.ddgs.atext(query, max_results=5)

            # Extract key information
            info = {
                "search_results": results,
                "query": query
            }

            return info
        except Exception as e:
            logger.error(f"Company search failed: {e}")
            return {}

    async def search_recent_news(self, company_name: str) -> List[Dict[str, Any]]:
        """Search for recent news about the company"""
        try:
            query = f"{company_name} news announcement funding product launch 2024"
            results = await self.ddgs.anews(query, max_results=10)

            news_items = []
            for item in results:
                news_items.append({
                    "title": item.get("title", ""),
                    "body": item.get("body", ""),
                    "url": item.get("url", ""),
                    "date": item.get("date", "")
                })

            return news_items
        except Exception as e:
            logger.error(f"News search failed: {e}")
            return []

    async def scrape_website(self, url: str) -> Dict[str, Any]:
        """Scrape company website for information"""
        if not url:
            return {}

        try:
            # Try trafilatura first (faster)
            downloaded = fetch_url(url)
            content = extract(downloaded, include_links=True, include_images=False)

            if content:
                return {
                    "url": url,
                    "content": content[:5000],  # Limit content size
                    "method": "trafilatura"
                }

            # Fallback to Playwright for dynamic content
            await self.initialize_browser()
            await self.page.goto(url, wait_until="networkidle", timeout=15000)

            # Extract relevant sections
            page_data = await self.page.evaluate("""
                () => {
                    const getText = (selector) => {
                        const element = document.querySelector(selector);
                        return element ? element.innerText : '';
                    };

                    return {
                        title: document.title,
                        description: getText('meta[name="description"]'),
                        h1: getText('h1'),
                        about: getText('[class*="about"], [id*="about"]'),
                        products: getText('[class*="product"], [id*="product"]'),
                        team: getText('[class*="team"], [id*="team"]')
                    };
                }
            """)

            return {
                "url": url,
                "data": page_data,
                "method": "playwright"
            }

        except Exception as e:
            logger.error(f"Website scraping failed for {url}: {e}")
            return {"url": url, "error": str(e)}

    async def search_social_mentions(self, company_name: str) -> List[Dict[str, Any]]:
        """Search for social media mentions and discussions"""
        try:
            # Search for social mentions
            query = f"{company_name} site:linkedin.com OR site:twitter.com OR site:reddit.com"
            results = await self.ddgs.atext(query, max_results=10)

            mentions = []
            for item in results:
                mentions.append({
                    "platform": self._extract_platform(item.get("href", "")),
                    "title": item.get("title", ""),
                    "body": item.get("body", ""),
                    "url": item.get("href", "")
                })

            return mentions
        except Exception as e:
            logger.error(f"Social search failed: {e}")
            return []

    async def search_job_postings(self, company_name: str) -> List[Dict[str, Any]]:
        """Search for job postings to understand growth and tech stack"""
        try:
            query = f"{company_name} careers hiring jobs opening"
            results = await self.ddgs.atext(query, max_results=5)

            jobs = []
            for item in results:
                jobs.append({
                    "title": item.get("title", ""),
                    "description": item.get("body", ""),
                    "url": item.get("href", "")
                })

            return jobs
        except Exception as e:
            logger.error(f"Job search failed: {e}")
            return []

    async def search_funding_info(self, company_name: str) -> Dict[str, Any]:
        """Search for funding and financial information"""
        try:
            query = f"{company_name} funding round investment valuation series"
            results = await self.ddgs.atext(query, max_results=5)

            funding_data = {
                "search_results": results,
                "query": query
            }

            return funding_data
        except Exception as e:
            logger.error(f"Funding search failed: {e}")
            return {}

    async def analyze_company_data(self, company_name: str, data: Dict[str, Any]) -> CompanyIntelligence:
        """Use LLM to analyze and structure company data"""

        # Create analysis prompt
        prompt = PromptTemplate(
            template="""Analyze the following research data about {company_name} and extract key intelligence.

Research Data:
{research_data}

Based on this data, provide a comprehensive analysis including:
1. Company overview (name, website, industry, size, location)
2. Recent news and developments
3. Technologies they use or might need
4. Potential pain points they might be facing
5. Growth signals and expansion indicators
6. Key decision makers if mentioned
7. Buying signals (hiring, funding, expansion, new initiatives)
8. Any competitor mentions
9. Budget or funding indicators

Format the response as a detailed JSON object with the following structure:
{{
    "company_name": "",
    "website": "",
    "description": "",
    "industry": "",
    "size": "",
    "location": "",
    "recent_news": [],
    "technologies": [],
    "pain_points": [],
    "growth_signals": [],
    "decision_makers": [],
    "buying_signals": [],
    "competitor_mentions": [],
    "budget_indicators": []
}}

Be specific and extract actual facts from the data. If information is not available, use empty values.
""",
            input_variables=["company_name", "research_data"]
        )

        # Prepare data for analysis
        research_summary = json.dumps(data, indent=2, default=str)[:8000]  # Limit size

        # Generate analysis
        llm = self.llm_manager.llm
        chain = LLMChain(llm=llm, prompt=prompt)

        try:
            response = await chain.ainvoke({
                "company_name": company_name,
                "research_data": research_summary
            })

            # Parse JSON response
            analysis = json.loads(response["text"])

            # Create CompanyIntelligence object
            intelligence = CompanyIntelligence(
                company_name=analysis.get("company_name", company_name),
                website=analysis.get("website", ""),
                description=analysis.get("description", ""),
                industry=analysis.get("industry", ""),
                size=analysis.get("size", ""),
                location=analysis.get("location", ""),
                recent_news=analysis.get("recent_news", []),
                technologies=analysis.get("technologies", []),
                pain_points=analysis.get("pain_points", []),
                growth_signals=analysis.get("growth_signals", []),
                decision_makers=analysis.get("decision_makers", []),
                buying_signals=analysis.get("buying_signals", []),
                competitor_mentions=analysis.get("competitor_mentions", []),
                budget_indicators=analysis.get("budget_indicators", []),
                sources=self._extract_sources(data)
            )

            return intelligence

        except json.JSONDecodeError:
            # Fallback to basic intelligence if JSON parsing fails
            return CompanyIntelligence(
                company_name=company_name,
                description="Research completed but analysis parsing failed",
                sources=self._extract_sources(data)
            )

    async def research_lead(self, lead: LeadProfile) -> LeadProfile:
        """Research an individual lead"""
        # Search for lead information
        query = f"{lead.name} {lead.title or ''} {lead.company or ''}"

        try:
            results = await self.ddgs.atext(query, max_results=5)

            # Extract bio and activity
            bio_parts = []
            activities = []

            for result in results:
                text = result.get("body", "")
                if lead.name.lower() in text.lower():
                    bio_parts.append(text[:200])
                    if any(keyword in text.lower() for keyword in ["posted", "shared", "announced", "joined"]):
                        activities.append(text[:150])

            lead.bio = " ".join(bio_parts[:2]) if bio_parts else None
            lead.recent_activity = activities[:3]

            # Calculate engagement score based on findings
            lead.engagement_score = min(1.0, len(results) * 0.2)

        except Exception as e:
            logger.error(f"Lead research failed for {lead.name}: {e}")

        return lead

    def _extract_platform(self, url: str) -> str:
        """Extract platform name from URL"""
        if "linkedin.com" in url:
            return "LinkedIn"
        elif "twitter.com" in url or "x.com" in url:
            return "Twitter/X"
        elif "reddit.com" in url:
            return "Reddit"
        elif "facebook.com" in url:
            return "Facebook"
        else:
            return "Web"

    def _extract_sources(self, data: Dict[str, Any]) -> List[str]:
        """Extract all sources used in research"""
        sources = []

        # Add search sources
        if "company_info" in data and data["company_info"]:
            sources.append("DuckDuckGo Search")

        if "website_data" in data and data["website_data"]:
            sources.append(f"Website: {data['website_data'].get('url', 'Unknown')}")

        if "recent_news" in data and data["recent_news"]:
            sources.append("News Search")

        if "social_mentions" in data and data["social_mentions"]:
            sources.append("Social Media")

        return sources

    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """Calculate confidence score based on data completeness"""
        score = 0.0
        weights = {
            "company_info": 0.2,
            "website_data": 0.2,
            "recent_news": 0.2,
            "social_mentions": 0.15,
            "job_postings": 0.15,
            "funding_info": 0.1
        }

        for key, weight in weights.items():
            if key in data and data[key]:
                score += weight

        return min(1.0, score)

    async def _empty_dict(self):
        """Helper to return empty dict for async gather"""
        return {}