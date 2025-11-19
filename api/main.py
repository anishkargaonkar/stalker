"""
FastAPI Backend for Stalker Engine
Provides REST endpoints for all functionality
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import pandas as pd
import json
import io
import asyncio
from datetime import datetime
import logging

from engine.orchestrator import StalkerOrchestrator, LeadProfile
from engine.research_engine import ResearchEngine, CompanyIntelligence
from engine.generation_engine import GenerationEngine, MessageType, SalesStage
from engine.email_sender import EmailSender, EmailTracker
from config.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Stalker Engine API",
    description="AI-Powered Sales Intelligence and Outreach Engine",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
orchestrator = StalkerOrchestrator()
research_engine = ResearchEngine()
generation_engine = GenerationEngine()
email_sender = EmailSender()
email_tracker = EmailTracker()

# ============= Pydantic Models =============

class LeadInput(BaseModel):
    """Input model for lead"""
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    linkedin: Optional[str] = None
    phone: Optional[str] = None

class ResearchRequest(BaseModel):
    """Request for company research"""
    company_name: str
    website: Optional[str] = None
    deep_research: bool = False

class GenerationRequest(BaseModel):
    """Request for message generation"""
    lead: LeadInput
    company_name: Optional[str] = None
    message_type: str = "cold_email"
    sales_stage: str = "introduction"
    personalization_level: str = "high"

class CampaignRequest(BaseModel):
    """Request for campaign execution"""
    leads: List[LeadInput]
    message_type: str = "cold_email"
    num_follow_ups: int = 3
    campaign_type: str = "standard"
    send_immediately: bool = False

class EmailRequest(BaseModel):
    """Request to send email"""
    to_email: str
    subject: str
    body: str
    html_body: Optional[str] = None
    schedule_time: Optional[str] = None

# ============= Health & Status Endpoints =============

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Stalker Engine",
        "version": "0.1.0",
        "status": "operational",
        "documentation": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "llm_provider": settings.llm_provider,
        "email_provider": settings.email_provider
    }

# ============= Lead Management Endpoints =============

@app.post("/api/leads/import")
async def import_leads(file: UploadFile = File(...)):
    """Import leads from CSV file"""
    try:
        # Read CSV
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))

        # Convert to LeadProfile objects
        leads = []
        required_fields = ["name"]

        for _, row in df.iterrows():
            if not all(field in row for field in required_fields):
                continue

            lead = LeadProfile(
                name=row["name"],
                title=row.get("title"),
                email=row.get("email"),
                company=row.get("company"),
                linkedin=row.get("linkedin"),
                phone=row.get("phone")
            )
            leads.append(lead)

        # Save to database (placeholder)
        logger.info(f"Imported {len(leads)} leads from {file.filename}")

        return {
            "success": True,
            "leads_imported": len(leads),
            "leads": [lead.__dict__ for lead in leads[:10]]  # Return first 10 for preview
        }

    except Exception as e:
        logger.error(f"Lead import failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/leads/create")
async def create_lead(lead: LeadInput):
    """Create a single lead"""
    try:
        lead_profile = LeadProfile(
            name=lead.name,
            title=lead.title,
            email=lead.email,
            company=lead.company,
            linkedin=lead.linkedin,
            phone=lead.phone
        )

        return {
            "success": True,
            "lead": lead_profile.__dict__
        }

    except Exception as e:
        logger.error(f"Lead creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ============= Research Endpoints =============

@app.post("/api/research/company")
async def research_company(request: ResearchRequest):
    """Research a company"""
    try:
        logger.info(f"Researching company: {request.company_name}")

        # Perform research
        intelligence = await research_engine.research_company(
            company_name=request.company_name,
            website=request.website
        )

        # Close browser
        await research_engine.close_browser()

        return {
            "success": True,
            "intelligence": intelligence.dict() if hasattr(intelligence, 'dict') else intelligence.__dict__
        }

    except Exception as e:
        logger.error(f"Company research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/research/lead")
async def research_lead(lead: LeadInput):
    """Research an individual lead"""
    try:
        lead_profile = LeadProfile(
            name=lead.name,
            title=lead.title,
            email=lead.email,
            company=lead.company,
            linkedin=lead.linkedin,
            phone=lead.phone
        )

        # Research lead
        enriched_lead = await research_engine.research_lead(lead_profile)

        # Also research their company if provided
        company_intelligence = None
        if lead.company:
            company_intelligence = await research_engine.research_company(lead.company)
            await research_engine.close_browser()

        return {
            "success": True,
            "lead": enriched_lead.__dict__,
            "company": company_intelligence.dict() if company_intelligence and hasattr(company_intelligence, 'dict') else None
        }

    except Exception as e:
        logger.error(f"Lead research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= Generation Endpoints =============

@app.post("/api/generate/message")
async def generate_message(request: GenerationRequest):
    """Generate a single message"""
    try:
        # Create lead profile
        lead = LeadProfile(
            name=request.lead.name,
            title=request.lead.title,
            email=request.lead.email,
            company=request.lead.company,
            linkedin=request.lead.linkedin,
            phone=request.lead.phone
        )

        # Get or research company
        company = None
        if request.company_name or request.lead.company:
            company_name = request.company_name or request.lead.company
            company = await research_engine.research_company(company_name)
            await research_engine.close_browser()

        # Generate message
        message = await generation_engine.generate_outreach(
            lead=lead,
            company=company or CompanyIntelligence(company_name="Unknown"),
            message_type=MessageType[request.message_type.upper()],
            stage=SalesStage[request.sales_stage.upper()]
        )

        return {
            "success": True,
            "message": message.dict() if hasattr(message, 'dict') else message.__dict__
        }

    except Exception as e:
        logger.error(f"Message generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/sequence")
async def generate_sequence(request: GenerationRequest):
    """Generate a message sequence"""
    try:
        # Create lead profile
        lead = LeadProfile(
            name=request.lead.name,
            title=request.lead.title,
            email=request.lead.email,
            company=request.lead.company,
            linkedin=request.lead.linkedin,
            phone=request.lead.phone
        )

        # Get or research company
        company = None
        if request.company_name or request.lead.company:
            company_name = request.company_name or request.lead.company
            company = await research_engine.research_company(company_name)
            await research_engine.close_browser()

        # Generate sequence
        sequence = await generation_engine.generate_campaign_sequence(
            lead=lead,
            company=company or CompanyIntelligence(company_name="Unknown"),
            num_messages=4
        )

        return {
            "success": True,
            "sequence": [msg.dict() if hasattr(msg, 'dict') else msg.__dict__ for msg in sequence]
        }

    except Exception as e:
        logger.error(f"Sequence generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= Campaign Endpoints =============

@app.post("/api/campaigns/create")
async def create_campaign(request: CampaignRequest, background_tasks: BackgroundTasks):
    """Create and optionally run a campaign"""
    try:
        # Convert to LeadProfile objects
        leads = []
        for lead_input in request.leads:
            lead = LeadProfile(
                name=lead_input.name,
                title=lead_input.title,
                email=lead_input.email,
                company=lead_input.company,
                linkedin=lead_input.linkedin,
                phone=lead_input.phone
            )
            leads.append(lead)

        # Campaign configuration
        campaign_config = {
            "message_type": request.message_type,
            "num_follow_ups": request.num_follow_ups,
            "campaign_type": request.campaign_type
        }

        # Run campaign (in background if requested)
        if request.send_immediately:
            background_tasks.add_task(
                orchestrator.run_campaign,
                leads,
                campaign_config
            )
            return {
                "success": True,
                "message": "Campaign started in background",
                "num_leads": len(leads)
            }
        else:
            # Run synchronously for preview
            result = await orchestrator.run_campaign(leads[:1], campaign_config)  # Preview with first lead
            return {
                "success": True,
                "preview": result,
                "total_leads": len(leads)
            }

    except Exception as e:
        logger.error(f"Campaign creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/campaigns/process-lead")
async def process_single_lead(lead: LeadInput):
    """Process a single lead through the entire pipeline"""
    try:
        lead_profile = LeadProfile(
            name=lead.name,
            title=lead.title,
            email=lead.email,
            company=lead.company,
            linkedin=lead.linkedin,
            phone=lead.phone
        )

        # Process lead
        result = await orchestrator.process_single_lead(lead_profile)

        return {
            "success": result.get("success", False),
            "result": result
        }

    except Exception as e:
        logger.error(f"Lead processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= Email Endpoints =============

@app.post("/api/email/send")
async def send_email(request: EmailRequest):
    """Send a single email"""
    try:
        result = await email_sender.send_email(
            to_email=request.to_email,
            subject=request.subject,
            body=request.body,
            html_body=request.html_body
        )

        email_tracker.record_sent(result)

        return {
            "success": result.success,
            "message_id": result.message_id,
            "error": result.error
        }

    except Exception as e:
        logger.error(f"Email send failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email/metrics")
async def get_email_metrics():
    """Get email campaign metrics"""
    return {
        "success": True,
        "metrics": email_tracker.get_metrics()
    }

@app.get("/api/email/verify")
async def verify_email_config():
    """Verify email configuration"""
    try:
        is_valid = await email_sender.verify_configuration()
        return {
            "success": is_valid,
            "provider": settings.email_provider,
            "configured": is_valid
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ============= Analytics Endpoints =============

@app.get("/api/analytics/dashboard")
async def get_dashboard_data():
    """Get dashboard analytics data"""
    return {
        "success": True,
        "data": {
            "leads_processed": 0,  # Would come from database
            "messages_generated": 0,
            "emails_sent": email_tracker.sent_count,
            "campaign_metrics": email_tracker.get_metrics(),
            "recent_activity": []
        }
    }

# ============= Export Endpoints =============

@app.get("/api/export/campaign-results")
async def export_campaign_results(campaign_id: Optional[str] = None):
    """Export campaign results as CSV"""
    try:
        # Placeholder data - would come from database
        data = {
            "leads": [],
            "messages": [],
            "metrics": email_tracker.get_metrics()
        }

        # Create CSV
        df = pd.DataFrame(data["leads"])
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)

        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=campaign_results_{datetime.now().strftime('%Y%m%d')}.csv"}
        )

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= Startup/Shutdown Events =============

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    logger.info("Stalker Engine API starting up...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Email Provider: {settings.email_provider}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    logger.info("Stalker Engine API shutting down...")
    await research_engine.close_browser()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)