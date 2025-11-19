"""
LLM Manager using LiteLLM for multi-provider support
Based on SalesGPT's approach but enhanced for flexibility
"""

from typing import Optional, Dict, Any, List
import litellm
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    from langchain.llms import OpenAI as ChatOpenAI
try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None
try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None
from langchain.schema import BaseMessage
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class LLMManager:
    """Manages LLM connections and provides unified interface"""

    def __init__(self):
        self.provider = settings.llm_provider
        self.config = settings.get_llm_config()
        self.llm = self._initialize_llm()

    def _initialize_llm(self):
        """Initialize the appropriate LLM based on settings"""
        try:
            if self.provider == "openai":
                return ChatOpenAI(
                    api_key=self.config["api_key"],
                    model=self.config["model"],
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"],
                    streaming=True
                )
            elif self.provider == "anthropic":
                return ChatAnthropic(
                    api_key=self.config["api_key"],
                    model=self.config["model"],
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"]
                )
            elif self.provider == "groq":
                return ChatGroq(
                    api_key=self.config["api_key"],
                    model=self.config["model"],
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"]
                )
            elif self.provider == "mock":
                # Mock LLM for testing
                return self._create_mock_llm()
            else:
                # Fallback to LiteLLM for any provider
                return self._create_litellm_wrapper()
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

    def _create_litellm_wrapper(self):
        """Create a LangChain-compatible wrapper for LiteLLM"""
        from langchain.llms.base import LLM
        from typing import Optional, List

        class LiteLLMWrapper(LLM):
            """Wrapper to use LiteLLM with LangChain"""

            @property
            def _llm_type(self) -> str:
                return "litellm"

            def _call(
                self,
                prompt: str,
                stop: Optional[List[str]] = None,
                run_manager: Optional[Any] = None,
                **kwargs: Any,
            ) -> str:
                try:
                    response = litellm.completion(
                        model=settings.llm_model,
                        messages=[{"role": "user", "content": prompt}],
                        api_key=settings.get_llm_config()["api_key"],
                        temperature=settings.llm_temperature,
                        max_tokens=settings.llm_max_tokens,
                        stop=stop,
                        **kwargs
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    logger.error(f"LiteLLM call failed: {e}")
                    raise

        return LiteLLMWrapper()

    def _create_mock_llm(self):
        """Create a mock LLM for testing"""
        from langchain.llms.base import LLM
        from typing import Optional, List

        class MockLLM(LLM):
            """Mock LLM that returns predefined responses"""

            @property
            def _llm_type(self) -> str:
                return "mock"

            def _call(
                self,
                prompt: str,
                stop: Optional[List[str]] = None,
                run_manager: Optional[Any] = None,
                **kwargs: Any,
            ) -> str:
                logger.info("[MOCK LLM] Generating response")
                # Return contextual mock responses
                if "company" in prompt.lower():
                    return "Based on the analysis, this company shows strong growth potential with recent funding and expansion initiatives."
                elif "email" in prompt.lower() or "message" in prompt.lower():
                    return "Subject: Innovative Solutions for Your Growth\n\nDear [Name],\n\nI noticed your company's recent expansion. Our solution can help streamline your operations and accelerate growth.\n\nBest regards"
                elif "pain" in prompt.lower():
                    return "The main pain points identified are: scaling infrastructure, improving efficiency, and customer retention."
                else:
                    return "This is a mock response for testing purposes. The system is working correctly."

            async def _acall(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
                return self._call(prompt, stop, **kwargs)

        logger.info("Using Mock LLM (no API calls)")
        return MockLLM()

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt"""
        try:
            response = self.llm.invoke(prompt, **kwargs)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise

    def generate_with_messages(self, messages: List[BaseMessage], **kwargs) -> str:
        """Generate response from message history"""
        try:
            response = self.llm.invoke(messages, **kwargs)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"Message generation failed: {e}")
            raise

    def stream_generate(self, prompt: str, callback=None, **kwargs):
        """Stream generation for real-time responses"""
        try:
            for chunk in self.llm.stream(prompt, **kwargs):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if callback:
                    callback(content)
                yield content
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            raise

    @staticmethod
    def count_tokens(text: str, model: Optional[str] = None) -> int:
        """Count tokens in text"""
        try:
            import tiktoken
            model = model or settings.llm_model

            # Map model to encoding
            if "gpt-4" in model or "gpt-3.5" in model:
                encoding = tiktoken.encoding_for_model(model)
            else:
                encoding = tiktoken.get_encoding("cl100k_base")

            return len(encoding.encode(text))
        except Exception as e:
            # Fallback to approximate count
            return len(text) // 4

# Global LLM manager instance
llm_manager = None

def get_llm_manager():
    """Get or create LLM manager instance"""
    global llm_manager
    if llm_manager is None:
        llm_manager = LLMManager()
    return llm_manager