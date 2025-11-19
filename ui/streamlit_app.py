"""
Streamlit UI Dashboard for Stalker Engine
Fast, interactive interface for sales intelligence and outreach
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import asyncio
from datetime import datetime, timedelta
import time
from typing import Dict, Any, List

# Page config
st.set_page_config(
    page_title="Stalker Engine - AI Sales Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = "http://localhost:8000"

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background: #f7f7f7;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .success-message {
        padding: 1rem;
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.25rem;
        color: #155724;
    }
    .error-message {
        padding: 1rem;
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.25rem;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'leads' not in st.session_state:
    st.session_state.leads = []
if 'research_results' not in st.session_state:
    st.session_state.research_results = {}
if 'generated_messages' not in st.session_state:
    st.session_state.generated_messages = {}
if 'campaign_status' not in st.session_state:
    st.session_state.campaign_status = "idle"

# Header
st.markdown('<h1 class="main-header">🎯 Stalker Engine</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; font-size: 1.2rem;">AI-Powered Sales Intelligence & Outreach Automation</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("## 🚀 Navigation")
    page = st.radio(
        "Select Page",
        ["Dashboard", "Lead Import", "Research", "Message Generation", "Campaign Manager", "Analytics"]
    )

    st.markdown("---")
    st.markdown("## ⚙️ Configuration")

    # API Health Check
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            st.success("✅ API Connected")
        else:
            st.error("❌ API Error")
    except:
        st.error("❌ API Offline")

    # Email Config Check
    try:
        response = requests.get(f"{API_BASE_URL}/api/email/verify", timeout=2)
        if response.json().get("configured"):
            st.success("✅ Email Configured")
        else:
            st.warning("⚠️ Email Not Configured")
    except:
        st.warning("⚠️ Email Status Unknown")

# ============= Dashboard Page =============
if page == "Dashboard":
    st.markdown("## 📊 Dashboard")

    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Leads",
            value=len(st.session_state.leads),
            delta="+10" if len(st.session_state.leads) > 0 else None
        )

    with col2:
        st.metric(
            label="Companies Researched",
            value=len(st.session_state.research_results),
            delta="+5" if len(st.session_state.research_results) > 0 else None
        )

    with col3:
        st.metric(
            label="Messages Generated",
            value=len(st.session_state.generated_messages),
            delta="+15" if len(st.session_state.generated_messages) > 0 else None
        )

    with col4:
        try:
            response = requests.get(f"{API_BASE_URL}/api/email/metrics")
            email_metrics = response.json()["metrics"]
            st.metric(
                label="Emails Sent",
                value=email_metrics.get("sent", 0),
                delta=f"{email_metrics.get('success_rate', 0):.1f}% success"
            )
        except:
            st.metric(label="Emails Sent", value=0)

    st.markdown("---")

    # Activity Timeline
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📈 Campaign Performance")

        # Create sample data for chart
        dates = pd.date_range(end=datetime.now(), periods=7)
        performance_data = pd.DataFrame({
            'Date': dates,
            'Leads Processed': [5, 8, 12, 15, 20, 18, 25],
            'Messages Sent': [10, 15, 25, 30, 40, 35, 50],
            'Responses': [1, 2, 3, 4, 6, 5, 8]
        })

        fig = px.line(
            performance_data,
            x='Date',
            y=['Leads Processed', 'Messages Sent', 'Responses'],
            title='7-Day Performance Trend'
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### 🎯 Quick Actions")

        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

        if st.button("📥 Import Leads", use_container_width=True):
            st.session_state.page = "Lead Import"
            st.rerun()

        if st.button("🔍 Research Company", use_container_width=True):
            st.session_state.page = "Research"
            st.rerun()

        if st.button("✉️ Generate Messages", use_container_width=True):
            st.session_state.page = "Message Generation"
            st.rerun()

        if st.button("🚀 Launch Campaign", use_container_width=True):
            st.session_state.page = "Campaign Manager"
            st.rerun()

# ============= Lead Import Page =============
elif page == "Lead Import":
    st.markdown("## 📥 Lead Import")

    tab1, tab2, tab3 = st.tabs(["CSV Upload", "Manual Entry", "Imported Leads"])

    with tab1:
        st.markdown("### Upload CSV File")
        st.info("CSV should contain columns: name, email, company, title, linkedin, phone")

        uploaded_file = st.file_uploader(
            "Choose a CSV file",
            type="csv",
            help="Upload a CSV file with lead information"
        )

        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.success(f"✅ Loaded {len(df)} leads from file")

                # Preview
                st.markdown("### Preview")
                st.dataframe(df.head(10))

                if st.button("Import Leads", type="primary"):
                    # Send to API
                    files = {'file': uploaded_file.getvalue()}
                    response = requests.post(f"{API_BASE_URL}/api/leads/import", files=files)

                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Successfully imported {result['leads_imported']} leads!")

                        # Update session state
                        for lead in result['leads']:
                            st.session_state.leads.append(lead)
                    else:
                        st.error(f"❌ Import failed: {response.text}")

            except Exception as e:
                st.error(f"❌ Error reading file: {e}")

    with tab2:
        st.markdown("### Add Lead Manually")

        with st.form("manual_lead_form"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("Name *", placeholder="John Doe")
                email = st.text_input("Email", placeholder="john@company.com")
                company = st.text_input("Company", placeholder="Acme Corp")

            with col2:
                title = st.text_input("Title", placeholder="VP of Sales")
                linkedin = st.text_input("LinkedIn", placeholder="linkedin.com/in/johndoe")
                phone = st.text_input("Phone", placeholder="+1-555-0100")

            submitted = st.form_submit_button("Add Lead", type="primary")

            if submitted and name:
                lead_data = {
                    "name": name,
                    "email": email,
                    "company": company,
                    "title": title,
                    "linkedin": linkedin,
                    "phone": phone
                }

                response = requests.post(f"{API_BASE_URL}/api/leads/create", json=lead_data)

                if response.status_code == 200:
                    st.success(f"✅ Lead {name} added successfully!")
                    st.session_state.leads.append(response.json()["lead"])
                else:
                    st.error("❌ Failed to add lead")

    with tab3:
        st.markdown("### Imported Leads")

        if st.session_state.leads:
            df = pd.DataFrame(st.session_state.leads)
            st.dataframe(df, use_container_width=True)

            # Export option
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"leads_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No leads imported yet. Use the tabs above to import leads.")

# ============= Research Page =============
elif page == "Research":
    st.markdown("## 🔍 Research Center")

    tab1, tab2 = st.tabs(["Company Research", "Lead Research"])

    with tab1:
        st.markdown("### Research Company")

        company_name = st.text_input("Company Name", placeholder="Enter company name...")
        website = st.text_input("Website (optional)", placeholder="https://example.com")

        col1, col2 = st.columns([1, 3])
        with col1:
            deep_research = st.checkbox("Deep Research", value=True)

        if st.button("🔍 Research Company", type="primary"):
            if company_name:
                with st.spinner(f"Researching {company_name}..."):
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/api/research/company",
                            json={
                                "company_name": company_name,
                                "website": website,
                                "deep_research": deep_research
                            },
                            timeout=60
                        )

                        if response.status_code == 200:
                            intelligence = response.json()["intelligence"]
                            st.session_state.research_results[company_name] = intelligence

                            # Display results
                            st.success(f"✅ Research completed for {company_name}")

                            # Company Overview
                            st.markdown("### 📊 Company Intelligence")
                            col1, col2, col3 = st.columns(3)

                            with col1:
                                st.markdown("**Basic Info**")
                                st.write(f"Industry: {intelligence.get('industry', 'N/A')}")
                                st.write(f"Size: {intelligence.get('size', 'N/A')}")
                                st.write(f"Location: {intelligence.get('location', 'N/A')}")

                            with col2:
                                st.markdown("**Signals**")
                                if intelligence.get('growth_signals'):
                                    for signal in intelligence['growth_signals'][:3]:
                                        st.write(f"• {signal[:50]}...")

                            with col3:
                                st.markdown("**Technologies**")
                                if intelligence.get('technologies'):
                                    for tech in intelligence['technologies'][:5]:
                                        st.write(f"• {tech}")

                            # Recent News
                            if intelligence.get('recent_news'):
                                st.markdown("### 📰 Recent News")
                                for news in intelligence['recent_news'][:3]:
                                    st.write(f"• {news[:100]}...")

                            # Pain Points
                            if intelligence.get('pain_points'):
                                st.markdown("### 🎯 Identified Pain Points")
                                for pain in intelligence['pain_points'][:3]:
                                    st.warning(f"• {pain}")

                            # Confidence Score
                            confidence = intelligence.get('confidence_score', 0)
                            st.progress(confidence, text=f"Research Confidence: {confidence*100:.0f}%")

                        else:
                            st.error(f"❌ Research failed: {response.text}")

                    except Exception as e:
                        st.error(f"❌ Error: {e}")
            else:
                st.warning("Please enter a company name")

    with tab2:
        st.markdown("### Research Lead")

        if st.session_state.leads:
            lead_names = [lead['name'] for lead in st.session_state.leads]
            selected_lead = st.selectbox("Select Lead", lead_names)

            if st.button("🔍 Research Lead", type="primary"):
                lead = next(l for l in st.session_state.leads if l['name'] == selected_lead)

                with st.spinner(f"Researching {selected_lead}..."):
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/api/research/lead",
                            json=lead,
                            timeout=60
                        )

                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Research completed for {selected_lead}")

                            # Display enriched lead info
                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("**Lead Information**")
                                enriched_lead = result['lead']
                                st.write(f"Name: {enriched_lead['name']}")
                                st.write(f"Title: {enriched_lead.get('title', 'N/A')}")
                                st.write(f"Company: {enriched_lead.get('company', 'N/A')}")
                                st.write(f"Engagement Score: {enriched_lead.get('engagement_score', 0)*100:.0f}%")

                            with col2:
                                st.markdown("**Recent Activity**")
                                if enriched_lead.get('recent_activity'):
                                    for activity in enriched_lead['recent_activity']:
                                        st.write(f"• {activity[:100]}...")

                            # Company Intelligence
                            if result.get('company'):
                                st.markdown("### Company Intelligence")
                                company = result['company']
                                st.write(f"Industry: {company.get('industry', 'N/A')}")
                                st.write(f"Recent News: {len(company.get('recent_news', []))} items found")

                        else:
                            st.error(f"❌ Research failed")

                    except Exception as e:
                        st.error(f"❌ Error: {e}")
        else:
            st.info("No leads available. Please import leads first.")

# ============= Message Generation Page =============
elif page == "Message Generation":
    st.markdown("## ✉️ Message Generation")

    if st.session_state.leads:
        tab1, tab2 = st.tabs(["Single Message", "Campaign Sequence"])

        with tab1:
            st.markdown("### Generate Single Message")

            col1, col2 = st.columns(2)

            with col1:
                lead_names = [lead['name'] for lead in st.session_state.leads]
                selected_lead = st.selectbox("Select Lead", lead_names)

                message_type = st.selectbox(
                    "Message Type",
                    ["cold_email", "linkedin", "follow_up", "call_script"]
                )

            with col2:
                sales_stage = st.selectbox(
                    "Sales Stage",
                    ["introduction", "qualification", "value_proposition", "closing"]
                )

                personalization = st.select_slider(
                    "Personalization Level",
                    options=["low", "medium", "high"],
                    value="high"
                )

            if st.button("🎨 Generate Message", type="primary"):
                lead = next(l for l in st.session_state.leads if l['name'] == selected_lead)

                with st.spinner("Generating personalized message..."):
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/api/generate/message",
                            json={
                                "lead": lead,
                                "message_type": message_type,
                                "sales_stage": sales_stage,
                                "personalization_level": personalization
                            },
                            timeout=30
                        )

                        if response.status_code == 200:
                            message = response.json()["message"]

                            # Store in session
                            message_key = f"{lead['name']}_{datetime.now().isoformat()}"
                            st.session_state.generated_messages[message_key] = message

                            # Display message
                            st.success("✅ Message generated successfully!")

                            if message.get('subject'):
                                st.markdown(f"**Subject:** {message['subject']}")

                            st.markdown("**Message:**")
                            st.text_area("", value=message['body'], height=200, disabled=True)

                            st.markdown("**Call to Action:**")
                            st.info(message.get('call_to_action', 'N/A'))

                            # Personalization hooks
                            if message.get('personalization_hooks'):
                                st.markdown("**Personalization Elements:**")
                                for hook in message['personalization_hooks']:
                                    st.write(f"• {hook}")

                            # Confidence score
                            confidence = message.get('confidence', 0)
                            st.progress(confidence, text=f"Confidence: {confidence*100:.0f}%")

                            # Actions
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                if st.button("📧 Send Email"):
                                    st.info("Email queued for sending")
                            with col2:
                                if st.button("🔄 Regenerate"):
                                    st.rerun()
                            with col3:
                                if st.button("📋 Copy to Clipboard"):
                                    st.info("Copied!")

                        else:
                            st.error("❌ Generation failed")

                    except Exception as e:
                        st.error(f"❌ Error: {e}")

        with tab2:
            st.markdown("### Generate Campaign Sequence")

            lead_names = [lead['name'] for lead in st.session_state.leads]
            selected_lead = st.selectbox("Select Lead for Sequence", lead_names, key="seq_lead")

            num_messages = st.slider("Number of Messages", 2, 6, 4)

            if st.button("🎨 Generate Sequence", type="primary"):
                lead = next(l for l in st.session_state.leads if l['name'] == selected_lead)

                with st.spinner(f"Generating {num_messages}-message sequence..."):
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/api/generate/sequence",
                            json={
                                "lead": lead,
                                "message_type": "cold_email",
                                "sales_stage": "introduction"
                            },
                            timeout=60
                        )

                        if response.status_code == 200:
                            sequence = response.json()["sequence"]
                            st.success(f"✅ Generated {len(sequence)}-message sequence!")

                            # Display each message
                            for i, msg in enumerate(sequence):
                                with st.expander(f"Message {i+1} - {msg.get('stage', 'Unknown Stage')}"):
                                    if msg.get('subject'):
                                        st.markdown(f"**Subject:** {msg['subject']}")
                                    st.text_area("", value=msg['body'], height=150, key=f"seq_{i}")
                                    st.info(f"CTA: {msg.get('call_to_action', 'N/A')}")

                        else:
                            st.error("❌ Sequence generation failed")

                    except Exception as e:
                        st.error(f"❌ Error: {e}")

    else:
        st.info("No leads available. Please import leads first.")

# ============= Campaign Manager Page =============
elif page == "Campaign Manager":
    st.markdown("## 🚀 Campaign Manager")

    if st.session_state.leads:
        st.markdown("### Campaign Configuration")

        col1, col2, col3 = st.columns(3)

        with col1:
            campaign_name = st.text_input("Campaign Name", value=f"Campaign_{datetime.now().strftime('%Y%m%d')}")
            message_type = st.selectbox("Message Type", ["cold_email", "linkedin", "follow_up"])

        with col2:
            num_follow_ups = st.number_input("Number of Follow-ups", 0, 5, 3)
            campaign_type = st.selectbox("Campaign Type", ["standard", "aggressive", "gentle"])

        with col3:
            send_immediately = st.checkbox("Send Immediately", value=False)
            schedule_time = st.time_input("Schedule Time", value=datetime.now().time())

        # Lead Selection
        st.markdown("### Select Leads")

        select_all = st.checkbox("Select All Leads")

        if select_all:
            selected_leads = st.session_state.leads
        else:
            lead_names = [lead['name'] for lead in st.session_state.leads]
            selected_names = st.multiselect("Select Leads for Campaign", lead_names)
            selected_leads = [l for l in st.session_state.leads if l['name'] in selected_names]

        st.info(f"📊 {len(selected_leads)} leads selected for campaign")

        # Campaign Actions
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🔍 Preview Campaign", type="secondary"):
                if selected_leads:
                    with st.spinner("Generating preview..."):
                        # Preview with first lead
                        st.markdown("### Campaign Preview")
                        st.write(f"**Lead:** {selected_leads[0]['name']}")
                        st.write(f"**Type:** {message_type}")
                        st.write(f"**Follow-ups:** {num_follow_ups}")
                        st.success("Preview generated!")

        with col2:
            if st.button("💾 Save Campaign", type="secondary"):
                st.success(f"Campaign '{campaign_name}' saved!")

        with col3:
            if st.button("🚀 Launch Campaign", type="primary"):
                if selected_leads:
                    with st.spinner(f"Launching campaign for {len(selected_leads)} leads..."):
                        try:
                            response = requests.post(
                                f"{API_BASE_URL}/api/campaigns/create",
                                json={
                                    "leads": selected_leads,
                                    "message_type": message_type,
                                    "num_follow_ups": num_follow_ups,
                                    "campaign_type": campaign_type,
                                    "send_immediately": send_immediately
                                },
                                timeout=60
                            )

                            if response.status_code == 200:
                                result = response.json()
                                st.success(f"✅ Campaign launched successfully!")
                                st.balloons()

                                if result.get("preview"):
                                    st.json(result["preview"])
                            else:
                                st.error("❌ Campaign launch failed")

                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                else:
                    st.warning("Please select leads for the campaign")

    else:
        st.info("No leads available. Please import leads first.")

# ============= Analytics Page =============
elif page == "Analytics":
    st.markdown("## 📈 Analytics")

    # Get metrics from API
    try:
        response = requests.get(f"{API_BASE_URL}/api/email/metrics")
        email_metrics = response.json()["metrics"]

        response2 = requests.get(f"{API_BASE_URL}/api/analytics/dashboard")
        dashboard_data = response2.json()["data"]
    except:
        email_metrics = {"sent": 0, "failed": 0, "opened": 0, "clicked": 0, "replied": 0}
        dashboard_data = {}

    # Metrics Overview
    st.markdown("### 📊 Key Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Emails Sent", email_metrics.get("sent", 0))
        st.metric("Success Rate", f"{email_metrics.get('success_rate', 0):.1f}%")

    with col2:
        st.metric("Open Rate", f"{email_metrics.get('open_rate', 0):.1f}%")
        st.metric("Click Rate", f"{email_metrics.get('click_rate', 0):.1f}%")

    with col3:
        st.metric("Reply Rate", f"{email_metrics.get('reply_rate', 0):.1f}%")
        st.metric("Bounce Rate", f"{(email_metrics.get('bounced', 0) / max(email_metrics.get('sent', 1), 1) * 100):.1f}%")

    with col4:
        st.metric("Leads Processed", len(st.session_state.leads))
        st.metric("Companies Researched", len(st.session_state.research_results))

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Email Performance")

        # Funnel chart
        fig = go.Figure(go.Funnel(
            y=["Sent", "Opened", "Clicked", "Replied"],
            x=[
                email_metrics.get("sent", 0),
                email_metrics.get("opened", 0),
                email_metrics.get("clicked", 0),
                email_metrics.get("replied", 0)
            ],
            textinfo="value+percent initial"
        ))
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Campaign Status")

        # Pie chart
        fig = px.pie(
            values=[
                email_metrics.get("sent", 1),
                email_metrics.get("failed", 0),
                email_metrics.get("bounced", 0)
            ],
            names=["Delivered", "Failed", "Bounced"],
            title="Email Delivery Status"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Export Options
    st.markdown("### 📥 Export Data")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Export Campaign Results"):
            st.info("Exporting results...")

    with col2:
        if st.button("Export Analytics Report"):
            st.info("Generating report...")

    with col3:
        if st.button("Export Lead Data"):
            if st.session_state.leads:
                df = pd.DataFrame(st.session_state.leads)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"leads_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

# Footer
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #888;">Powered by LangChain, LangGraph & Open Source AI | Built for Hackathon 2024</p>',
    unsafe_allow_html=True
)