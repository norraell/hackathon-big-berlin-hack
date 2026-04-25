"""Gemini LLM client for streaming completions with function calling."""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, Callable, Any

import google.generativeai as genai

from app.config import settings
from app.llm.prompts import get_system_prompt
from app.llm.tools import TOOLS, validate_tool_call

logger = logging.getLogger(__name__)


class GeminiLLMClient:
    """Handles streaming LLM completions using Google Gemini.
    
    This class manages:
    - Streaming chat completions
    - Function/tool calling
    - Conversation history
    - Token streaming for low-latency TTS
    """

    def __init__(
        self,
        language: str = "en",
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> None:
        """Initialize the Gemini LLM client.
        
        Args:
            language: Language code for system prompt
            on_token: Callback for each token generated
            on_tool_call: Callback for tool calls (tool_name, arguments)
        """
        self.language = language
        self.on_token = on_token
        self.on_tool_call = on_tool_call
        
        # Conversation history
        self.messages: list[dict[str, Any]] = []
        
        # System prompt
        self.system_prompt = get_system_prompt(language)
        
        # Gemini model and chat
        self.model = None
        self.chat = None
        
        # Streaming state
        self.current_response = ""
        self.is_streaming = False
        
        logger.info(f"GeminiLLMClient initialized with language: {language}")

    async def initialize(self) -> None:
        """Initialize the Gemini client."""
        try:
            # Configure Gemini API
            genai.configure(api_key=settings.gemini_api_key)
            
            # Initialize model with system instruction
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=self.system_prompt,
            )
            
            # Start chat session
            self.chat = self.model.start_chat(history=[])
            
            logger.info("Gemini client initialized")
            
        except Exception as e:
            logger.error(f"Error initializing Gemini client: {e}", exc_info=True)
            raise

    async def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation history.
        
        Args:
            content: User message content
        """
        self.messages.append({
            "role": "user",
            "content": content,
        })
        logger.info(f"Added user message: {content[:100]}...")

    async def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation history.
        
        Args:
            content: Assistant message content
        """
        self.messages.append({
            "role": "assistant",
            "content": content,
        })
        logger.info(f"Added assistant message: {content[:100]}...")

    async def add_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> None:
        """Add a tool call result to the conversation history.
        
        Args:
            tool_call_id: ID of the tool call
            tool_name: Name of the tool that was called
            result: Result of the tool execution
        """
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result,
        })
        logger.info(f"Added tool result for {tool_name}")

    async def stream_completion(
        self,
        max_tokens: int = 150,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion from the LLM.
        
        This method streams tokens as they are generated, enabling
        low-latency text-to-speech synthesis.
        
        Args:
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Yields:
            Individual tokens as they are generated
        """
        if not self.chat:
            await self.initialize()
        
        self.is_streaming = True
        self.current_response = ""
        
        try:
            # Get the last user message
            last_message = None
            for msg in reversed(self.messages):
                if msg["role"] == "user":
                    last_message = msg["content"]
                    break
            
            if not last_message:
                logger.warning("No user message found for streaming")
                return
            
            logger.info("Starting LLM completion stream")
            
            # Configure generation
            generation_config = genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            
            # Stream response from Gemini
            response = await asyncio.to_thread(
                self.chat.send_message,
                last_message,
                generation_config=generation_config,
                stream=True,
            )
            
            # Process streaming chunks
            for chunk in response:
                if chunk.text:
                    token = chunk.text
                    self.current_response += token
                    
                    if self.on_token:
                        self.on_token(token)
                    
                    yield token
            
            # Add complete response to history
            await self.add_assistant_message(self.current_response.strip())
            
            logger.info(f"Completed LLM stream: {self.current_response[:100]}...")
            
        except Exception as e:
            logger.error(f"Error streaming completion: {e}", exc_info=True)
            raise
        finally:
            self.is_streaming = False

    async def get_completion_with_tools(
        self,
        max_tokens: int = 150,
        temperature: float = 0.7,
    ) -> tuple[Optional[str], Optional[list[dict[str, Any]]]]:
        """Get a completion that may include tool calls.
        
        This is used when we need to wait for the complete response
        to check for tool calls before proceeding.
        
        Args:
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Tuple of (response_text, tool_calls)
        """
        if not self.chat:
            await self.initialize()
        
        try:
            # Get the last user message
            last_message = None
            for msg in reversed(self.messages):
                if msg["role"] == "user":
                    last_message = msg["content"]
                    break
            
            if not last_message:
                logger.warning("No user message found for completion")
                return None, None
            
            logger.info("Getting LLM completion with tools")
            
            # Configure generation
            generation_config = genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            
            # Get response from Gemini (non-streaming for tool calls)
            response = await asyncio.to_thread(
                self.chat.send_message,
                last_message,
                generation_config=generation_config,
            )
            
            # Extract text response
            response_text = response.text if response.text else None
            
            # Check for function calls (Gemini's tool calling)
            tool_calls = None
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call'):
                            # Convert Gemini function call to our format
                            if tool_calls is None:
                                tool_calls = []
                            tool_calls.append({
                                "id": f"call_{len(tool_calls)}",
                                "function": {
                                    "name": part.function_call.name,
                                    "arguments": json.dumps(dict(part.function_call.args)),
                                }
                            })
            
            # Add to history
            if response_text:
                await self.add_assistant_message(response_text)
            
            return response_text, tool_calls
            
        except Exception as e:
            logger.error(f"Error getting completion with tools: {e}", exc_info=True)
            raise

    async def process_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Process and validate tool calls from the LLM.
        
        Args:
            tool_calls: List of tool calls from the LLM
            
        Returns:
            List of tuples (tool_call_id, tool_name, arguments)
        """
        processed_calls = []
        
        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", "")
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")
            
            try:
                arguments = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in tool call arguments: {function.get('arguments')}")
                continue
            
            # Validate tool call
            is_valid, error_msg = validate_tool_call(tool_name, arguments)
            
            if not is_valid:
                logger.error(f"Invalid tool call: {error_msg}")
                continue
            
            logger.info(f"Valid tool call: {tool_name} with args: {arguments}")
            
            # Notify callback
            if self.on_tool_call:
                self.on_tool_call(tool_name, arguments)
            
            processed_calls.append((tool_call_id, tool_name, arguments))
        
        return processed_calls

    async def change_language(self, language: str) -> None:
        """Change the conversation language.
        
        Args:
            language: New language code
        """
        logger.info(f"Changing LLM language from {self.language} to {language}")
        
        self.language = language
        
        # Update system prompt and reinitialize
        self.system_prompt = get_system_prompt(language)
        
        # Reinitialize model with new system instruction
        await self.initialize()

    def get_conversation_history(self) -> list[dict[str, Any]]:
        """Get the current conversation history.
        
        Returns:
            List of message dictionaries
        """
        return self.messages.copy()

    def clear_history(self, keep_system: bool = True) -> None:
        """Clear the conversation history.
        
        Args:
            keep_system: Whether to keep the system prompt (reinitialize chat)
        """
        self.messages = []
        
        # Restart chat session
        if self.model and keep_system:
            self.chat = self.model.start_chat(history=[])
        
        logger.info("Conversation history cleared")

    async def stop_streaming(self) -> None:
        """Stop the current streaming operation."""
        self.is_streaming = False
        logger.info("LLM streaming stopped")