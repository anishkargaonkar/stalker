"""
LangGraph-based Orchestrator for the Stalker Engine
Manages the complete sales pipeline workflow
"""

import asyncio
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime
import logging
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from engine.research_engine import ResearchEngine, CompanyIntelligence, LeadProfile
from engine.generation_engine import GenerationEngine, MessageType, SalesStage, GeneratedMessage
from engine.llm_manager import get_llm_manager

logger = logging.getLogger(__name__)

class WorkflowState(TypedDict):
    """State for the sales workflow"""
    # Input
    leads: List[LeadProfile]
    campaign_config: Dict[str, Any]

    # Processing
    current_lead_index: int
    researched_companies: Dict[str, CompanyIntelligence]
    generated_messages: Dict[str, List[GeneratedMessage]]
    sent_messages: List[Dict[str, Any]]

    # Status
    status: str
    errors: List[str]
    metrics: Dict[str, Any]

class WorkflowStatus(Enum):
    """Workflow status states"""
    INITIALIZED = "initialized"
    RESEARCHING = "researching"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"

class StalkerOrchestrator:
    """
    Main orchestrator using LangGraph for complex workflows
    Inspired by Sales Outreach Automation (kaymen99)
    """

    def __init__(self):
        # Use mock engine if in mock mode
        from config.settings import settings
        if settings.llm_provider == "mock":
            from engine.research_engine_mock import MockResearchEngine
            self.research_engine = MockResearchEngine()
        else:
            self.research_engine = ResearchEngine()
        self.generation_engine = GenerationEngine()
        self.llm_manager = get_llm_manager()
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""

        # Create workflow graph
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("validate_input", self.validate_input)
        workflow.add_node("research_lead", self.research_lead)
        workflow.add_node("generate_messages", self.generate_messages)
        workflow.add_node("review_quality", self.review_quality)
        workflow.add_node("send_messages", self.send_messages)
        workflow.add_node("track_metrics", self.track_metrics)

        # Add edges
        workflow.add_edge("validate_input", "research_lead")
        workflow.add_edge("research_lead", "generate_messages")
        workflow.add_edge("generate_messages", "review_quality")

        # Conditional edge from review
        workflow.add_conditional_edges(
            "review_quality",
            self.should_send,
            {
                "send": "send_messages",
                "regenerate": "generate_messages",
                "skip": "track_metrics"
            }
        )

        workflow.add_edge("send_messages", "track_metrics")

        # Check if more leads
        workflow.add_conditional_edges(
            "track_metrics",
            self.has_more_leads,
            {
                "continue": "research_lead",
                "end": END
            }
        )

        # Set entry point
        workflow.set_entry_point("validate_input")

        return workflow.compile()

    async def validate_input(self, state: WorkflowState) -> WorkflowState:
        """Validate input data"""
        logger.info(f"Validating {len(state['leads'])} leads")

        if not state.get("leads"):
            state["status"] = WorkflowStatus.FAILED.value
            state["errors"] = ["No leads provided"]
            return state

        # Initialize state
        state["current_lead_index"] = 0
        state["researched_companies"] = {}
        state["generated_messages"] = {}
        state["sent_messages"] = []
        state["status"] = WorkflowStatus.INITIALIZED.value
        state["errors"] = []
        state["metrics"] = {
            "total_leads": len(state["leads"]),
            "processed": 0,
            "messages_generated": 0,
            "messages_sent": 0,
            "start_time": datetime.now().isoformat()
        }

        return state

    async def research_lead(self, state: WorkflowState) -> WorkflowState:
        """Research current lead and company"""
        current_index = state["current_lead_index"]

        if current_index >= len(state["leads"]):
            return state

        lead = state["leads"][current_index]
        logger.info(f"Researching lead {current_index + 1}/{len(state['leads'])}: {lead.name}")

        state["status"] = WorkflowStatus.RESEARCHING.value

        try:
            # Research company if not already done
            company_key = lead.company or lead.name

            if company_key not in state["researched_companies"]:
                company_intel = await self.research_engine.research_company(
                    company_name=lead.company or lead.name,
                    website=None  # Could be extracted from lead data
                )
                state["researched_companies"][company_key] = company_intel
            else:
                company_intel = state["researched_companies"][company_key]

            # Research individual lead
            enriched_lead = await self.research_engine.research_lead(lead)
            state["leads"][current_index] = enriched_lead

            # Update metrics
            state["metrics"]["last_research_time"] = datetime.now().isoformat()
            state["metrics"]["companies_researched"] = len(state["researched_companies"])

        except Exception as e:
            logger.error(f"Research failed for {lead.name}: {e}")
            state["errors"].append(f"Research failed for {lead.name}: {str(e)}")

        return state

    async def generate_messages(self, state: WorkflowState) -> WorkflowState:
        """Generate personalized messages for current lead"""
        current_index = state["current_lead_index"]

        if current_index >= len(state["leads"]):
            return state

        lead = state["leads"][current_index]
        company_key = lead.company or lead.name

        logger.info(f"Generating messages for {lead.name}")
        state["status"] = WorkflowStatus.GENERATING.value

        try:
            # Get company intelligence
            company = state["researched_companies"].get(company_key)

            if not company:
                logger.warning(f"No company intelligence for {lead.name}, using basic generation")
                company = CompanyIntelligence(
                    company_name=lead.company or "Unknown",
                    description="Limited information available"
                )

            # Generate message sequence based on campaign config
            campaign_config = state.get("campaign_config", {})
            message_type = MessageType[campaign_config.get("message_type", "COLD_EMAIL").upper()]
            num_messages = campaign_config.get("num_follow_ups", 3) + 1

            # Generate campaign sequence
            messages = await self.generation_engine.generate_campaign_sequence(
                lead=lead,
                company=company,
                campaign_type=campaign_config.get("campaign_type", "standard"),
                num_messages=num_messages
            )

            # Store generated messages
            lead_key = f"{lead.name}_{lead.company or 'unknown'}"
            state["generated_messages"][lead_key] = messages

            # Update metrics
            state["metrics"]["messages_generated"] += len(messages)
            state["metrics"]["last_generation_time"] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Generation failed for {lead.name}: {e}")
            state["errors"].append(f"Generation failed for {lead.name}: {str(e)}")

        return state

    async def review_quality(self, state: WorkflowState) -> WorkflowState:
        """Review generated messages for quality"""
        current_index = state["current_lead_index"]

        if current_index >= len(state["leads"]):
            return state

        lead = state["leads"][current_index]
        lead_key = f"{lead.name}_{lead.company or 'unknown'}"

        logger.info(f"Reviewing message quality for {lead.name}")
        state["status"] = WorkflowStatus.REVIEWING.value

        try:
            messages = state["generated_messages"].get(lead_key, [])

            if not messages:
                logger.warning(f"No messages to review for {lead.name}")
                return state

            # Quality check using LLM
            for message in messages:
                quality_prompt = f"""Review this sales message for quality:

Subject: {message.subject if message.subject else 'N/A'}
Body: {message.body}

Rate on:
1. Personalization (1-10)
2. Clarity (1-10)
3. Call-to-action strength (1-10)
4. Professional tone (1-10)
5. Length appropriateness (1-10)

Provide an overall score and any critical issues.
Format: SCORE: X/50 | ISSUES: [list any] | PASS: yes/no"""

                review = await self.llm_manager.llm.ainvoke(quality_prompt)
                review_text = review.content if hasattr(review, 'content') else str(review)

                # Parse review (simple extraction)
                if "PASS: yes" in review_text:
                    message.confidence = 0.9
                elif "PASS: no" in review_text:
                    message.confidence = 0.3
                else:
                    message.confidence = 0.7

                # Extract score if present
                if "SCORE:" in review_text:
                    try:
                        score_text = review_text.split("SCORE:")[1].split("|")[0]
                        score = int(score_text.split("/")[0].strip())
                        message.confidence = score / 50.0
                    except:
                        pass

            # Update metrics
            state["metrics"]["messages_reviewed"] = state["metrics"].get("messages_reviewed", 0) + len(messages)
            avg_confidence = sum(m.confidence for m in messages) / len(messages) if messages else 0
            state["metrics"][f"quality_score_{lead_key}"] = avg_confidence

        except Exception as e:
            logger.error(f"Review failed for {lead.name}: {e}")
            state["errors"].append(f"Review failed for {lead.name}: {str(e)}")

        return state

    def should_send(self, state: WorkflowState) -> str:
        """Decide whether to send, regenerate, or skip"""
        current_index = state["current_lead_index"]

        if current_index >= len(state["leads"]):
            return "skip"

        lead = state["leads"][current_index]
        lead_key = f"{lead.name}_{lead.company or 'unknown'}"
        messages = state["generated_messages"].get(lead_key, [])

        if not messages:
            return "skip"

        # Check average confidence
        avg_confidence = sum(m.confidence for m in messages) / len(messages) if messages else 0

        # Decision logic
        if avg_confidence >= 0.7:
            return "send"
        elif avg_confidence >= 0.5 and state["metrics"].get("regeneration_count", 0) < 2:
            state["metrics"]["regeneration_count"] = state["metrics"].get("regeneration_count", 0) + 1
            return "regenerate"
        else:
            return "skip"

    async def send_messages(self, state: WorkflowState) -> WorkflowState:
        """Send messages (or queue for sending)"""
        current_index = state["current_lead_index"]

        if current_index >= len(state["leads"]):
            return state

        lead = state["leads"][current_index]
        lead_key = f"{lead.name}_{lead.company or 'unknown'}"

        logger.info(f"Queueing messages for {lead.name}")
        state["status"] = WorkflowStatus.SENDING.value

        try:
            messages = state["generated_messages"].get(lead_key, [])

            # In production, this would actually send emails
            # For now, we'll just queue them
            for i, message in enumerate(messages):
                send_record = {
                    "lead": lead.dict() if hasattr(lead, 'dict') else lead.__dict__,
                    "message": message.dict() if hasattr(message, 'dict') else message.__dict__,
                    "sequence_number": i + 1,
                    "scheduled_send": datetime.now().isoformat(),
                    "status": "queued"
                }
                state["sent_messages"].append(send_record)

            # Update metrics
            state["metrics"]["messages_sent"] += len(messages)
            state["metrics"][f"sent_{lead_key}"] = True

            logger.info(f"Queued {len(messages)} messages for {lead.name}")

        except Exception as e:
            logger.error(f"Send failed for {lead.name}: {e}")
            state["errors"].append(f"Send failed for {lead.name}: {str(e)}")

        return state

    async def track_metrics(self, state: WorkflowState) -> WorkflowState:
        """Track campaign metrics"""
        logger.info("Tracking metrics")

        # Update processed count
        state["metrics"]["processed"] = state["current_lead_index"] + 1

        # Calculate success rate
        total_leads = len(state["leads"])
        messages_sent = state["metrics"].get("messages_sent", 0)
        messages_generated = state["metrics"].get("messages_generated", 0)

        state["metrics"]["success_rate"] = (state["metrics"]["processed"] / total_leads * 100) if total_leads > 0 else 0
        state["metrics"]["send_rate"] = (messages_sent / messages_generated * 100) if messages_generated > 0 else 0

        # Move to next lead
        state["current_lead_index"] += 1

        # Log progress
        logger.info(f"Progress: {state['metrics']['processed']}/{total_leads} leads processed")

        return state

    def has_more_leads(self, state: WorkflowState) -> str:
        """Check if there are more leads to process"""
        if state["current_lead_index"] < len(state["leads"]):
            return "continue"
        else:
            state["status"] = WorkflowStatus.COMPLETED.value
            state["metrics"]["end_time"] = datetime.now().isoformat()
            return "end"

    async def run_campaign(
        self,
        leads: List[LeadProfile],
        campaign_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a complete campaign"""

        initial_state = WorkflowState(
            leads=leads,
            campaign_config=campaign_config or {},
            current_lead_index=0,
            researched_companies={},
            generated_messages={},
            sent_messages=[],
            status=WorkflowStatus.INITIALIZED.value,
            errors=[],
            metrics={}
        )

        try:
            # Run workflow
            final_state = await self.workflow.ainvoke(initial_state)

            # Close research engine browser if open
            await self.research_engine.close_browser()

            return {
                "status": final_state["status"],
                "metrics": final_state["metrics"],
                "errors": final_state["errors"],
                "messages_queued": final_state["sent_messages"],
                "research_data": final_state["researched_companies"]
            }

        except Exception as e:
            logger.error(f"Campaign failed: {e}")
            return {
                "status": WorkflowStatus.FAILED.value,
                "error": str(e),
                "metrics": initial_state["metrics"]
            }

    async def process_single_lead(
        self,
        lead: LeadProfile,
        quick_mode: bool = False
    ) -> Dict[str, Any]:
        """Process a single lead quickly"""

        try:
            # Research
            company = await self.research_engine.research_company(
                company_name=lead.company or lead.name
            )

            # Generate message
            message = await self.generation_engine.generate_outreach(
                lead=lead,
                company=company,
                message_type=MessageType.COLD_EMAIL,
                stage=SalesStage.INTRODUCTION
            )

            return {
                "success": True,
                "lead": lead,
                "company_intelligence": company,
                "generated_message": message
            }

        except Exception as e:
            logger.error(f"Single lead processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "lead": lead
            }

        finally:
            await self.research_engine.close_browser()