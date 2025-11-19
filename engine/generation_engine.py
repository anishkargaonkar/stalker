"""
Message Generation Engine inspired by SalesGPT
Generates hyper-personalized outreach messages based on research
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from enum import Enum

from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.chains import LLMChain
from langchain.schema import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from engine.llm_manager import get_llm_manager
from engine.research_engine import CompanyIntelligence, LeadProfile

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Types of messages we can generate"""
    COLD_EMAIL = "cold_email"
    FOLLOW_UP = "follow_up"
    LINKEDIN = "linkedin"
    CALL_SCRIPT = "call_script"
    SMS = "sms"
    PROPOSAL = "proposal"

class SalesStage(Enum):
    """Sales stages inspired by SalesGPT"""
    INTRODUCTION = "introduction"
    QUALIFICATION = "qualification"
    NEEDS_ANALYSIS = "needs_analysis"
    VALUE_PROPOSITION = "value_proposition"
    OBJECTION_HANDLING = "objection_handling"
    CLOSING = "closing"
    FOLLOW_UP = "follow_up"

class GeneratedMessage(BaseModel):
    """Structure for generated messages"""
    subject: Optional[str] = Field(None, description="Email subject line")
    body: str = Field(description="Message body")
    call_to_action: str = Field(description="Clear CTA")
    personalization_hooks: List[str] = Field(default_factory=list, description="Personalization elements used")
    stage: str = Field(description="Sales stage")
    confidence: float = Field(default=0.0, description="Confidence score")
    alternative_versions: List[str] = Field(default_factory=list, description="Alternative versions")

class GenerationEngine:
    """
    Advanced message generation using research insights
    Inspired by SalesGPT's conversational approach
    """

    def __init__(self):
        self.llm_manager = get_llm_manager()

    async def generate_outreach(
        self,
        lead: LeadProfile,
        company: CompanyIntelligence,
        message_type: MessageType = MessageType.COLD_EMAIL,
        stage: SalesStage = SalesStage.INTRODUCTION,
        product_info: Optional[Dict[str, Any]] = None,
        previous_interactions: Optional[List[str]] = None
    ) -> GeneratedMessage:
        """Generate personalized outreach message"""

        # Select appropriate generation strategy
        if message_type == MessageType.COLD_EMAIL:
            return await self._generate_cold_email(lead, company, stage, product_info)
        elif message_type == MessageType.LINKEDIN:
            return await self._generate_linkedin_message(lead, company, stage, product_info)
        elif message_type == MessageType.FOLLOW_UP:
            return await self._generate_follow_up(lead, company, previous_interactions, product_info)
        elif message_type == MessageType.CALL_SCRIPT:
            return await self._generate_call_script(lead, company, stage, product_info)
        else:
            return await self._generate_generic_message(lead, company, message_type, stage, product_info)

    async def _generate_cold_email(
        self,
        lead: LeadProfile,
        company: CompanyIntelligence,
        stage: SalesStage,
        product_info: Optional[Dict[str, Any]]
    ) -> GeneratedMessage:
        """Generate cold email with SalesGPT-style personalization"""

        # Build context from research
        context = self._build_context(lead, company, product_info)

        # Create prompt based on stage
        prompt = self._get_stage_prompt(stage).format(
            lead_name=lead.name,
            lead_title=lead.title or "there",
            company_name=company.company_name,
            **context
        )

        system_prompt = """You are a top-performing sales professional crafting highly personalized cold emails.
Your emails should:
1. Start with a compelling, personalized opening based on recent company news or achievements
2. Quickly establish relevance and value
3. Be concise (under 150 words)
4. Include a clear, low-commitment call-to-action
5. Sound natural and conversational, not salesy
6. Reference specific pain points or opportunities from research

Generate 3 versions with different angles, and identify the personalization hooks used."""

        # Generate message
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]

        response = await self.llm_manager.llm.ainvoke(messages)

        # Parse response and create structured message
        generated_message = self._parse_email_response(response.content, stage)

        # Add personalization hooks from research
        generated_message.personalization_hooks = self._extract_personalization_hooks(context, company)

        return generated_message

    async def _generate_linkedin_message(
        self,
        lead: LeadProfile,
        company: CompanyIntelligence,
        stage: SalesStage,
        product_info: Optional[Dict[str, Any]]
    ) -> GeneratedMessage:
        """Generate LinkedIn message"""

        context = self._build_context(lead, company, product_info)

        prompt = f"""Write a brief LinkedIn message to {lead.name} at {company.company_name}.

Context:
- Their role: {lead.title or 'Unknown'}
- Recent company news: {', '.join(company.recent_news[:2]) if company.recent_news else 'None'}
- Growth signals: {', '.join(company.growth_signals[:2]) if company.growth_signals else 'None'}
- Our value prop: {product_info.get('value_prop', 'Help companies scale') if product_info else 'Help companies scale'}

The message should:
1. Be under 300 characters
2. Reference something specific about them or their company
3. Not pitch immediately
4. Focus on starting a conversation
5. Be genuinely helpful or interesting"""

        response = await self.llm_manager.llm.ainvoke(prompt)

        return GeneratedMessage(
            body=response.content,
            call_to_action="Would love to connect and share insights",
            stage=stage.value,
            confidence=0.85,
            personalization_hooks=self._extract_personalization_hooks(context, company)
        )

    async def _generate_follow_up(
        self,
        lead: LeadProfile,
        company: CompanyIntelligence,
        previous_interactions: Optional[List[str]],
        product_info: Optional[Dict[str, Any]]
    ) -> GeneratedMessage:
        """Generate follow-up message based on previous interactions"""

        context = self._build_context(lead, company, product_info)

        # Include previous interaction context
        prev_context = "\n".join(previous_interactions[-3:]) if previous_interactions else "No previous interaction"

        prompt = f"""Create a follow-up email to {lead.name} at {company.company_name}.

Previous Interaction:
{prev_context}

New Information:
- Recent company developments: {', '.join(company.recent_news[:2]) if company.recent_news else 'None'}
- Identified pain points: {', '.join(company.pain_points[:2]) if company.pain_points else 'None'}

The follow-up should:
1. Reference our previous conversation naturally
2. Provide new value or insights
3. Not be pushy
4. Move the conversation forward
5. Be under 100 words"""

        response = await self.llm_manager.llm.ainvoke(prompt)

        return GeneratedMessage(
            subject=f"Re: Quick thought on {company.company_name}'s growth",
            body=response.content,
            call_to_action="Would 15 minutes next week work to explore this?",
            stage=SalesStage.FOLLOW_UP.value,
            confidence=0.9,
            personalization_hooks=self._extract_personalization_hooks(context, company)
        )

    async def _generate_call_script(
        self,
        lead: LeadProfile,
        company: CompanyIntelligence,
        stage: SalesStage,
        product_info: Optional[Dict[str, Any]]
    ) -> GeneratedMessage:
        """Generate call script with objection handling"""

        context = self._build_context(lead, company, product_info)

        prompt = f"""Create a call script for reaching {lead.name} at {company.company_name}.

Key Information:
- Role: {lead.title or 'Decision Maker'}
- Company focus: {company.description[:200] if company.description else 'Unknown'}
- Pain points: {', '.join(company.pain_points[:3]) if company.pain_points else 'Unknown'}
- Our solution: {product_info.get('value_prop', 'Business solution') if product_info else 'Business solution'}

Create a script with:
1. Strong opening (10 seconds)
2. Permission to continue
3. Value prop tied to their specific situation
4. Discovery questions
5. Common objections and responses
6. Next steps

Keep it conversational and under 2 minutes for the main flow."""

        response = await self.llm_manager.llm.ainvoke(prompt)

        return GeneratedMessage(
            body=response.content,
            call_to_action="Schedule a detailed discussion",
            stage=stage.value,
            confidence=0.8,
            personalization_hooks=self._extract_personalization_hooks(context, company)
        )

    async def _generate_generic_message(
        self,
        lead: LeadProfile,
        company: CompanyIntelligence,
        message_type: MessageType,
        stage: SalesStage,
        product_info: Optional[Dict[str, Any]]
    ) -> GeneratedMessage:
        """Fallback for other message types"""

        context = self._build_context(lead, company, product_info)

        prompt = f"""Generate a {message_type.value} message for {lead.name} at {company.company_name}.

Context:
{json.dumps(context, indent=2)}

The message should be appropriate for the {stage.value} stage and be highly personalized."""

        response = await self.llm_manager.llm.ainvoke(prompt)

        return GeneratedMessage(
            body=response.content,
            call_to_action="Let's discuss further",
            stage=stage.value,
            confidence=0.7,
            personalization_hooks=self._extract_personalization_hooks(context, company)
        )

    def _build_context(
        self,
        lead: LeadProfile,
        company: CompanyIntelligence,
        product_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build context for message generation"""

        context = {
            "lead_info": {
                "name": lead.name,
                "title": lead.title,
                "bio": lead.bio,
                "recent_activity": lead.recent_activity
            },
            "company_info": {
                "name": company.company_name,
                "industry": company.industry,
                "size": company.size,
                "description": company.description[:500] if company.description else None,
                "recent_news": company.recent_news[:3],
                "pain_points": company.pain_points[:3],
                "growth_signals": company.growth_signals[:3],
                "technologies": company.technologies[:5],
                "buying_signals": company.buying_signals[:3]
            }
        }

        if product_info:
            context["product"] = product_info

        return context

    def _get_stage_prompt(self, stage: SalesStage) -> str:
        """Get stage-specific prompt template"""

        prompts = {
            SalesStage.INTRODUCTION: """Create a cold email to {lead_name}, {lead_title} at {company_name}.

Use this research to personalize:
{company_info}

Focus on:
1. Grabbing attention with specific, relevant insight about their company
2. Establishing credibility quickly
3. Soft introduction of how we might help
4. Easy CTA to start conversation""",

            SalesStage.QUALIFICATION: """Create an email to {lead_name} at {company_name} to qualify their needs.

Research insights:
{company_info}

Focus on:
1. Understanding their current challenges
2. Identifying decision-making process
3. Budget and timeline indicators
4. Technical requirements""",

            SalesStage.VALUE_PROPOSITION: """Create an email to {lead_name} at {company_name} presenting our value proposition.

Their situation:
{company_info}

Focus on:
1. Directly address identified pain points
2. Provide specific examples of value
3. Include relevant case studies or results
4. Clear demonstration of ROI""",

            SalesStage.OBJECTION_HANDLING: """Create an email to {lead_name} at {company_name} addressing potential objections.

Context:
{company_info}

Address common objections:
1. Budget constraints
2. Timing concerns
3. Integration complexity
4. Stakeholder buy-in""",

            SalesStage.CLOSING: """Create an email to {lead_name} at {company_name} to close the deal.

Situation:
{company_info}

Focus on:
1. Summarize value and fit
2. Create urgency (if genuine)
3. Clear next steps
4. Remove remaining friction"""
        }

        return prompts.get(stage, prompts[SalesStage.INTRODUCTION])

    def _parse_email_response(self, response: str, stage: SalesStage) -> GeneratedMessage:
        """Parse LLM response into structured message"""

        # Simple parsing - in production, use structured output
        lines = response.strip().split('\n')

        # Try to extract subject line
        subject = None
        body_lines = []
        alternatives = []

        for line in lines:
            if line.startswith("Subject:"):
                subject = line.replace("Subject:", "").strip()
            elif line.startswith("Version") or line.startswith("Alternative"):
                alternatives.append(line)
            else:
                body_lines.append(line)

        body = '\n'.join(body_lines).strip()

        # Extract CTA (usually last sentence)
        sentences = body.split('.')
        cta = sentences[-1].strip() if sentences else "Let's connect"

        return GeneratedMessage(
            subject=subject or f"Quick question about {stage.value}",
            body=body,
            call_to_action=cta,
            stage=stage.value,
            confidence=0.85,
            alternative_versions=alternatives[:2]
        )

    def _extract_personalization_hooks(
        self,
        context: Dict[str, Any],
        company: CompanyIntelligence
    ) -> List[str]:
        """Extract what personalization elements were used"""

        hooks = []

        if company.recent_news:
            hooks.append(f"Recent news: {company.recent_news[0][:50]}")

        if company.growth_signals:
            hooks.append(f"Growth signal: {company.growth_signals[0][:50]}")

        if company.pain_points:
            hooks.append(f"Pain point: {company.pain_points[0][:50]}")

        if company.technologies:
            hooks.append(f"Tech stack: {', '.join(company.technologies[:3])}")

        if company.buying_signals:
            hooks.append(f"Buying signal: {company.buying_signals[0][:50]}")

        return hooks[:5]  # Limit to top 5 hooks

    async def generate_campaign_sequence(
        self,
        lead: LeadProfile,
        company: CompanyIntelligence,
        campaign_type: str = "standard",
        num_messages: int = 4
    ) -> List[GeneratedMessage]:
        """Generate a full campaign sequence"""

        sequence = []
        stages = [
            SalesStage.INTRODUCTION,
            SalesStage.VALUE_PROPOSITION,
            SalesStage.OBJECTION_HANDLING,
            SalesStage.CLOSING
        ]

        for i, stage in enumerate(stages[:num_messages]):
            # Add delay for rate limiting
            if i > 0:
                import asyncio
                await asyncio.sleep(1)

            message = await self.generate_outreach(
                lead=lead,
                company=company,
                message_type=MessageType.COLD_EMAIL if i == 0 else MessageType.FOLLOW_UP,
                stage=stage,
                previous_interactions=[m.body for m in sequence] if sequence else None
            )

            sequence.append(message)

        return sequence