import os
import json
import time
import re
import random
import logging
from typing import List, Dict, Any, Generator, Optional, Callable
from google import genai
from google.genai import errors
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 10  # seconds

# Model configuration
DEFAULT_MODEL = "gemini-2.0-flash-001"

class GeminiClient:
    """Wrapper class for Google Gemini API client with retry functionality."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        """Initialize the Gemini client with API key and default model."""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key is required")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
    
    def with_retries(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic for API errors."""
        retries = 0
        while retries <= MAX_RETRIES:
            try:
                return func(*args, **kwargs)
            except (errors.GoogleGenerativeAIError) as e:
                retries += 1
                if retries > MAX_RETRIES:
                    logger.error(f"Failed after {MAX_RETRIES} retries: {str(e)}")
                    raise
                
                # Calculate exponential backoff with jitter
                delay = min(INITIAL_RETRY_DELAY * (2 ** (retries - 1)) + random.uniform(0, 1), MAX_RETRY_DELAY)
                logger.warning(f"API error: {str(e)}. Retrying in {delay:.2f} seconds (attempt {retries}/{MAX_RETRIES})...")
                time.sleep(delay)
    
    def create_chat_session(self) -> Any:
        """Create a new chat session with the model."""
        return self.with_retries(self.client.chats.create, model=self.model)
    
    def send_message(self, chat, message: str) -> Any:
        """Send a message to the chat session."""
        return self.with_retries(chat.send_message, message)
    
    def send_message_stream(self, chat, message: str) -> Generator:
        """Send a message to the chat session and stream the response."""
        return self.with_retries(chat.send_message_stream, message)


class ResponseGenerator:
    """Class to generate responses from the Gemini model."""
    
    def __init__(self, client: GeminiClient, use_case: str = "insurance"):
        """Initialize with a GeminiClient instance and use case."""
        self.client = client
        self.use_case = use_case
        self.use_case_system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from the corresponding .md file in use_cases folder."""
        try:
            # Get the directory of the current script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_file = os.path.join(current_dir, "use_cases", f"{self.use_case}.md")
            
            with open(prompt_file, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except FileNotFoundError:
            logger.error(f"System prompt file not found: use_cases/{self.use_case}.md")
            # Fallback to a basic prompt
            return "You are a helpful assistant. Please provide clear and helpful responses."
        except Exception as e:
            logger.error(f"Error loading system prompt: {str(e)}")
            return "You are a helpful assistant. Please provide clear and helpful responses."
    
    def get_assistant_response(self, prompt: str) -> str:
        """Get a complete response from the assistant."""
        return "".join(self.stream_assistant_response(prompt))
    
    def stream_assistant_response(self, prompt: str) -> Generator[str, None, None]:
        """Stream the assistant's response."""
        try:
            # Create a chat session with the Gemini model
            chat = self.client.create_chat_session()
            
            # Send the system instruction as the first message
            self.client.send_message(chat, self.use_case_system_prompt)
            
            # Use send_message_stream for streaming responses
            for chunk in self.client.send_message_stream(chat, prompt):
                if chunk.text:
                    yield chunk.text
                    
        except errors.GoogleGenerativeAIError as e:
            logger.error(f"API error in stream_assistant_response: {str(e)}")
            yield f"I apologize, but I couldn't process your request at this time due to a service issue."
            
        except Exception as e:
            logger.error(f"Error in stream_assistant_response: {str(e)}")
            yield "I apologize, but I couldn't process your request at this time due to an unexpected error."
    
    def generate_context(self, prompt: str) -> List[str]:
        """Generate context fragments for a prompt."""
        try:
            # Create system prompt for context generation with explicit JSON format instructions
            context_system_prompt = """
                You are a helpful assistant that provides relevant context fragments for user questions.
                For the given user query, generate 3-5 short, relevant context fragments that would be helpful for answering the question.
                
                IMPORTANT: You MUST respond with ONLY a valid JSON object that has a "fragments" key containing an array of strings.
                Example format:
                {
                    "fragments": [
                        "Context fragment 1",
                        "Context fragment 2",
                        "Context fragment 3"
                    ]
                }
                
                Do not include any explanations, markdown formatting, or additional text outside of the JSON object.
                """
            
            # Create a chat session with the Gemini model
            chat = self.client.create_chat_session()
            
            # Send the system instruction as the first message
            self.client.send_message(chat, context_system_prompt)
            
            # Send the user's question and get the response
            response = self.client.send_message(chat, f"Generate context fragments for this insurance question: {prompt}")
            
            # Parse the response
            return self._parse_context_response(response.text, prompt)
            
        except errors.GoogleGenerativeAIError as e:
            logger.error(f"API error in generate_context: {str(e)}")
            return self._get_default_fragments(prompt)
            
        except Exception as e:
            logger.error(f"Error in generate_context: {str(e)}")
            return self._get_default_fragments(prompt)
    
    def _parse_context_response(self, text: str, prompt: str) -> List[str]:
        """Parse the response text to extract context fragments."""
        # Try to parse the entire response as JSON
        try:
            context_data = json.loads(text)
            fragments = context_data.get("fragments", [])
            if fragments and isinstance(fragments, list):
                return fragments[:5]
        except json.JSONDecodeError:
            pass
        
        # If direct JSON parsing fails, try to extract JSON using regex
        try:
            json_match = re.search(r'(\{.*"fragments"\s*:\s*\[.*\].*\})', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                context_data = json.loads(json_str)
                fragments = context_data.get("fragments", [])
                if fragments and isinstance(fragments, list):
                    return fragments[:5]
        except:
            pass
            
        # If JSON extraction fails, try to extract just the array
        try:
            array_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', text)
            if array_match:
                array_str = array_match.group(0)
                fragments = json.loads(array_str)
                if isinstance(fragments, list):
                    return fragments[:5]
        except:
            pass
        
        # If all structured parsing fails, extract text fragments
        fragments = self._extract_text_fragments(text)
        
        # If we still have no fragments, create default ones based on the prompt
        if not fragments:
            return self._get_default_fragments(prompt)
        
        return fragments[:5]  # Return up to 5 fragments
    
    def _extract_text_fragments(self, text: str) -> List[str]:
        """Extract text fragments from unstructured text."""
        fragments = []
        
        # Extract bullet points or numbered items
        bullet_items = re.findall(r'(?:^|\n)[•\-*]\s*(.*?)(?=(?:\n[•\-*])|$)', text, re.MULTILINE)
        if bullet_items:
            fragments.extend(bullet_items)
        
        # Extract numbered items if no bullet points found
        if not fragments:
            numbered_items = re.findall(r'(?:^|\n)\d+\.\s*(.*?)(?=(?:\n\d+\.)|$)', text, re.MULTILINE)
            if numbered_items:
                fragments.extend(numbered_items)
        
        # If still no fragments, split by newlines and take non-empty lines
        if not fragments:
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            fragments.extend(lines)
        
        return fragments
    
    def _get_default_fragments(self, prompt: str) -> List[str]:
        """Get default context fragments based on the prompt."""
        return [
            f"Information about {prompt}",
            f"Key concepts related to {prompt}",
            f"Common questions about {prompt}"
        ]


# Create singleton instances for use in the API
gemini_client = GeminiClient()

def get_response_generator(use_case: str = "insurance") -> ResponseGenerator:
    """Get a ResponseGenerator instance for the specified use case."""
    return ResponseGenerator(gemini_client, use_case)

# Public API functions that maintain backward compatibility
def get_assistant_response(prompt: str, use_case: str = "insurance") -> str:
    """Get a complete response from the assistant."""
    response_generator = get_response_generator(use_case)
    return response_generator.get_assistant_response(prompt)

def stream_assistant_response(prompt: str, use_case: str = "insurance") -> Generator[str, None, None]:
    """Stream the assistant's response."""
    response_generator = get_response_generator(use_case)
    return response_generator.stream_assistant_response(prompt)

def generate_context(prompt: str, use_case: str = "insurance") -> List[str]:
    """Generate context fragments for a prompt."""
    response_generator = get_response_generator(use_case)
    return response_generator.generate_context(prompt)

