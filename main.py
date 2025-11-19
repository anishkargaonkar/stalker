#!/usr/bin/env python3
"""
Stalker Engine - Main Entry Point
Launches both API and UI servers
"""

import sys
import os
import subprocess
import time
import signal
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_requirements():
    """Check if all requirements are installed"""
    try:
        import langchain
        import fastapi
        import streamlit
        logger.info("✅ Core dependencies verified")
        return True
    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        logger.info("Please run: pip install -r requirements.txt")
        return False

def check_env_file():
    """Check if .env file exists"""
    env_file = Path(".env")
    if not env_file.exists():
        logger.warning("⚠️  .env file not found")
        logger.info("Creating .env from .env.example...")

        example_file = Path(".env.example")
        if example_file.exists():
            env_file.write_text(example_file.read_text())
            logger.info("✅ Created .env file. Please update it with your API keys.")
            return False
        else:
            logger.error("❌ .env.example file not found")
            return False
    return True

def start_api_server():
    """Start the FastAPI server"""
    logger.info("🚀 Starting FastAPI server on port 8000...")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

def start_ui_server():
    """Start the Streamlit UI"""
    logger.info("🎨 Starting Streamlit UI on port 8501...")
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "ui/streamlit_app.py", "--server.port", "8501"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

def main():
    """Main entry point"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║                    🎯 STALKER ENGINE 🎯                   ║
    ║                                                           ║
    ║         AI-Powered Sales Intelligence & Outreach         ║
    ║                                                           ║
    ║   Built with: LangChain, LangGraph, SalesGPT & More!    ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # Check requirements
    if not check_requirements():
        logger.error("Please install requirements first")
        sys.exit(1)

    # Check environment
    if not check_env_file():
        logger.warning("Please configure .env file with your API keys")
        logger.info("Required keys: OPENAI_API_KEY or ANTHROPIC_API_KEY")
        sys.exit(1)

    # Start servers
    api_process = None
    ui_process = None

    try:
        # Start API server
        api_process = start_api_server()
        time.sleep(3)  # Wait for API to start

        # Start UI server
        ui_process = start_ui_server()
        time.sleep(3)  # Wait for UI to start

        logger.info("=" * 60)
        logger.info("✅ Stalker Engine is running!")
        logger.info("=" * 60)
        logger.info("📡 API Server: http://localhost:8000")
        logger.info("📡 API Docs: http://localhost:8000/docs")
        logger.info("🎨 UI Dashboard: http://localhost:8501")
        logger.info("=" * 60)
        logger.info("Press Ctrl+C to stop all services")

        # Keep running
        while True:
            time.sleep(1)

            # Check if processes are still running
            if api_process and api_process.poll() is not None:
                logger.error("API server stopped unexpectedly")
                break
            if ui_process and ui_process.poll() is not None:
                logger.error("UI server stopped unexpectedly")
                break

    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down Stalker Engine...")

    finally:
        # Cleanup
        if api_process:
            api_process.terminate()
            api_process.wait()
            logger.info("API server stopped")

        if ui_process:
            ui_process.terminate()
            ui_process.wait()
            logger.info("UI server stopped")

        logger.info("👋 Goodbye!")

if __name__ == "__main__":
    main()