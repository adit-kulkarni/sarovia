from fastapi import FastAPI, WebSocket, Query, Body, HTTPException, Request, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import base64
import asyncio
import websockets
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import os
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import requests
import logging
import uuid
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import aiohttp
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
import httpx
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
import re
from openai import AsyncOpenAI
import warnings
from supabase import create_client, Client
import numpy as np
from collections import defaultdict, Counter
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

# Import the optimized lesson summary
from optimized_lesson_summary import get_lesson_summary_optimized

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Add connection management and task queue classes
class DatabaseManager:
    def __init__(self, supabase_client):
        self.client = supabase_client
        self._connection_semaphore = asyncio.Semaphore(10)  # Limit concurrent DB operations
    
    async def execute_query(self, query_func):
        """Execute database queries with connection limiting"""
        async with self._connection_semaphore:
            return await asyncio.get_event_loop().run_in_executor(None, query_func)

class BackgroundTaskManager:
    def __init__(self):
        self._task_queue = asyncio.Queue(maxsize=100)  # Limit queue size
        self._worker_semaphore = asyncio.Semaphore(5)  # Limit concurrent background tasks
        self._workers = []
    
    async def start_workers(self, num_workers=3):
        """Start background worker tasks"""
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)
    
    async def _worker(self):
        """Background worker to process tasks"""
        while True:
            try:
                task_func, args, kwargs = await self._task_queue.get()
                async with self._worker_semaphore:
                    try:
                        if asyncio.iscoroutinefunction(task_func):
                            await task_func(*args, **kwargs)
                        else:
                            # Run synchronous functions in thread pool
                            await asyncio.get_event_loop().run_in_executor(None, task_func, *args, **kwargs)
                    except Exception as e:
                        logging.error(f"Background task error: {e}")
                self._task_queue.task_done()
            except Exception as e:
                logging.error(f"Worker error: {e}")
                await asyncio.sleep(1)  # Brief pause on error
    
    async def submit_task(self, task_func, *args, **kwargs):
        """Submit a task to the background queue"""
        try:
            await self._task_queue.put((task_func, args, kwargs))
        except asyncio.QueueFull:
            logging.warning("Background task queue is full, dropping task")
    
    def submit_task_nowait(self, task_func, *args, **kwargs):
        """Submit a task without waiting (non-blocking)"""
        try:
            self._task_queue.put_nowait((task_func, args, kwargs))
        except asyncio.QueueFull:
            logging.warning("Background task queue is full, dropping task")

# Load environment variables
load_dotenv()

# Initialize Sentry for error monitoring
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            FastApiIntegration(),
            AsyncioIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
        profiles_sample_rate=0.1,  # 10% for profiling
        environment=os.getenv("ENVIRONMENT", "production"),
        before_send=lambda event, hint: event if event.get('level') != 'info' else None  # Filter out info logs
    )
    logging.info("Sentry initialized for error monitoring")
else:
    logging.warning("SENTRY_DSN not found - error monitoring disabled")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
supabase = create_client(url, key)

# Initialize database manager
db_manager = DatabaseManager(supabase)
# task_manager = BackgroundTaskManager()  # Temporarily disabled

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("API key is missing. Please set the 'OPENAI_API_KEY' environment variable.")

# Interaction mode configuration - can be "audio" or "text"
INTERACTION_MODE = os.getenv("INTERACTION_MODE", "audio")

WS_URL = 'wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17'

# Initialize spaCy models
nlp_models = {}

def get_nlp_model(language: str):
    """Get or load spaCy model for the specified language"""
    global nlp_models
    
    if not SPACY_AVAILABLE:
        logging.warning("spaCy not available, NLP features will be limited")
        return None
    
    if language in nlp_models:
        return nlp_models[language]
    
    # Map language codes to spaCy model names
    spacy_models = {
        'en': 'en_core_web_sm',
        'es': 'es_core_news_sm',
        'fr': 'fr_core_news_sm',
        'de': 'de_core_news_sm',
        'it': 'it_core_news_sm',
        'pt': 'pt_core_news_sm'
    }
    
    model_name = spacy_models.get(language, 'en_core_web_sm')
    
    try:
        nlp_models[language] = spacy.load(model_name)
        logging.info(f"Loaded spaCy model {model_name} for language {language}")
        return nlp_models[language]
    except OSError:
        logging.warning(f"spaCy model {model_name} not found, NLP features will be limited")
        return None
    except Exception as e:
        logging.warning(f"Error loading spaCy model: {e}")
        return None

# Language configuration
LANGUAGES = {
    'en': 'English',
    'it': 'Italian',
    'es': 'Spanish',
    'pt': 'Portuguese',
    'fr': 'French',
    'de': 'German',
    'kn': 'Kannada'
}

# Voice agent instruction system configuration
BASE_PROMPT_TEMPLATE = """
🎓 STUDENT LEVEL
The student is at {level} level, knowing approximately {word_count} common {language_name} words and simple phrases. They can form very basic sentences primarily in the {tenses} only.

🗣️ SPEAKING RULES - Stick to the following rules as closely as you can to ensure the best user experience. Break the rules sparingly, only if absolutely necessary to continue conversation.
Speak {speech_speed}. The maximum sentence length is {max_sentence_length} words
The maximum message length is {max_message_length} words
Speak in the following tenses only: {tenses}

Start every sentence with {language_name}.
<!-- COMMENTED OUT FOR NOW: and provide an English translation for every sentence AFTER the {language_name}. -->

💬 CONVERSATION ENGAGEMENT RULES - CRITICAL for keeping dialogue flowing:
- ALWAYS ask questions to keep the student talking. Never just make statements.
- Turn your responses into conversation starters: Instead of "Me gusta correr" say "Me gusta correr, ¿a ti también te gusta?" / "I like running, do you like it too?"
- Share personal opinions/experiences with hooks for follow-up: "Me gusta correr, pero a veces me duelen las piernas" / "I like running, but sometimes my legs hurt"
- Invite students to ask YOU questions: "Me encanta viajar, ¿quieres saber adónde voy?" / "I love traveling, do you want to know where I go?"
- Use conversation bridges like: "Y tú, ¿qué piensas?" / "And you, what do you think?"

🎯 LEVEL-SPECIFIC CONVERSATION STYLE:
{conversation_style}

🎭 SPEAKING CONTEXT/ROLEPLAY
{context_instructions}

🎯 TOPIC ADHERENCE - CRITICAL RULES
- NEVER deviate from the context theme. If the student tries to change topics, gently redirect them back to the context.
- ALL your responses must relate directly to the context scenario. Do not discuss unrelated topics.
- If conversation naturally reaches an end point, either:
  a) Ask if they want to end the conversation: "¿Quieres terminar nuestra conversación?" / "Do you want to end our conversation?"
  b) Suggest a new angle within the same context: "Hablemos de otro aspecto de [context topic]" / "Let's talk about another aspect of [context topic]"
- Stay in character throughout the entire conversation. Your role and personality are defined by the context instructions above.

❓ EXAMPLE CONVERSATION STARTERS - These are example phrases to inspire your conversation style. You can use them, adapt them, or create similar ones. Focus on natural conversation flow, not just repeating phrases:
{starter_questions}

Your primary goal is to have a smooth, engaging conversation that stays in character and within the context theme. Use these examples as inspiration for the style and complexity level, but prioritize natural dialogue over using specific phrases.

🔄 CONVERSATION FLOW EXAMPLES:
Instead of: "Me gusta la comida italiana." / "I like Italian food."
Say: "Me gusta la comida italiana, ¿cuál es tu comida favorita?" / "I like Italian food, what's your favorite food?"

Instead of: "Voy al gimnasio." / "I go to the gym."
Say: "Voy al gimnasio todos los días, pero es difícil. ¿Tú haces ejercicio?" / "I go to the gym every day, but it's hard. Do you exercise?"

Always end with questions, opinions that invite response, or invitations for the student to ask you something!

🛠️ WHEN STUDENTS MAKE MISTAKES
Correct gently and clearly and then continue conversation. If the mistake is major ask the student to try saying it again

⚠️ IMPORTANT
- Never break character or persona
- Never stray from the context topic  
- Focus on natural conversation flow while staying within your level constraints
- If conversation stalls, reinvigorate it with new questions or perspectives within the same context theme
- PRIORITIZE asking questions over making statements - your job is to get the student talking
- Every response should encourage the student to share more or ask you something back
- Be engaging and curious about the student's thoughts and experiences
"""

# Level-specific configurations
LEVEL_CONFIG = {
    "A1": {
        "word_count": "150-250",
        "tenses": "present tense",
        "speech_speed": "very slowly with clear pauses between sentences",
        "max_sentence_length": "6",
        "max_message_length": "20",
        "conversation_style": "Ask very simple, direct questions. Use basic question words: ¿Qué? ¿Dónde? ¿Te gusta? ¿Tienes? Always encourage them to respond."
    },
    "A2": {
        "word_count": "250-500", 
        "tenses": "present tense and simple past tense",
        "speech_speed": "slowly with clear pronunciation",
        "max_sentence_length": "10",
        "max_message_length": "30",
        "conversation_style": "Ask simple questions and share basic opinions with follow-up questions. Use ¿Por qué? and ¿Cómo? to encourage elaboration."
    },
    "B1": {
        "word_count": "500-1000",
        "tenses": "present, past, and simple future tenses",
        "speech_speed": "at moderate pace with clear articulation",
        "max_sentence_length": "15",
        "max_message_length": "50",
        "conversation_style": "Share more detailed opinions with open-ended questions. Use phrases like 'Me parece que...' and ask '¿Qué opinas tú?'"
    },
    "B2": {
        "word_count": "1000-2000",
        "tenses": "all major tenses including conditional and subjunctive",
        "speech_speed": "at normal conversational pace",
        "max_sentence_length": "20",
        "max_message_length": "75",
        "conversation_style": "Engage in nuanced discussions with hypothetical questions and personal anecdotes that invite sharing."
    },
    "C1": {
        "word_count": "2000-4000",
        "tenses": "all tenses with complex grammatical structures",
        "speech_speed": "at native-like pace with natural flow",
        "max_sentence_length": "25",
        "max_message_length": "100",
        "conversation_style": "Use sophisticated conversation techniques with abstract concepts and encourage critical thinking through probing questions."
    },
    "C2": {
        "word_count": "4000+",
        "tenses": "all tenses with advanced nuanced expressions",
        "speech_speed": "at full native pace with cultural nuances",
        "max_sentence_length": "30",
        "max_message_length": "120",
        "conversation_style": "Engage in highly sophisticated discourse with cultural references, subtle humor, and complex philosophical questions."
    }
}

def get_level_variables(level: str, language: str) -> dict:
    """Get level-specific variables for the base prompt template"""
    config = LEVEL_CONFIG.get(level, LEVEL_CONFIG["A1"])
    language_name = LANGUAGES.get(language, language)
    
    return {
        "level": level,
        "word_count": config["word_count"],
        "language_name": language_name,
        "tenses": config["tenses"],
        "speech_speed": config["speech_speed"],
        "max_sentence_length": config["max_sentence_length"],
        "max_message_length": config["max_message_length"],
        "conversation_style": config.get("conversation_style", "Ask engaging questions to keep the conversation flowing.")
    }

def format_starter_questions(questions: List[str]) -> str:
    """Format starter questions for the prompt"""
    if not questions:
        return "No specific starter questions available - be creative!"
    
    # Format with semicolons for better structure and readability
    formatted_questions = []
    for q in questions:
        formatted_questions.append(f'"{q}"')
    
    return "; ".join(formatted_questions)

def get_personalized_context_starter_questions(context_id: str, level: str, user_id: str) -> List[str]:
    """Get level-specific starter questions for a personalized context"""
    if not context_id.startswith('user_') or not user_id:
        return []
    
    try:
        level_column = f"{level.lower()}_phrases"
        result = supabase.table('personalized_contexts').select(level_column).eq('id', context_id).eq('user_id', user_id).execute()
        
        if result.data and len(result.data) > 0:
            phrases = result.data[0].get(level_column, [])
            return phrases if phrases else []
        
    except Exception as e:
        logging.error(f"Error fetching starter questions for context {context_id}, level {level}: {e}")
    
    return []

def get_feedback_categories(interaction_type: str = "audio") -> dict:
    """Return appropriate feedback categories based on interaction type"""
    
    base_categories = {
        "grammar": ["verb tense", "verb usage", "subject-verb agreement", "article usage", 
                   "preposition usage", "pluralization", "auxiliary verb usage", 
                   "modal verb usage", "pronoun agreement", "negation", 
                   "comparatives/superlatives", "conditional structures", 
                   "passive voice", "question formation", "other"],
        "vocabulary": ["word meaning error", "false friend", "missing word", 
                      "extra word", "word form", "other"],
        "syntax": ["word order", "run-on sentence", "fragment/incomplete sentence", "other"],
        "word choice": ["unnatural phrasing", "contextually inappropriate word", 
                       "idiomatic error", "register mismatch", "other"],
        "register/formality": ["informal in formal context", "formal in informal context", "other"]
    }
    
    if interaction_type == "text":
        # Only add spelling and punctuation for text interactions
        # For audio/voice interactions, we skip these categories to avoid penalizing transcription errors
        base_categories.update({
            "spelling": ["common spelling error", "homophone confusion", "other"],
            "punctuation": ["missing punctuation", "comma splice", "run-on sentence", 
                           "quotation mark error", "other"]
        })
    
    return base_categories

def format_categories_for_prompt(categories: dict) -> str:
    """Format categories dictionary into prompt text"""
    category_lines = []
    for category, types in categories.items():
        types_str = ", ".join(types)
        category_lines.append(f"        - {category}: {types_str}")
    return "\n" + "\n".join(category_lines)

async def get_existing_language_tags(language: str, limit: int = 30) -> List[str]:
    """Get most commonly used language feature tags for this language"""
    try:
        result = supabase.table('language_feature_tags') \
            .select('tag_name') \
            .eq('language', language) \
            .order('usage_count', desc=True) \
            .limit(limit) \
            .execute()
        
        return [row['tag_name'] for row in result.data]
    except Exception as e:
        logging.warning(f"Error fetching existing language tags: {e}")
        return []

async def upsert_language_tag(tag_name: str, language: str) -> None:
    """Create or update a language feature tag usage count"""
    try:
        # First try to increment existing tag
        existing = supabase.table('language_feature_tags') \
            .select('id, usage_count') \
            .eq('tag_name', tag_name) \
            .eq('language', language) \
            .execute()
        
        if existing.data:
            # Update usage count
            new_count = existing.data[0]['usage_count'] + 1
            supabase.table('language_feature_tags') \
                .update({'usage_count': new_count, 'updated_at': 'now()'}) \
                .eq('id', existing.data[0]['id']) \
                .execute()
        else:
            # Create new tag
            supabase.table('language_feature_tags') \
                .insert({
                    'tag_name': tag_name,
                    'language': language,
                    'usage_count': 1
                }) \
                .execute()
                
    except Exception as e:
        logging.warning(f"Error upserting language tag {tag_name}: {e}")

async def record_language_tags(tags: List[str], language: str) -> None:
    """Record usage of language feature tags"""
    if not tags:
        return
    
    # Filter and clean tags
    clean_tags = []
    for tag in tags:
        if tag and isinstance(tag, str) and len(tag.strip()) > 0:
            # Basic cleanup and validation
            clean_tag = tag.lower().strip().replace(' ', '_')
            # Filter out obvious invalid tags
            if (len(clean_tag) > 2 and 
                clean_tag not in ['a1', 'a2', 'b1', 'b2', 'c1', 'c2'] and
                clean_tag not in ['minor', 'moderate', 'critical'] and
                clean_tag not in ['grammar', 'vocabulary', 'syntax'] and
                not clean_tag.isdigit()):
                clean_tags.append(clean_tag)
    
    # Record each tag
    for tag in clean_tags:
        await upsert_language_tag(tag, language)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://localhost:3000",
        "https://frontend-efaqqvgby-adit-kulkarnis-projects.vercel.app",
        "https://frontend-ruby-five-82.vercel.app",
        "https://frontend-git-main-adit-kulkarnis-projects.vercel.app",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Sarovia Language Learning API is running!", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "sarovia-api"}

@app.get("/debug/openai")
async def debug_openai():
    """Debug endpoint to test OpenAI connection"""
    try:
        # Check if API key is set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"error": "OPENAI_API_KEY environment variable not set"}
        
        # Check API key format
        if not api_key.startswith("sk-"):
            return {"error": "Invalid API key format (should start with 'sk-')"}
        
        # Test basic OpenAI API connection (not realtime)
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                return {
                    "status": "success", 
                    "message": "OpenAI API key is valid",
                    "api_key_prefix": api_key[:7] + "..." if len(api_key) > 7 else "too_short"
                }
            else:
                return {
                    "error": f"OpenAI API returned status {response.status_code}",
                    "response": response.text[:200]
                }
                
    except Exception as e:
        return {"error": f"Failed to test OpenAI connection: {str(e)}"}

@app.get("/debug/websocket")
async def debug_websocket():
    """Debug endpoint to test WebSocket connection to OpenAI"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"error": "OPENAI_API_KEY environment variable not set"}
        
        # Test WebSocket connection
        import websockets
        import asyncio
        
        ws_url = 'wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17'
        headers = {
            'Authorization': f'Bearer {api_key}',
            'OpenAI-Beta': 'realtime=v1'
        }
        
        try:
            ws = await websockets.connect(
                ws_url,
                extra_headers=headers,
                timeout=10
            )
            await ws.close()
            return {
                "status": "success",
                "message": "WebSocket connection to OpenAI Realtime API successful",
                "url": ws_url
            }
        except websockets.exceptions.InvalidStatusCode as e:
            return {
                "error": "WebSocket connection failed",
                "status_code": e.status_code,
                "response_headers": dict(e.response_headers) if hasattr(e, 'response_headers') else None,
                "details": str(e)
            }
        except Exception as e:
            return {
                "error": "WebSocket connection failed",
                "exception_type": type(e).__name__,
                "details": str(e)
            }
            
    except Exception as e:
        return {"error": f"Failed to test WebSocket connection: {str(e)}"}

@app.get("/debug/sentry-test")
async def test_sentry_error(token: str = Query(...)):
    """🧪 Secret debug endpoint to test Sentry error tracking - requires authentication"""
    try:
        # Verify user is authenticated
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        user_email = user_payload.get("email", "unknown")
        
        # Add some context for testing
        if sentry_dsn:
            sentry_sdk.add_breadcrumb(
                message="User triggered Sentry test",
                data={
                    "user_id": user_id,
                    "user_email": user_email,
                    "test_type": "manual_debug_endpoint"
                },
                level="info"
            )
            sentry_sdk.set_tag("test_error", True)
            sentry_sdk.set_tag("debug_endpoint", "/debug/sentry-test")
            sentry_sdk.set_context("debug_test", {
                "endpoint": "/debug/sentry-test",
                "user_triggered": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "user_email": user_email
            })
        
        # Deliberately throw a test error with user context
        raise Exception(f"🧪 SENTRY TEST ERROR - This is intentional! User: {user_email} ({user_id[:8]}...) at {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
        
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Authentication required for debug endpoints")
    except Exception as e:
        # Let FastAPI handle the error gracefully while Sentry captures it
        if "SENTRY TEST ERROR" in str(e):
            # This is our test error - let Sentry capture it but return a success response
            return {
                "status": "success", 
                "message": "🎯 Test error thrown successfully! Check your Sentry dashboard in a few seconds.",
                "error_preview": str(e)[:100] + "...",
                "sentry_enabled": sentry_dsn is not None,
                "instructions": "Look for the error in Sentry dashboard with your user email/ID attached"
            }
        else:
            # This is an unexpected error - let it bubble up
            raise HTTPException(status_code=500, detail=f"Unexpected error in test: {str(e)}")

# Startup will be handled by the main execution at the bottom of the file


# Store active connections
active_connections = {}

SUPABASE_PROJECT_REF = "tobnmxaytsknubdpzpnf"
SUPABASE_JWT_ISSUER = f"https://{SUPABASE_PROJECT_REF}.supabase.co/auth/v1"
SUPABASE_JWT_AUDIENCE = 'authenticated'
JWKS_URL = f"{SUPABASE_JWT_ISSUER}/.well-known/jwks.json"
JWKS = requests.get(JWKS_URL).json()

def get_public_key(token):
    unverified_header = jwt.get_unverified_header(token)
    for key in JWKS['keys']:
        if key['kid'] == unverified_header['kid']:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)
    raise Exception("Public key not found.")

def verify_jwt(token):
    try:
        # First try to decode without verification to check the algorithm
        unverified_header = jwt.get_unverified_header(token)
        algorithm = unverified_header.get('alg', 'RS256')
        
        if algorithm == 'HS256':
            if not jwt_secret:
                raise jwt.InvalidTokenError("JWT secret not configured for HS256")
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience=SUPABASE_JWT_AUDIENCE,
                issuer=SUPABASE_JWT_ISSUER,
            )
        else:  # RS256
            public_key = get_public_key(token)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=SUPABASE_JWT_AUDIENCE,
                issuer=SUPABASE_JWT_ISSUER,
            )
        
        # Add user context to Sentry for debugging
        if sentry_dsn:
            sentry_sdk.set_user({
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "username": payload.get("email", "").split("@")[0] if payload.get("email") else None
            })
        
        return payload
    except ExpiredSignatureError:
        raise jwt.InvalidTokenError("Token has expired")
    except Exception as e:
        print(f"JWT verification error: {str(e)}")  # Add detailed logging
        raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")

async def connect_to_openai():
    """Establish WebSocket connection with OpenAI"""
    try:
        logging.info(f"[OpenAI] Attempting to connect to WebSocket URL: {WS_URL}")
        logging.info(f"[OpenAI] Using API key prefix: {API_KEY[:7]}...")
        
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'OpenAI-Beta': 'realtime=v1'
        }
        logging.info(f"[OpenAI] Headers: {dict((k, v[:20] + '...' if k == 'Authorization' else v) for k, v in headers.items())}")
        
        ws = await websockets.connect(
            WS_URL,
            extra_headers=headers,
            timeout=30  # Add explicit timeout
        )
        logging.info(f"[OpenAI] WebSocket connection established successfully")
        return ws
    except websockets.exceptions.InvalidStatusCode as e:
        logging.error(f"[OpenAI] Invalid status code: {e.status_code} - {e}")
        logging.error(f"[OpenAI] Response headers: {e.response_headers}")
        return None
    except websockets.exceptions.ConnectionClosed as e:
        logging.error(f"[OpenAI] Connection closed: {e.code} - {e.reason}")
        return None
    except asyncio.TimeoutError as e:
        logging.error(f"[OpenAI] Connection timeout: {e}")
        return None
    except Exception as e:
        logging.error(f"[OpenAI] Unexpected error connecting to OpenAI: {type(e).__name__}: {e}")
        import traceback
        logging.error(f"[OpenAI] Full traceback: {traceback.format_exc()}")
        return None

async def forward_to_openai(ws: websockets.WebSocketClientProtocol, message: dict):
    """Forward message to OpenAI"""
    try:
        await ws.send(json.dumps(message))
    except Exception as e:
        print(f"Error forwarding to OpenAI: {e}")

def get_context_specific_instructions(context: str, language: str) -> str:
    """Generate context-specific instructions for the AI"""
    context_guidelines = {
        "restaurant": (
            f"You are a {LANGUAGES[language]} restaurant server at a unique restaurant. Your role is to:\n"
            "CREATIVITY & VARIATION:\n"
            "- Create a different restaurant concept each conversation (family bistro, upscale dining, cozy trattoria, modern café, traditional tavern, etc.)\n"
            "- Vary the restaurant name, cuisine style, atmosphere, and specialties each time\n"
            "- Develop a unique personality and backstory for your server character\n\n"
            "ROLEPLAY GUIDELINES:\n"
            "- Stay fully in character as a restaurant server - this creates immersive language practice\n"
            "- However, remember this is for language learning: you may break character briefly to provide language help when needed\n"
            "- If the student struggles significantly, offer explanations or simpler alternatives while staying mostly in role\n\n"
            "AUTHENTIC INTERACTIONS:\n"
            "- Start with a warm, specific greeting that establishes your restaurant's character\n"
            "- Be knowledgeable about your restaurant's unique menu, specialties, and daily specials\n"
            "- Make personalized recommendations based on customer preferences\n"
            "- Handle special requests naturally and helpfully\n"
            "- Maintain a friendly but professional demeanor\n"
            "- Keep the conversation flowing naturally while managing your duties\n\n"
            "Example interaction styles (vary these significantly):\n"
            "- Family restaurant: 'Welcome to our family kitchen! We've been serving homemade pasta for three generations.'\n"
            "- Modern bistro: 'Good evening! Our farm-to-table menu changes daily based on what's fresh.'\n"
            "- Traditional tavern: 'Come in, come in! Try our signature dish - it's a local favorite for 50 years.'"
        ),
        "drinks": (
            f"You are someone at a {LANGUAGES[language]} bar or café. Your role is to:\n"
            "CREATIVITY & VARIATION:\n"
            "- Create different venue types each conversation (craft cocktail bar, cozy wine bar, trendy café, neighborhood pub, rooftop lounge, etc.)\n"
            "- Vary your character's background, interests, and reason for being there\n"
            "- Develop unique venue characteristics, specialties, and atmosphere\n\n"
            "ROLEPLAY GUIDELINES:\n"
            "- Stay in character as a friendly patron enjoying the venue\n"
            "- Remember this is for language learning: briefly break character to help with language when needed\n"
            "- Maintain natural conversation flow while providing learning opportunities\n\n"
            "AUTHENTIC INTERACTIONS:\n"
            "- Start with a natural, context-appropriate introduction\n"
            "- Share genuine interests and experiences related to the venue\n"
            "- Respond naturally to conversation while maintaining appropriate boundaries\n"
            "- Show personality while being respectful\n"
            "- Keep the conversation engaging and authentic\n\n"
            "Example character types (vary significantly):\n"
            "- Regular customer: 'I've been coming here for years - they know exactly how I like my coffee.'\n"
            "- Visiting for special event: 'I'm here for the wine tasting. Are you here for that too?'\n"
            "- Local enthusiast: 'This place has the best craft beer selection in the neighborhood.'"
        ),
        "introduction": (
            f"You are meeting someone new in a {LANGUAGES[language]} setting. Your role is to:\n"
            "CREATIVITY & VARIATION:\n"
            "- Create different meeting contexts each conversation (conference, party, coffee shop, gym, class, park, bookstore, etc.)\n"
            "- Vary your character's background, profession, interests, and personality traits\n"
            "- Develop unique conversation starters and shared contexts\n\n"
            "ROLEPLAY GUIDELINES:\n"
            "- Stay in character as someone naturally meeting a new person\n"
            "- Remember this is for language learning: offer gentle help with language when needed\n"
            "- Model natural conversation patterns and cultural norms for introductions\n\n"
            "AUTHENTIC INTERACTIONS:\n"
            "- Start with a natural, context-appropriate greeting and introduction\n"
            "- Share specific, genuine details about yourself and your interests\n"
            "- Show interest in the other person's background and experiences\n"
            "- Find natural connection points in the conversation\n"
            "- Keep the conversation light but meaningful\n\n"
            "Example meeting contexts (vary significantly):\n"
            "- Student setting: 'I'm also taking this literature course. Are you enjoying the reading so far?'\n"
            "- Social event: 'I love this band! Have you heard their new album? I'm Maria, by the way.'\n"
            "- Professional: 'You look familiar - do you work in the marketing building downtown?'"
        ),
        "market": (
            f"You are a vendor at a {LANGUAGES[language]} market or shop. Your role is to:\n"
            "CREATIVITY & VARIATION:\n"
            "- Create different market/shop types each conversation (farmers market, spice shop, bakery, cheese store, flower market, artisan crafts, etc.)\n"
            "- Vary your business background, family history, and specialties\n"
            "- Develop unique product stories and vendor personality\n\n"
            "ROLEPLAY GUIDELINES:\n"
            "- Stay fully in character as a passionate vendor who knows their products\n"
            "- Remember this is for language learning: offer help with product names and market vocabulary when needed\n"
            "- Model authentic market interactions and cultural shopping customs\n\n"
            "AUTHENTIC INTERACTIONS:\n"
            "- Start with a warm, welcoming greeting that reflects your shop's character\n"
            "- Be knowledgeable about your specific products and their unique qualities\n"
            "- Share personal stories about your products or business heritage\n"
            "- Handle negotiations naturally while maintaining professionalism\n"
            "- Keep the conversation informative but friendly\n\n"
            "Example vendor types (vary significantly):\n"
            "- Family baker: 'These pastries are made from my grandmother's secret recipe passed down four generations.'\n"
            "- Artisan vendor: 'I handcraft each piece of jewelry using traditional techniques from my hometown.'\n"
            "- Produce seller: 'This fruit comes directly from organic farms in the mountains - taste the difference!'"
        ),
        "karaoke": (
            f"You are at a {LANGUAGES[language]} karaoke venue or music event. Your role is to:\n"
            "CREATIVITY & VARIATION:\n"
            "- Create different venue types each conversation (karaoke bar, private room, community center, music cafe, outdoor festival, etc.)\n"
            "- Vary your music preferences, experience level, and reason for being there\n"
            "- Develop unique venue characteristics and crowd atmosphere\n\n"
            "ROLEPLAY GUIDELINES:\n"
            "- Stay in character as an enthusiastic music lover at the event\n"
            "- Remember this is for language learning: help with music vocabulary and cultural expressions when needed\n"
            "- Model natural social interactions around music and performance\n\n"
            "AUTHENTIC INTERACTIONS:\n"
            "- Start with an enthusiastic, music-focused greeting\n"
            "- Share genuine enthusiasm for music and the venue atmosphere\n"
            "- Encourage participation naturally without being pushy\n"
            "- Share personal experiences with songs, genres, or performances\n"
            "- Keep the energy high but authentic to the setting\n\n"
            "Example character types (vary significantly):\n"
            "- Karaoke regular: 'I perform here every Friday night - the acoustics in this room are incredible!'\n"
            "- First-timer: 'This is my first time at karaoke! I'm nervous but excited. What song would you recommend?'\n"
            "- Music enthusiast: 'I love discovering new songs through karaoke. Have you heard this local artist before?'"
        ),
        "city": (
            f"You are a local person in a {LANGUAGES[language]} city. Your role is to:\n"
            "CREATIVITY & VARIATION:\n"
            "- Create different cities and urban settings each conversation (historic center, modern district, coastal town, mountain city, etc.)\n"
            "- Vary your role (local resident, tour guide, shop owner, student, artist, etc.) and knowledge level\n"
            "- Develop unique neighborhood characteristics and local culture\n\n"
            "ROLEPLAY GUIDELINES:\n"
            "- Stay in character as someone who genuinely knows and loves their city\n"
            "- Remember this is for language learning: help with city vocabulary and cultural concepts when needed\n"
            "- Model authentic local interactions and cultural pride\n\n"
            "AUTHENTIC INTERACTIONS:\n"
            "- Start with a warm, locally-appropriate greeting\n"
            "- Share insider knowledge about neighborhoods, attractions, and hidden gems\n"
            "- Make personalized recommendations based on the visitor's interests\n"
            "- Share local stories, cultural insights, and personal experiences\n"
            "- Keep the conversation informative and engaging\n\n"
            "Example local perspectives (vary significantly):\n"
            "- Long-time resident: 'I've lived here 30 years and still discover new places. This neighborhood has such character!'\n"
            "- Young local: 'All the artists hang out in this area - there's amazing street art and great coffee shops.'\n"
            "- Cultural enthusiast: 'You have to see the evening light on these old buildings. It's magical at sunset.'"
        )
    }
    return context_guidelines.get(context, context_guidelines["restaurant"])

def get_level_specific_instructions(level: str, context: str, language: str, user_id: str = None) -> str:
    """Generate level-specific instructions using the new base prompt template"""
    # Get level-specific variables
    level_vars = get_level_variables(level, language)
    
    # Get context-specific instructions
    context_instructions = get_context_specific_instructions_extended(context, language, user_id)
    
    # Get starter questions for personalized contexts
    starter_questions = []
    if context.startswith('user_') and user_id:
        starter_questions = get_personalized_context_starter_questions(context, level, user_id)
    
    # Format starter questions
    formatted_questions = format_starter_questions(starter_questions)
    
    # Combine all variables for the template
    template_vars = {
        **level_vars,
        "context_instructions": context_instructions,
        "starter_questions": formatted_questions
    }
    
    # Generate the final instructions using the base template
    return BASE_PROMPT_TEMPLATE.format(**template_vars)

async def process_feedback_background(message_id: str, language: str, level: str, client_ws: WebSocket, interaction_type: str = "audio"):
    """Process feedback in the background without blocking the conversation"""
    try:
        # Use database manager for async execution
        def get_message():
            return supabase.table('messages').select('*').eq('id', message_id).execute()
        
        message_result = await db_manager.execute_query(get_message)
        if not message_result.data:
            logging.error(f"[Background] Message not found: message_id={message_id}")
            return
        
        message = message_result.data[0]
        original_message = message['content']
        
        # Skip feedback for very short messages or common responses
        if len(original_message.strip()) < 3:
            logging.info(f"[Background] Skipping feedback for very short message: {original_message}")
            return
        
        # Get conversation context
        conversation_result = supabase.table('conversations').select('*').eq('id', message['conversation_id']).execute()
        if not conversation_result.data:
            logging.error(f"[Background] Conversation not found for message_id={message_id}")
            return
        
        conversation = conversation_result.data[0]
        
        # Get recent messages for context
        context_messages = supabase.table('messages').select('*').eq('conversation_id', message['conversation_id']).order('created_at', desc=True).limit(5).execute()
        
        # Get appropriate categories based on interaction type
        categories = get_feedback_categories(interaction_type)
        category_text = format_categories_for_prompt(categories)
        
        # Build category options for JSON format
        category_options = "|".join(categories.keys())
        
        # Get existing language tags for this language
        existing_tags = await get_existing_language_tags(language, limit=25)
        
        # Format existing tags for prompt
        if existing_tags:
            tag_guidance = f"""
        
Existing language feature tags (prefer these when the error fits):
{', '.join(existing_tags)}

Tag assignment strategy:
1. CHECK if the error matches an EXISTING tag above - use it if appropriate
2. Only create a NEW tag if the linguistic pattern is truly different
3. New tags should follow the naming style you see: underscores, specific, concise
4. Maximum 3 tags per mistake, focus on the most teachable aspects
5. Examples of good tags: "past_tense", "ser_vs_estar", "noun_gender", "question_formation"

Remember: Consistency helps students see patterns in their learning!
            """
        else:
            tag_guidance = """
        
Language feature tag guidelines:
- Use underscores for multi-word concepts: "past_tense", "noun_gender"
- Be specific but concise: "question_formation" not "questions"
- Focus on teachable grammatical patterns
- Maximum 3 tags per mistake, prioritize the most relevant
- Examples: "past_tense", "ser_vs_estar", "noun_gender", "conditional_mood"
            """
        
        # Prepare the prompt for OpenAI
        prompt = f"""Analyze the following message in {language} for language learning feedback.
        Student Level: {level}
        Context: {conversation['context']}
        Interaction Type: {interaction_type}
        
        Recent conversation context:
        {format_conversation_context(context_messages.data)}
        
        Message to analyze: "{original_message}"
        
        🎙️ VOICE TRANSCRIPTION CONSIDERATIONS - CRITICAL:
        This is a voice-based language learning app, so the text comes from speech transcription. Be very forgiving of:
        
        1. SPELLING ERRORS: Do NOT penalize spelling mistakes or typos - these are likely transcription errors, not language errors
        2. MISSING ACCENTS: Do NOT penalize missing accent marks (á, é, í, ó, ú, ñ, etc.) - transcription often misses these
        3. PUNCTUATION: Do NOT penalize missing or incorrect punctuation - focus only on spoken language errors
        4. WORD REPETITIONS: If a user repeats a word (e.g., "yo yo voy"), this is often natural speech hesitation - only flag if it affects meaning
        5. MINOR TRANSCRIPTION ARTIFACTS: Ignore "um", "uh", filler words, or slight transcription variations
        
        FOCUS ON: Grammar, vocabulary choice, syntax, sentence structure, and meaningful language use errors that indicate actual language learning needs.
        
        📊 SEVERITY ASSESSMENT GUIDELINES:
        🔴 CRITICAL - Errors that significantly impede communication or indicate fundamental misunderstanding:
        • Wrong verb tense in context (using past when present is needed)
        • Major word meaning errors (saying "dead" instead of "tired")
        • Sentence structure so broken it's incomprehensible
        • Using wrong gender for core nouns repeatedly
        
        🟠 MODERATE - Errors that affect clarity but message is still understandable:
        • Minor verb conjugation errors
        • Incorrect articles (el/la confusion)
        • Word order issues that change meaning slightly
        • Inappropriate register (too formal/informal for context)
        
        🟡 MINOR - Errors that don't affect understanding but could be polished:
        • Singular/plural agreement mistakes
        • Missing or incorrect prepositions where meaning is clear
        • Unnatural phrasing that's still comprehensible
        • Small vocabulary improvements
        
        If the message is perfect (no mistakes), return an empty mistakes array.
        If there are mistakes, provide feedback in the following JSON format:
        {{
            "messageId": "{message_id}",
            "originalMessage": "{original_message}",
            "mistakes": [
                {{
                    "category": "{category_options}|other",
                    "type": "<specific mistake type>",
                    "error": "<incorrect text>",
                    "correction": "<corrected text>",
                    "explanation": "<clear explanation>",
                    "severity": "minor|moderate|critical",
                    "languageFeatureTags": ["tag1", "tag2"]
                }}
            ]
        }}
        
        Categories and types must be from the predefined lists:{category_text}
        {tag_guidance}
        
        Important: If the message is perfect for the student's level, return an empty mistakes array.
        Remember: This is voice-based learning - prioritize meaningful language errors over transcription artifacts.
        """
        
        # Call OpenAI API using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.3,
                    "response_format": { "type": "json_object" }
                }
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logging.error(f"[Background] OpenAI API error: {response_text}")
                    return
                
                response_data = await response.json()
                feedback_data = response_data["choices"][0]["message"]["content"]
        
        # Parse and validate the response
        feedback = FeedbackResponse.parse_raw(feedback_data)
        
        # Log the feedback results
        mistake_count = len(feedback.mistakes)
        if mistake_count == 0:
            logging.info(f"[Background] Perfect message detected for message_id={message_id}")
        else:
            logging.info(f"[Background] Found {mistake_count} mistakes for message_id={message_id}")
            for i, mistake in enumerate(feedback.mistakes, 1):
                logging.info(f"[Background] Mistake {i}: category={mistake.category}, type={mistake.type}, severity={mistake.severity}")
        
        # Convert mistakes to dictionaries for database storage
        mistakes_dict = [mistake.dict() for mistake in feedback.mistakes]
        
        # Save feedback to database
        supabase.table('message_feedback').insert({
            'message_id': message_id,
            'original_message': original_message,
            'mistakes': mistakes_dict
        }).execute()
        
        # Cache invalidation moved to post-conversation for better performance
        # Real-time cache updates removed to keep conversation fluent
        
        # Language tag recording moved to post-conversation for better performance
        # Real-time tag processing removed to keep conversation fluent
        
        # Send feedback to client
        await client_ws.send_json({
            "type": "feedback.generated",
            "messageId": message_id,
            "feedback": feedback.dict(),
            "hasMistakes": len(feedback.mistakes) > 0
        })
        logging.info(f"[Background] Feedback sent to client for message_id={message_id}, hasMistakes={len(feedback.mistakes) > 0}")
        
        # Check if suggestion threshold is met after feedback generation
        if len(feedback.mistakes) > 0:  # Only check if there were mistakes
            try:
                # Get user_id from the conversation
                user_result = supabase.table('conversations').select('user_id, curriculum_id').eq('id', conversation['id']).execute()
                if user_result.data:
                    user_data = user_result.data[0]
                    user_id = user_data['user_id']
                    curriculum_id = user_data['curriculum_id']
                    
                    # Check suggestion threshold
                    threshold_check = await check_lesson_suggestion_threshold(user_id, curriculum_id)
                    if threshold_check["needs_suggestion"]:
                        # Send suggestion notification to client
                        await client_ws.send_json({
                            "type": "suggestion.available",
                            "curriculum_id": curriculum_id,
                            "threshold_data": threshold_check
                        })
                        logging.info(f"[Background] Suggestion threshold met for user {user_id}, curriculum {curriculum_id}")
            except Exception as suggestion_error:
                logging.error(f"[Background] Error checking suggestion threshold: {suggestion_error}")
        
    except Exception as e:
        logging.error(f"[Background] Error generating feedback: {e}")
        try:
            await client_ws.send_json({
                "type": "feedback.error",
                "messageId": message_id,
                "error": str(e)
            })
        except Exception as ws_error:
            logging.error(f"[Background] Error sending feedback error to client: {ws_error}")

async def handle_openai_response_with_callback(ws, client_ws, level, context, language, on_openai_session_created, custom_instructions=None, initial_turns=0, vad_settings=None):
    handler_id = str(uuid.uuid4())[:8]
    response_created = False
    conversation_id = None
    openai_session_confirmed = False
    on_openai_session_created_called = False
    current_turns = initial_turns  # Initialize with existing turn count for continuing conversations
    user_id = None  # Track user_id for knowledge updates
    pending_user_message = False  # Track if we have a user message waiting for AI response
    logging.info(f"[Handler {handler_id}] Starting with initial_turns={initial_turns}")
    try:
        while True:
            message = await ws.recv()
            if not message:
                break
            data = json.loads(message)
            event_type = data.get('type')
            # Forward audio events immediately
            if event_type in ['response.audio.delta', 'response.audio.done', 'input_audio_buffer.speech_started']:
                await client_ws.send_json(data)
                continue
            
            # Forward AI transcript events (needed for frontend to display AI messages)
            # but block user transcript events (handled by server to prevent duplicates)
            if event_type == 'response.audio_transcript.done':
                logging.info(f"[Handler {handler_id}] Forwarding response.audio_transcript.done to frontend: {data}")
                await client_ws.send_json(data)
                # Don't continue here - we need to process this event for saving to DB
            
            # Forward other specific events for debugging
            debug_events = ['session.created', 'session.updated', 'error', 'rate_limits.updated']
            if event_type in debug_events:
                await client_ws.send_json(data)
            # Only after OpenAI session.created, create conversation and notify frontend
            if event_type == 'session.created' and not openai_session_confirmed:
                openai_session_confirmed = True
                if not on_openai_session_created_called:
                    on_openai_session_created_called = True
                    conversation_id = await on_openai_session_created()
                    # Get user_id from conversation for knowledge updates
                    if conversation_id:
                        try:
                            conv_result = supabase.table('conversations').select('user_id').eq('id', conversation_id).execute()
                            if conv_result.data:
                                user_id = conv_result.data[0]['user_id']
                        except Exception as e:
                            logging.warning(f"[Handler {handler_id}] Could not get user_id for knowledge updates: {e}")
                    logging.info(f"[Handler {handler_id}] OpenAI session.created confirmed, conversation_id: {conversation_id}, user_id: {user_id}")
                else:
                    logging.warning(f"[Handler {handler_id}] Duplicate OpenAI session.created event ignored.")
                
                # Now send session config and response.create to OpenAI (AFTER conversation is ready)
                instructions_to_send = custom_instructions if custom_instructions else get_level_specific_instructions(level, context, language, user_id)
                logging.info(f"[Handler {handler_id}] Sending session.update with instructions:\n{instructions_to_send}")
                # Configure turn detection based on VAD settings
                logging.info(f"[Handler {handler_id}] VAD settings received: {vad_settings}")
                turn_detection_config = {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
                
                if vad_settings:
                    logging.info(f"[Handler {handler_id}] Processing VAD settings - type: {vad_settings.get('type')}")
                    if vad_settings.get("type") == "semantic":
                        turn_detection_config = {
                            "type": "semantic_vad",
                            "eagerness": vad_settings.get("eagerness", "medium")
                        }
                        logging.info(f"[Handler {handler_id}] Set semantic VAD with eagerness: {vad_settings.get('eagerness', 'medium')}")
                    elif vad_settings.get("type") == "disabled":
                        # For disabled VAD, we'll handle this in the frontend
                        # Keep server_vad but with very high threshold to minimize false triggers
                        turn_detection_config = {
                            "type": "server_vad",
                            "threshold": 0.9,
                            "prefix_padding_ms": 100,
                            "silence_duration_ms": 2000
                        }
                        logging.info(f"[Handler {handler_id}] Set disabled VAD (high threshold server_vad)")
                else:
                    logging.info(f"[Handler {handler_id}] No VAD settings provided, using default server_vad")
                
                session_config = {
                    "type": "session.update",
                    "session": {
                        "instructions": instructions_to_send,
                        "turn_detection": turn_detection_config,
                        "voice": "alloy",
                        "temperature": 1,
                        "max_response_output_tokens": 4096,
                        "modalities": ["text", "audio"],
                        "input_audio_format": "pcm16",
                        "output_audio_format": "pcm16",
                        "input_audio_transcription": {
                            "model": "whisper-1",
                            "language": language
                        }
                    }
                }
                await forward_to_openai(ws, session_config)
                
                # DELAY: Wait for conversation to be created before sending response.create
                # This ensures conversation_id is ready before OpenAI starts listening for user messages
                if conversation_id:
                    response_create = {
                        "type": "response.create",
                        "response": {
                            "modalities": ["text", "audio"],
                            "output_audio_format": "pcm16",
                            "temperature": 0.8,
                            "max_output_tokens": 4096
                        }
                    }
                    await forward_to_openai(ws, response_create)
                    response_created = True
                    logging.info(f"[Handler {handler_id}] response.create sent AFTER conversation ready. Guard flag set to True.")
                else:
                    logging.error(f"[Handler {handler_id}] Cannot send response.create - conversation_id not ready")
            # Save assistant messages (final transcript) and update turn count
            elif event_type == 'response.audio_transcript.done' and conversation_id:
                logging.info(f"[Handler {handler_id}] Received response.audio_transcript.done event")
                transcript = data.get('transcript', '')
                logging.info(f"[Handler {handler_id}] Assistant transcript: '{transcript}' (length: {len(transcript)})")
                if transcript:
                    # Generate message ID upfront for consistency with user messages
                    message_id = str(uuid.uuid4())
                    
                    # Save assistant message with better error handling
                    async def save_assistant_message_background():
                        try:
                            logging.info(f"[Handler {handler_id}] About to save assistant message to DB: message_id={message_id}")
                            await save_message_with_id(conversation_id, 'assistant', transcript, message_id)
                            logging.info(f"[Handler {handler_id}] Successfully saved assistant message: {transcript[:50]}...")
                        except Exception as e:
                            logging.error(f"[Handler {handler_id}] Failed to save assistant message: {e}")
                    
                    asyncio.create_task(save_assistant_message_background())
                    
                    # Only increment turn count if there was a pending user message (complete exchange)
                    if pending_user_message:
                        current_turns += 1
                        asyncio.create_task(update_lesson_progress_turns(conversation_id, current_turns, client_ws))
                        pending_user_message = False  # Reset for next exchange
                        logging.info(f"[Handler {handler_id}] Complete turn exchange: user → AI. Turn count: {current_turns}")
                        
                        # Knowledge updates moved to post-conversation for better performance
                        # Real-time updates removed to keep conversation fluent
                    else:
                        logging.info(f"[Handler {handler_id}] AI response without pending user message - no turn increment")
                else:
                    logging.warning(f"[Handler {handler_id}] Empty transcript in response.audio_transcript.done event")
            # Save user messages (transcription) and generate feedback
            elif event_type == 'conversation.item.input_audio_transcription.completed' and conversation_id:
                transcript = data.get('transcript', '')
                if transcript:
                    # Generate message ID upfront for immediate display
                    message_id = str(uuid.uuid4())
                    
                    # IMMEDIATELY send to frontend for instant display (non-blocking)
                    logging.info(f"[WebSocket] Immediately emitting user message for instant display: message_id={message_id}, transcript={transcript}")
                    await client_ws.send_json({
                        "type": "conversation.item.input_audio_transcription.completed",
                        "message_id": message_id,
                        "transcript": transcript
                    })
                    
                    # Save to DB and generate feedback in background (non-blocking)
                    async def save_and_generate_feedback_background():
                        try:
                            # Save with pre-generated ID
                            await save_message_with_id(conversation_id, 'user', transcript, message_id)
                            logging.info(f"[Background] Saved user message to DB: message_id={message_id}")
                            
                            # Generate feedback in background
                            asyncio.create_task(process_feedback_background(message_id, language, level, client_ws, INTERACTION_MODE))
                            logging.info(f"[Background] Started feedback generation for message_id={message_id}")
                        except Exception as e:
                            logging.error(f"[Background] Error in save_and_generate_feedback: {e}")
                    
                    asyncio.create_task(save_and_generate_feedback_background())
                    pending_user_message = True
                    logging.info(f"[Handler {handler_id}] User message received - pending AI response for turn completion")
    except Exception as e:
        logging.error(f"[Handler {handler_id}] Error handling OpenAI response: {e}")
    finally:
        # Post-conversation processing when conversation ends
        if user_id and conversation_id and current_turns > 0:
            logging.info(f"[Handler {handler_id}] Scheduling post-conversation analysis for {conversation_id}")
            asyncio.create_task(process_conversation_completion(user_id, conversation_id, language, current_turns))
        await ws.close()

async def create_conversation(user_id: str, context: str, language: str, level: str, curriculum_id: str) -> str:
    """Create a new conversation and return its ID"""
    try:
        if not curriculum_id:
            raise ValueError("curriculum_id is required to create a conversation")
        logging.debug(f"[create_conversation] user_id={user_id}, context={context}, language={language}, level={level}, curriculum_id={curriculum_id}")
        result = supabase.table('conversations').insert({
            'user_id': user_id,
            'context': context,
            'language': language,
            'level': level,
            'curriculum_id': curriculum_id
        }).execute()
        logging.debug(f"[create_conversation] Supabase insert result.data: {result.data}")
        return result.data[0]['id']
    except Exception as e:
        logging.error(f"Error creating conversation: {e}")
        raise

async def save_message(conversation_id: str, role: str, content: str):
    """Save a message to the database and return the result"""
    try:
        logging.info(f"[save_message] Attempting to save {role} message: conversation_id={conversation_id}, content_length={len(content)}")
        
        # Use database manager for async execution
        def insert_message():
            return supabase.table('messages').insert({
                'conversation_id': conversation_id,
                'role': role,
                'content': content
            }).execute()
        
        result = await db_manager.execute_query(insert_message)
        logging.info(f"[save_message] Successfully saved {role} message: {result.data[0]['id'] if result.data else 'no_id'}")
        return result
    except Exception as e:
        logging.error(f"Error saving {role} message for conversation {conversation_id}: {e}")
        raise

async def save_message_with_id(conversation_id: str, role: str, content: str, message_id: str):
    """Save a message to the database with a specific ID"""
    try:
        logging.info(f"[save_message_with_id] Attempting to save {role} message: id={message_id}, conversation_id={conversation_id}, content_length={len(content)}")
        
        # Use database manager for async execution
        def insert_message():
            return supabase.table('messages').insert({
                'id': message_id,
                'conversation_id': conversation_id,
                'role': role,
                'content': content
            }).execute()
        
        result = await db_manager.execute_query(insert_message)
        logging.info(f"[save_message_with_id] Successfully saved {role} message: {result.data[0]['id'] if result.data else 'no_id'}")
        return result
    except Exception as e:
        logging.error(f"Error saving {role} message with ID {message_id}: {e}")
        raise

def get_required_turns_for_difficulty(difficulty: str) -> int:
    """Get required turns based on lesson difficulty"""
    difficulty_map = {
        'easy': 7,
        'medium': 9,
        'challenging': 11
    }
    return difficulty_map.get(difficulty.lower(), 7)

async def get_or_create_lesson_progress(conversation_id: str, user_id: str) -> dict:
    """Get or create lesson progress record for a conversation"""
    try:
        # Get conversation details
        conversation = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
        if not conversation.data:
            return None
        
        conv_data = conversation.data[0]
        lesson_id = conv_data.get('lesson_id')
        custom_lesson_id = conv_data.get('custom_lesson_id')
        curriculum_id = conv_data.get('curriculum_id')
        
        if not curriculum_id or (not lesson_id and not custom_lesson_id):
            # Not a lesson conversation
            return None
        
        # Check if progress record exists
        progress_query = supabase.table('lesson_progress').select('*').eq('user_id', user_id).eq('curriculum_id', curriculum_id)
        
        if lesson_id:
            progress_query = progress_query.eq('lesson_id', lesson_id)
        elif custom_lesson_id:
            progress_query = progress_query.eq('custom_lesson_id', custom_lesson_id)
        
        progress_result = progress_query.execute()
        
        if progress_result.data:
            return progress_result.data[0]
        
        # Create new progress record
        difficulty = 'easy'  # Default
        required_turns = 7
        
        if lesson_id:
            # Get difficulty from lesson template
            lesson_template = supabase.table('lesson_templates').select('difficulty').eq('id', lesson_id).execute()
            if lesson_template.data:
                difficulty = lesson_template.data[0].get('difficulty', 'easy')
        elif custom_lesson_id:
            # Get difficulty from custom lesson
            custom_lesson = supabase.table('custom_lesson_templates').select('difficulty').eq('id', custom_lesson_id).execute()
            if custom_lesson.data:
                difficulty = custom_lesson.data[0].get('difficulty', 'easy')
        
        required_turns = get_required_turns_for_difficulty(difficulty)
        
        # Create progress record
        progress_data = {
            'user_id': user_id,
            'curriculum_id': curriculum_id,
            'conversation_id': conversation_id,  # Add the conversation_id
            'status': 'in_progress',
            'required_turns': required_turns,
            'started_at': datetime.now().isoformat()
        }
        
        if lesson_id:
            progress_data['lesson_id'] = lesson_id
        elif custom_lesson_id:
            progress_data['custom_lesson_id'] = custom_lesson_id
        
        new_progress = supabase.table('lesson_progress').insert(progress_data).execute()
        return new_progress.data[0] if new_progress.data else None
        
    except Exception as e:
        logging.error(f"Error getting/creating lesson progress: {e}")
        return None

async def update_lesson_progress_turns(conversation_id: str, turns: int, client_ws):
    """Update lesson progress with current turn count"""
    try:
        # Use database manager for async execution
        def get_conversation():
            return supabase.table('conversations').select('*').eq('id', conversation_id).execute()
        
        conversation = await db_manager.execute_query(get_conversation)
        if not conversation.data:
            return
        
        conv_data = conversation.data[0]
        user_id = conv_data['user_id']
        
        # Get or create progress record
        progress = await get_or_create_lesson_progress(conversation_id, user_id)
        if not progress:
            return
        
        # Update turn count
        def update_progress():
            return supabase.table('lesson_progress').update({
                'turns_completed': turns,
                'updated_at': datetime.now().isoformat()
            }).eq('id', progress['id']).execute()
        
        await db_manager.execute_query(update_progress)
        
        # Send progress update to client (only every 3 turns to reduce message frequency)
        can_complete = turns >= progress['required_turns']
        if turns % 3 == 0 or can_complete:
            await client_ws.send_json({
                "type": "lesson.progress",
                "turns": turns,
                "required": progress['required_turns'],
                "can_complete": can_complete,
                "lesson_id": progress.get('lesson_id'),
                "custom_lesson_id": progress.get('custom_lesson_id'),
                "progress_id": progress['id']
            })
        
        logging.info(f"[Progress] Updated lesson progress: {turns}/{progress['required_turns']} turns, can_complete={can_complete}")
        
    except Exception as e:
        logging.error(f"Error updating lesson progress: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    connection_id = str(uuid.uuid4())[:8]
    connection_established = False
    conversation_id = None
    user_id = None
    
    # Start Sentry transaction for WebSocket connection
    transaction = None
    if sentry_dsn:
        transaction = sentry_sdk.start_transaction(op="websocket", name="websocket_connection")
        sentry_sdk.set_tag("connection_id", connection_id)
    
    try:
        # Verify token before accepting the connection
        try:
            user_payload = verify_jwt(token)
            user_id = user_payload["sub"]
            
            # Add more context to Sentry
            if sentry_dsn:
                sentry_sdk.set_tag("user_id", user_id)
                sentry_sdk.set_context("websocket", {
                    "connection_id": connection_id,
                    "user_id": user_id
                })
            
            logging.info(f"[WebSocket] Connection open: connection_id={connection_id}, user_id={user_id}")
        except Exception as e:
            logging.debug(f"[Connection {connection_id}] Authentication failed: {str(e)}")
            await websocket.close(code=4001, reason="Invalid authentication token")
            return
        # Accept the connection
        await websocket.accept()
        connection_established = True
        # Get the initial message
        try:
            initial_data = await websocket.receive_json()
            conversation_id = initial_data.get('conversation_id') or initial_data.get('conversation')
            custom_instructions = initial_data.get('custom_instructions')
            vad_settings = initial_data.get('vad_settings')
            # If conversation_id is provided, fetch conversation and lesson info
            if conversation_id:
                convo_result = supabase.table('conversations').select('*').eq('id', conversation_id).eq('user_id', user_id).execute()
                if not convo_result.data:
                    raise ValueError("Conversation not found or not owned by user")
                conversation = convo_result.data[0]
                language = conversation.get('language', 'en')
                level = conversation.get('level', 'A1')
                context = conversation.get('context', 'restaurant')
                curriculum_id = conversation.get('curriculum_id')
                lesson_id = conversation.get('lesson_id')
                custom_lesson_id = conversation.get('custom_lesson_id')
                
                # If custom_lesson_id is present, fetch custom lesson and build instructions
                if custom_lesson_id:
                    custom_lesson_result = supabase.table('custom_lesson_templates').select('*').eq('id', custom_lesson_id).execute()
                    if not custom_lesson_result.data:
                        raise ValueError("Custom lesson template not found for conversation")
                    custom_lesson = custom_lesson_result.data[0]
                    level = custom_lesson.get('difficulty', level)
                    context = f"Custom Lesson: {custom_lesson.get('title', '')}"
                    
                    # Build custom instructions for custom lesson
                    base_instructions = f"""
You are a {language} teacher conducting a custom lesson designed to address the student's specific weaknesses.

LESSON DETAILS:
Title: {custom_lesson.get('title', '')}
Difficulty: {custom_lesson.get('difficulty', '')}
Targeted Weaknesses: {', '.join(custom_lesson.get('targeted_weaknesses', []))}

LESSON OBJECTIVES:
{custom_lesson.get('objectives', '')}

LESSON CONTENT:
{custom_lesson.get('content', '')}

CULTURAL ELEMENT:
{custom_lesson.get('cultural_element', '')}

PRACTICE ACTIVITY:
{custom_lesson.get('practice_activity', '')}

IMPORTANT INSTRUCTIONS:
- Focus specifically on the targeted weakness areas mentioned above
- Provide immediate corrections when students make the types of mistakes this lesson addresses
- Be patient and encouraging, as these are areas the student struggles with
- Use examples and exercises that directly relate to their common mistakes
- Speak at the {level} CEFR level with appropriate complexity
- Provide English explanations when needed to clarify difficult concepts
"""
                    custom_instructions = base_instructions
                
                # If lesson_id is present, fetch lesson template and build custom instructions
                elif lesson_id:
                    lesson_result = supabase.table('lesson_templates').select('*').eq('id', lesson_id).execute()
                    if not lesson_result.data:
                        raise ValueError("Lesson template not found for conversation")
                    lesson = lesson_result.data[0]
                    level = lesson.get('difficulty', level)
                    context = f"Lesson: {lesson.get('title', '')}"
                    order_num = lesson.get('order_num', 0)
                    # Compose custom instructions
                    base_instructions = f"""
You are a {language} teacher. 
The lesson briefing is defined below. 
Speak in the language CEFR level defined by \"difficulty\". Your sentence length should also be suggested by the CEFR level in \"difficulty\". For example, A1 should be short, succinct messages. If needed, you can speak English to help the student. Try to keep the conversation flowing. If you cannot, you can always suggest practicing the same thing over and over again.
"""
                    if order_num <= 10:
                        base_instructions += " You should ALWAYS provide an English translation after each sentence to help the user."
                    base_instructions += "\n\nThe conversation body is determined by \"Objectives\" below. You can take inspiration from Content, cultural element, and practice activity. Do not stray from this brief. Speak ONLY in present tense, even if the user asks about the past or future.\n\n"
                    base_instructions += f"### Lesson: {lesson.get('title', '')}\n**Difficulty**: {lesson.get('difficulty', '')}  \n**Objectives**: {lesson.get('objectives', '')}  \n**Content**: {lesson.get('content', '')}  \n**Cultural Element**: {lesson.get('cultural_element', '')}  \n**Practice Activity**: {lesson.get('practice_activity', '')}\n"
                    custom_instructions = base_instructions
                    
                logging.info(f"[Connection {connection_id}] Loaded conversation_id={conversation_id}, context={context}, curriculum_id={curriculum_id}, level={level}, language={language}, lesson_id={lesson_id}, custom_lesson_id={custom_lesson_id}, custom_instructions={'yes' if custom_instructions else 'no'}")
                if not curriculum_id:
                    raise ValueError("curriculum_id is required for conversation")
            else:
                # Fallback: use provided fields (for generic conversations)
                level = initial_data.get('level', 'A1')
                context = initial_data.get('context', 'restaurant')
                language = initial_data.get('language', 'en')
                curriculum_id = initial_data.get('curriculum_id')
                logging.info(f"[Connection {connection_id}] Received initial data: context={context}, curriculum_id={curriculum_id}, level={level}, language={language}, custom_instructions={'yes' if custom_instructions else 'no'}")
                if not curriculum_id:
                    raise ValueError("curriculum_id is required to start a conversation")
        except Exception as e:
            logging.error(f"[Connection {connection_id}] Error receiving initial data: {e}")
            await websocket.close(code=4002, reason="Missing or invalid initial data (curriculum_id required)")
            return
        # Connect to OpenAI
        openai_ws = await connect_to_openai()
        if not openai_ws:
            if connection_established:
                logging.error(f"[Connection {connection_id}] Failed to connect to OpenAI service")
                await websocket.send_json({"error": "Failed to connect to OpenAI service"})
                await websocket.close(code=1011, reason="Failed to connect to OpenAI service")
            return
        
        # Get initial turn count for existing lesson conversations
        initial_turns = 0
        if conversation_id and (lesson_id or custom_lesson_id):
            try:
                # Get existing lesson progress to continue from current turn count
                progress = await get_or_create_lesson_progress(conversation_id, user_id)
                if progress:
                    initial_turns = progress.get('turns_completed', 0)
                    logging.info(f"[Connection {connection_id}] Found existing lesson progress: {initial_turns} turns completed")
            except Exception as e:
                logging.warning(f"[Connection {connection_id}] Could not load lesson progress: {e}")
        
        # Create callback for when OpenAI session is created
        async def on_openai_session_created():
            nonlocal conversation_id
            if conversation_id:
                # Already created, just return
                return conversation_id
            conversation_id_new = await create_conversation(user_id, context, language, level, curriculum_id)
            logging.info(f"[Connection {connection_id}] Created new conversation: {conversation_id_new}")
            await websocket.send_json({
                "type": "conversation.created",
                "conversation": {
                    "conversation_id": conversation_id_new,
                    "level": level,
                    "context": context,
                    "language": language,
                    "curriculum_id": curriculum_id
                }
            })
            return conversation_id_new
        # Start handling OpenAI responses
        openai_handler = asyncio.create_task(
            handle_openai_response_with_callback(
                openai_ws, websocket, level, context, language, on_openai_session_created, custom_instructions, initial_turns, vad_settings
            )
        )
        # Main client message loop - only handle client->OpenAI messages
        try:
            while True:
                data = await websocket.receive_json()
                data_type = data.get('type')
                # Only forward audio input to OpenAI, everything else is handled by the response handler
                if data_type == 'input_audio_buffer.append':
                    await forward_to_openai(openai_ws, data)
        except Exception as e:
            logging.error(f"[Connection {connection_id}] Error in websocket connection: {e}")
        finally:
            openai_handler.cancel()
            await openai_ws.close()
    except Exception as e:
        logging.error(f"[Connection {connection_id}] Unexpected error: {e}")
    finally:
        # Finish Sentry transaction
        if transaction:
            transaction.finish()
            
        if connection_established:
            try:
                logging.info(f"[WebSocket] Connection closed: connection_id={connection_id}")
                await websocket.close()
            except RuntimeError:
                pass

# Add new endpoint to get conversation history
@app.get("/api/conversations")
async def get_conversations(token: str = Query(...)):
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Get conversations with their latest message
        result = supabase.table('conversations').select(
            'id, context, language, level, created_at, updated_at, messages!inner(content, role, created_at)'
        ).eq('user_id', user_id).order('created_at', desc=True).execute()
        
        return result.data
    except Exception as e:
        logging.error(f"Error getting conversations: {e}")
        raise

@app.get("/api/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str, token: str = Query(...)):
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify the conversation belongs to the user
        conversation = supabase.table('conversations').select('id').eq('id', conversation_id).eq('user_id', user_id).execute()
        if not conversation.data:
            raise Exception("Conversation not found or access denied")
        
        # Get all messages for the conversation
        result = supabase.table('messages').select('*').eq('conversation_id', conversation_id).order('created_at', desc=False).execute()
        
        return result.data
    except Exception as e:
        logging.error(f"Error getting conversation messages: {e}")
        raise

@app.get("/api/conversations/{conversation_id}/review")
async def get_conversation_review(conversation_id: str, token: str = Query(...)):
    """Get conversation messages with their feedback for review purposes - optimized single query approach"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify the conversation belongs to the user
        conversation = supabase.table('conversations').select('id').eq('id', conversation_id).eq('user_id', user_id).execute()
        if not conversation.data:
            raise Exception("Conversation not found or access denied")
        
        # Get all messages for the conversation
        messages_result = supabase.table('messages').select('*').eq('conversation_id', conversation_id).order('created_at', desc=False).execute()
        messages = messages_result.data
        
        if not messages:
            return {"messages": [], "feedback": {}}
        
        # Get all message IDs for feedback lookup
        message_ids = [msg['id'] for msg in messages]
        
        # Get all feedback for these messages in a single query
        feedback_result = supabase.table('message_feedback').select('*').in_('message_id', message_ids).execute()
        
        # Create feedback lookup map
        feedback_map = {}
        for feedback in feedback_result.data:
            feedback_map[feedback['message_id']] = feedback
        
        return {
            "messages": messages,
            "feedback": feedback_map
        }
        
    except Exception as e:
        logging.error(f"Error getting conversation review: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_hint(level: str, context: str, language: str, conversation_history: list, user_id: str = None) -> str:
    """Generate a conversation hint using OpenAI's chat completions API"""
    try:
        # Get the conversation context and instructions
        instructions = get_level_specific_instructions(level, context, language, user_id)
        
        # Format conversation history, handling empty or short conversations
        if not conversation_history:
            history_text = "This is the start of the conversation."
        else:
            # Take up to 5 most recent messages, or all if less than 5
            recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
        
        # Create the prompt for hint generation
        prompt = f"""Based on the following conversation context and instructions, suggest a natural next response for the user.
        The response should be appropriate for their language level ({level}) and the current context ({context}).

        Instructions:
        {instructions}

        Recent conversation:
        {history_text}

        Provide a single, natural response suggestion that the user could say next. Keep it simple and appropriate for their level.
        If this is the start of the conversation, suggest an appropriate opening line."""

        # Call OpenAI's chat completions API using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 150
                }
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logging.error(f"Error generating hint: {response_text}")
                    return "Sorry, I couldn't generate a hint at this time."
                
                response_data = await response.json()
                hint = response_data["choices"][0]["message"]["content"].strip()
                logging.debug(f"[generate_hint] Generated hint for {len(conversation_history)} messages: {hint}")
                return hint
            
    except Exception as e:
        logging.error(f"Error in generate_hint: {e}")
        return "Sorry, I couldn't generate a hint at this time."

async def generate_custom_hint(level: str, context: str, language: str, custom_request: str, conversation_history: list, user_id: str = None) -> str:
    """Generate a custom hint based on user's specific request"""
    try:
        # Get the conversation context and instructions
        instructions = get_level_specific_instructions(level, context, language, user_id)
        
        # Format conversation history for context
        if not conversation_history:
            history_text = "This is the start of the conversation."
        else:
            # Take up to 3 most recent messages for context
            recent_messages = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
        
        # Create the prompt for custom hint generation
        prompt = f"""The user is learning {language} at level {level} in the context of {context}. They want to translate: "{custom_request}"

        Learning context and instructions:
        {instructions}

        Recent conversation context:
        {history_text}

        Provide a direct, contextually accurate translation of their request into {language}.
        - Translate exactly what they asked for, nothing more, nothing less
        - Make it appropriate for their {level} level
        - Do not add conversational elements, questions, or extra phrases
        - Do not include explanations, commentary, or additional text
        - If the input doesn't make grammatical sense, make only the minimal necessary adjustments
        
        Respond with ONLY the {language} translation."""

        # Call OpenAI's chat completions API using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 200
                }
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logging.error(f"Error generating custom hint: {response_text}")
                    return "Sorry, I couldn't generate a hint at this time."
                
                response_data = await response.json()
                hint = response_data["choices"][0]["message"]["content"].strip()
                logging.debug(f"[generate_custom_hint] Generated custom hint for request: {custom_request}")
                return hint
            
    except Exception as e:
        logging.error(f"Error in generate_custom_hint: {e}")
        return "Sorry, I couldn't generate a hint at this time."

class HintRequest(BaseModel):
    conversation_id: str
    custom_request: Optional[str] = None  # Optional text input for custom hint requests

@app.post("/api/hint")
async def get_hint(
    request: HintRequest,
    token: str = Query(...)
):
    conversation_id = request.conversation_id
    custom_request = request.custom_request
    logging.debug(f"[get_hint] Incoming request: conversation_id={conversation_id}, custom_request={custom_request}, token={token}")
    try:
        # Verify token
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        logging.debug(f"[get_hint] Request received for conversation_id: {conversation_id}")
        
        # Verify the conversation belongs to the user
        conversation = supabase.table('conversations').select('id, level, context, language').eq('id', conversation_id).eq('user_id', user_id).execute()
        if not conversation.data:
            logging.error(f"[get_hint] Conversation not found or access denied for user {user_id}")
            raise Exception("Conversation not found or access denied")
            
        # Get conversation messages
        messages = supabase.table('messages').select('*').eq('conversation_id', conversation_id).order('created_at', desc=False).execute()
        
        logging.debug(f"[get_hint] Found {len(messages.data)} messages for conversation")
        
        # Generate hint based on whether it's a custom request or general hint
        if custom_request and custom_request.strip():
            hint = await generate_custom_hint(
                conversation.data[0]['level'],
                conversation.data[0]['context'],
                conversation.data[0]['language'],
                custom_request.strip(),
                messages.data,
                user_id
            )
        else:
            hint = await generate_hint(
                conversation.data[0]['level'],
                conversation.data[0]['context'],
                conversation.data[0]['language'],
                messages.data,
                user_id
            )
        
        logging.debug(f"[get_hint] Generated hint: {hint}")
        
        return {"hint": hint}
        
    except Exception as e:
        logging.error(f"[get_hint] Error getting hint: {e}")
        raise

# Feedback generation models
class Mistake(BaseModel):
    category: str
    type: str
    error: str
    correction: str
    explanation: str
    severity: str
    languageFeatureTags: Optional[List[str]] = None

class FeedbackResponse(BaseModel):
    messageId: str
    originalMessage: str
    mistakes: List[Mistake]

def format_conversation_context(messages: List[dict]) -> str:
    """Format conversation messages for context."""
    formatted = []
    for msg in reversed(messages):  # Reverse to get chronological order
        role = "Student" if msg['role'] == 'user' else "Teacher"
        formatted.append(f"{role}: {msg['content']}")
    return "\n".join(formatted)

class FeedbackRequest(BaseModel):
    message_id: str

@app.post("/api/feedback")
async def get_feedback(
    request: FeedbackRequest,
    token: str = Query(...)
):
    """Get language learning feedback for a message."""
    try:
        # Verify token
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Get the message to verify ownership
        message = supabase.table('messages').select('conversation_id, content').eq('id', request.message_id).execute()
        if not message.data:
            raise Exception("Message not found")
            
        # Verify the conversation belongs to the user
        conversation = supabase.table('conversations').select('language, level').eq('id', message.data[0]['conversation_id']).eq('user_id', user_id).execute()
        if not conversation.data:
            raise Exception("Conversation not found or access denied")
            
        # Create a dummy WebSocket for the feedback response
        class DummyWebSocket:
            async def send_json(self, data):
                self.last_response = data
                
        dummy_ws = DummyWebSocket()
        
        # Generate feedback using configured interaction mode
        await process_feedback_background(
            request.message_id,
            conversation.data[0]['language'],
            conversation.data[0]['level'],
            dummy_ws,
            INTERACTION_MODE
        )
        
        if hasattr(dummy_ws, 'last_response'):
            return dummy_ws.last_response
        else:
            raise Exception("Failed to generate feedback")
        
    except Exception as e:
        logging.error(f"Error getting feedback: {e}")
        raise

class CurriculumCreateRequest(BaseModel):
    language: str
    start_level: str

class CurriculumUpdateRequest(BaseModel):
    language: Optional[str] = None
    start_level: Optional[str] = None
    current_lesson: Optional[int] = None

class LessonCreateRequest(BaseModel):
    order: int
    brief: str

class LessonUpdateRequest(BaseModel):
    order: Optional[int] = None
    brief: Optional[str] = None
    status: Optional[str] = None
    score: Optional[float] = None

@app.get("/api/curriculums")
async def list_curriculums(token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    result = supabase.table('curriculums').select('*').eq('user_id', user_id).execute()
    return result.data

@app.post("/api/curriculums")
async def create_curriculum(request: CurriculumCreateRequest, token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    data = {
        'user_id': user_id,
        'language': request.language,
        'start_level': request.start_level
    }
    result = supabase.table('curriculums').insert(data).execute()
    return result.data

@app.get("/api/curriculums/{curriculum_id}")
async def get_curriculum(curriculum_id: str, token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    result = supabase.table('curriculums').select('*').eq('id', curriculum_id).eq('user_id', user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return result.data[0]

@app.put("/api/curriculums/{curriculum_id}")
async def update_curriculum(curriculum_id: str, request: CurriculumUpdateRequest, token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    update_data = {k: v for k, v in request.dict().items() if v is not None}
    result = supabase.table('curriculums').update(update_data).eq('id', curriculum_id).eq('user_id', user_id).execute()
    return result.data

@app.delete("/api/curriculums/{curriculum_id}")
async def delete_curriculum(curriculum_id: str, token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    result = supabase.table('curriculums').delete().eq('id', curriculum_id).eq('user_id', user_id).execute()
    return {"deleted": True}

@app.get("/api/curriculums/{curriculum_id}/lessons")
async def list_lessons(curriculum_id: str, token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    # Verify curriculum ownership
    curriculum = supabase.table('curriculums').select('id').eq('id', curriculum_id).eq('user_id', user_id).execute()
    if not curriculum.data:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    result = supabase.table('lessons').select('*').eq('curriculum_id', curriculum_id).order('order', desc=False).execute()
    return result.data

@app.post("/api/curriculums/{curriculum_id}/lessons")
async def create_lesson(curriculum_id: str, request: LessonCreateRequest, token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    # Verify curriculum ownership
    curriculum = supabase.table('curriculums').select('id').eq('id', curriculum_id).eq('user_id', user_id).execute()
    if not curriculum.data:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    data = {
        'curriculum_id': curriculum_id,
        'order': request.order,
        'brief': request.brief
    }
    result = supabase.table('lessons').insert(data).execute()
    return result.data

@app.get("/api/lessons/{lesson_id}")
async def get_lesson(lesson_id: str, token: str = Query(...)):
    # Get lesson and verify curriculum ownership
    lesson = supabase.table('lessons').select('*').eq('id', lesson_id).execute()
    if not lesson.data:
        raise HTTPException(status_code=404, detail="Lesson not found")
    curriculum_id = lesson.data[0]['curriculum_id']
    curriculum = supabase.table('curriculums').select('id', 'user_id').eq('id', curriculum_id).execute()
    if not curriculum.data:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    if curriculum.data[0]['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return lesson.data[0]

@app.put("/api/lessons/{lesson_id}")
async def update_lesson(lesson_id: str, request: LessonUpdateRequest, token: str = Query(...)):
    lesson = supabase.table('lessons').select('*').eq('id', lesson_id).execute()
    if not lesson.data:
        raise HTTPException(status_code=404, detail="Lesson not found")
    curriculum_id = lesson.data[0]['curriculum_id']
    curriculum = supabase.table('curriculums').select('id', 'user_id').eq('id', curriculum_id).execute()
    if not curriculum.data:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    if curriculum.data[0]['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    update_data = {k: v for k, v in request.dict().items() if v is not None}
    result = supabase.table('lessons').update(update_data).eq('id', lesson_id).execute()
    return result.data

@app.delete("/api/lessons/{lesson_id}")
async def delete_lesson(lesson_id: str, token: str = Query(...)):
    lesson = supabase.table('lessons').select('*').eq('id', lesson_id).execute()
    if not lesson.data:
        raise HTTPException(status_code=404, detail="Lesson not found")
    curriculum_id = lesson.data[0]['curriculum_id']
    curriculum = supabase.table('curriculums').select('id', 'user_id').eq('id', curriculum_id).execute()
    if not curriculum.data:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    if curriculum.data[0]['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    supabase.table('lessons').delete().eq('id', lesson_id).execute()
    return {"deleted": True}

@app.get("/api/lesson_templates")
async def list_lesson_templates(language: str):
    result = supabase.table('lesson_templates').select('*').eq('language', language).order('order_num', desc=False).execute()
    return result.data

@app.get("/api/language_tags")
async def get_language_tags(language: str, limit: int = 50, token: str = Query(...)):
    """Get language feature tags for a specific language"""
    try:
        verify_jwt(token)  # Verify user is authenticated
        
        result = supabase.table('language_feature_tags') \
            .select('tag_name, usage_count, created_at, updated_at') \
            .eq('language', language) \
            .order('usage_count', desc=True) \
            .limit(limit) \
            .execute()
        
        return {
            "language": language,
            "tags": result.data,
            "total_count": len(result.data)
        }
    except Exception as e:
        logging.error(f"Error fetching language tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user_knowledge")
async def get_user_knowledge(language: str, token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    result = supabase.table('user_knowledge').select('knowledge_json').eq('user_id', user_id).eq('language', language).execute()
    if not result.data:
        return {"knowledge": None}
    return {"knowledge": result.data[0]['knowledge_json']}

@app.post("/api/user_knowledge")
async def generate_user_knowledge(request: Request, language: str = Query(...), token: str = Query(...)):
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    
    try:
        # Use the new incremental update system
        success = await update_user_knowledge_incrementally(user_id, language)
        
        if success:
            # Return the updated knowledge
            result = supabase.table('user_knowledge').select('knowledge_json').eq('user_id', user_id).eq('language', language).execute()
            if result.data:
                return {"knowledge": result.data[0]['knowledge_json']}
            else:
                return {"error": "No conversations found to analyze for this language."}
        else:
            return {"error": "Failed to generate knowledge report."}
            
    except Exception as e:
        logging.error(f"Error generating user knowledge: {e}")
        return {"error": f"Failed to generate knowledge report: {str(e)}"}

@app.post("/api/user_knowledge/update")
async def update_user_knowledge(language: str = Query(...), token: str = Query(...)):
    """Manually trigger an incremental knowledge update"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Get unanalyzed conversations count before update
        unanalyzed = await get_unanalyzed_conversations(user_id, language)
        
        if not unanalyzed:
            # Still fetch and return current knowledge even if no update needed
            result = supabase.table('user_knowledge').select('knowledge_json').eq('user_id', user_id).eq('language', language).execute()
            current_knowledge = result.data[0]['knowledge_json'] if result.data else None
            
            return {
                "updated": True,
                "message": "Knowledge is already up to date",
                "conversations_analyzed": 0,
                "knowledge": current_knowledge
            }
        
        logging.info(f"[Knowledge Update] Updating knowledge for user {user_id}, found {len(unanalyzed)} unanalyzed conversations")
        
        # Perform incremental update
        success = await update_user_knowledge_incrementally(user_id, language)
        
        if success:
            # Return updated knowledge
            result = supabase.table('user_knowledge').select('knowledge_json').eq('user_id', user_id).eq('language', language).execute()
            updated_knowledge = result.data[0]['knowledge_json'] if result.data else None
            
            return {
                "updated": True,
                "conversations_analyzed": len(unanalyzed),
                "knowledge": updated_knowledge,
                "message": f"Successfully analyzed {len(unanalyzed)} new conversations"
            }
        else:
            return {
                "updated": False,
                "error": "Failed to update knowledge",
                "conversations_analyzed": 0
            }
            
    except Exception as e:
        logging.error(f"Error updating user knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/user_knowledge")
async def delete_user_knowledge(language: str = Query(...), token: str = Query(...)):
    """Delete user knowledge data to allow regeneration"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Delete existing knowledge record
        supabase.table('user_knowledge').delete().eq('user_id', user_id).eq('language', language).execute()
        
        return {"deleted": True, "message": "Knowledge data deleted. You can now regenerate it."}
        
    except Exception as e:
        logging.error(f"Error deleting user knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class StartLessonConversationRequest(BaseModel):
    lesson_template_id: str
    curriculum_id: str

class StartLessonConversationResponse(BaseModel):
    conversation_id: str
    level: str
    language: str
    custom_instructions: str
    lesson_order: int

@app.post("/api/start_lesson_conversation", response_model=StartLessonConversationResponse)
async def start_lesson_conversation(
    request: StartLessonConversationRequest,
    token: str = Query(...)
):
    """Start a conversation for a lesson with custom instructions."""
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    # Fetch lesson template
    lesson_result = supabase.table('lesson_templates').select('*').eq('id', request.lesson_template_id).execute()
    if not lesson_result.data:
        raise HTTPException(status_code=404, detail="Lesson template not found")
    lesson = lesson_result.data[0]
    # Fetch curriculum to verify ownership and get language/level
    curriculum_result = supabase.table('curriculums').select('*').eq('id', request.curriculum_id).eq('user_id', user_id).execute()
    if not curriculum_result.data:
        raise HTTPException(status_code=404, detail="Curriculum not found or not owned by user")
    curriculum = curriculum_result.data[0]
    language = curriculum['language']
    level = lesson.get('difficulty', curriculum.get('start_level', 'A1'))
    order_num = lesson.get('order_num', 0)
    # Compose custom instructions
    base_instructions = f"""
You are a {language} teacher. 
The lesson briefing is defined below. 
Speak in the language CEFR level defined by \"difficulty\". Your sentence length should also be suggested by the CEFR level in \"difficulty\". For example, A1 should be short, succinct messages. If needed, you can speak English to help the student. Try to keep the conversation flowing. If you cannot, you can always suggest practicing the same thing over and over again.
"""
    # Only provide English translation for first 10 lessons
    if order_num <= 10:
        base_instructions += " You should ALWAYS provide an English translation after each sentence to help the user."
    base_instructions += "\n\nThe conversation body is determined by \"Objectives\" below. You can take inspiration from Content, cultural element, and practice activity. Do not stray from this brief. Speak ONLY in present tense, even if the user asks about the past or future.\n\n"
    base_instructions += f"### Lesson: {lesson.get('title', '')}\n**Difficulty**: {lesson.get('difficulty', '')}  \n**Objectives**: {lesson.get('objectives', '')}  \n**Content**: {lesson.get('content', '')}  \n**Cultural Element**: {lesson.get('cultural_element', '')}  \n**Practice Activity**: {lesson.get('practice_activity', '')}\n"
    # Create conversation with lesson_id and context as 'Lesson: <Title>'
    conversation_result = supabase.table('conversations').insert({
        'user_id': user_id,
        'context': f"Lesson: {lesson.get('title', '')}",
        'language': language,
        'level': level,
        'curriculum_id': request.curriculum_id,
        'lesson_id': lesson['id']
    }).execute()
    conversation_id = conversation_result.data[0]['id']
    return StartLessonConversationResponse(
        conversation_id=conversation_id,
        level=level,
        language=language,
        custom_instructions=base_instructions,
        lesson_order=order_num
    )

@app.get("/api/conversation_instructions")
async def get_conversation_instructions(conversation_id: str, token: str = Query(...)):
    """Return the custom instructions for a conversation, if any."""
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    # Fetch conversation and verify ownership
    convo = supabase.table('conversations').select('*').eq('id', conversation_id).eq('user_id', user_id).execute()
    if not convo.data:
        raise HTTPException(status_code=404, detail="Conversation not found or not owned by user")
    conversation = convo.data[0]
    # If context is lesson:<lesson_id>, fetch lesson template and generate instructions
    context = conversation.get('context', '')
    if context.startswith('lesson:'):
        lesson_id = context.split(':', 1)[1]
        lesson_result = supabase.table('lesson_templates').select('*').eq('id', lesson_id).execute()
        if not lesson_result.data:
            raise HTTPException(status_code=404, detail="Lesson template not found")
        lesson = lesson_result.data[0]
        language = conversation['language']
        level = lesson.get('difficulty', conversation.get('level', 'A1'))
        order_num = lesson.get('order_num', 0)
        base_instructions = f"""
You are a {language} teacher. 
The lesson briefing is defined below. 
Speak in the language CEFR level defined by \"difficulty\". Your sentence length should also be suggested by the CEFR level in \"difficulty\". For example, A1 should be short, succinct messages. If needed, you can speak English to help the student. Try to keep the conversation flowing. If you cannot, you can always suggest practicing the same thing over and over again.
"""
        if order_num <= 10:
            base_instructions += " You should ALWAYS provide an English translation after each sentence to help the user."
        base_instructions += "\n\nThe conversation body is determined by \"Objectives\" below. You can take inspiration from Content, cultural element, and practice activity. Do not stray from this brief. Speak ONLY in present tense, even if the user asks about the past or future.\n\n"
        base_instructions += f"### Lesson: {lesson.get('title', '')}\n**Difficulty**: {lesson.get('difficulty', '')}  \n**Objectives**: {lesson.get('objectives', '')}  \n**Content**: {lesson.get('content', '')}  \n**Cultural Element**: {lesson.get('cultural_element', '')}  \n**Practice Activity**: {lesson.get('practice_activity', '')}\n"
        return JSONResponse({"instructions": base_instructions})
    # Otherwise, return default instructions
    instructions = get_level_specific_instructions(conversation['level'], conversation['context'], conversation['language'], user_id)
    return JSONResponse({"instructions": instructions})

# Add new models for custom lesson generation
class WeaknessPattern(BaseModel):
    category: str
    type: str
    frequency: int
    severity_distribution: dict
    examples: List[dict]
    language_feature_tags: List[str]

class CustomLessonRequest(BaseModel):
    curriculum_id: str
    weakness_patterns: List[str]  # Specific areas to target

class GeneratedLesson(BaseModel):
    title: str
    difficulty: str
    objectives: str
    content: str
    cultural_element: str
    practice_activity: str
    targeted_weaknesses: List[str]

@app.get("/api/analyze_weaknesses")
async def analyze_user_weaknesses(curriculum_id: str, token: str = Query(...)):
    """Analyze user's mistake patterns to identify areas of weakness."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('*').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        language = curriculum.data[0]['language']
        
        # Get all conversations for this curriculum
        conversations = supabase.table('conversations').select('id').eq('user_id', user_id).eq('curriculum_id', curriculum_id).execute()
        conversation_ids = [c['id'] for c in conversations.data]
        
        if not conversation_ids:
            return {"weakness_patterns": [], "message": "No conversation data found"}
        
        # Get all feedback for these conversations
        all_mistakes = []
        for conv_id in conversation_ids:
            messages = supabase.table('messages').select('id').eq('conversation_id', conv_id).eq('role', 'user').execute()
            message_ids = [m['id'] for m in messages.data]
            
            for msg_id in message_ids:
                feedback = supabase.table('message_feedback').select('mistakes').eq('message_id', msg_id).execute()
                for fb in feedback.data:
                    all_mistakes.extend(fb['mistakes'])
        
        if not all_mistakes:
            return {"weakness_patterns": [], "message": "No mistakes found to analyze"}
        
        # Analyze patterns
        weakness_patterns = analyze_mistake_patterns(all_mistakes, language)
        
        return {"weakness_patterns": weakness_patterns}
        
    except Exception as e:
        logging.error(f"Error analyzing weaknesses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def analyze_mistake_patterns(mistakes: List[dict], language: str) -> List[dict]:
    """Analyze mistakes to identify patterns of weakness."""
    # Group mistakes by category and type
    pattern_analysis = {}
    
    for mistake in mistakes:
        category = mistake.get('category', 'other')
        mistake_type = mistake.get('type', 'other')
        severity = mistake.get('severity', 'minor')
        
        # Create a key for this pattern
        pattern_key = f"{category}:{mistake_type}"
        
        if pattern_key not in pattern_analysis:
            pattern_analysis[pattern_key] = {
                'category': category,
                'type': mistake_type,
                'frequency': 0,
                'severity_distribution': {'minor': 0, 'moderate': 0, 'critical': 0},
                'examples': [],
                'language_feature_tags': set()
            }
        
        pattern_analysis[pattern_key]['frequency'] += 1
        pattern_analysis[pattern_key]['severity_distribution'][severity] += 1
        
        # Add example (limit to 3 per pattern)
        if len(pattern_analysis[pattern_key]['examples']) < 3:
            pattern_analysis[pattern_key]['examples'].append({
                'error': mistake.get('error', ''),
                'correction': mistake.get('correction', ''),
                'explanation': mistake.get('explanation', '')
            })
        
        # Add language feature tags
        tags = mistake.get('languageFeatureTags', [])
        if tags:
            pattern_analysis[pattern_key]['language_feature_tags'].update(tags)
    
    # Convert to list and filter for significant patterns (frequency >= 2)
    significant_patterns = []
    for pattern in pattern_analysis.values():
        if pattern['frequency'] >= 2:  # Only patterns that occur multiple times
            pattern['language_feature_tags'] = list(pattern['language_feature_tags'])
            significant_patterns.append(pattern)
    
    # Sort by frequency and severity (critical/moderate mistakes get priority)
    def pattern_priority(pattern):
        critical_weight = pattern['severity_distribution']['critical'] * 3
        moderate_weight = pattern['severity_distribution']['moderate'] * 2
        minor_weight = pattern['severity_distribution']['minor'] * 1
        return critical_weight + moderate_weight + minor_weight
    
    significant_patterns.sort(key=pattern_priority, reverse=True)
    
    return significant_patterns[:10]  # Return top 10 patterns

@app.post("/api/generate_custom_lesson")
async def generate_custom_lesson(request: CustomLessonRequest, token: str = Query(...)):
    """Generate a custom lesson targeting specific weakness patterns."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('*').eq('id', request.curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        curriculum_data = curriculum.data[0]
        language = curriculum_data['language']
        level = curriculum_data['start_level']
        
        # Get weakness analysis directly (not through API call)
        # Get all conversations for this curriculum
        conversations = supabase.table('conversations').select('id').eq('user_id', user_id).eq('curriculum_id', request.curriculum_id).execute()
        conversation_ids = [c['id'] for c in conversations.data]
        
        if not conversation_ids:
            raise HTTPException(status_code=400, detail="No conversation data found")
        
        # Get all feedback for these conversations
        all_mistakes = []
        for conv_id in conversation_ids:
            messages = supabase.table('messages').select('id').eq('conversation_id', conv_id).eq('role', 'user').execute()
            message_ids = [m['id'] for m in messages.data]
            
            for msg_id in message_ids:
                feedback = supabase.table('message_feedback').select('mistakes').eq('message_id', msg_id).execute()
                for fb in feedback.data:
                    all_mistakes.extend(fb['mistakes'])
        
        if not all_mistakes:
            raise HTTPException(status_code=400, detail="No mistakes found to analyze")
        
        # Analyze patterns - focus on the most common mistake (top 1)
        patterns = analyze_mistake_patterns(all_mistakes, language)
        
        if not patterns:
            raise HTTPException(status_code=400, detail="No weakness patterns found")
        
        # Focus on just the most common pattern for simplicity
        top_pattern = patterns[0]
        
        # Generate custom lesson using OpenAI
        lesson = await generate_lesson_with_openai([top_pattern], language, level)
        
        # Return lesson data without saving - let frontend handle preview/save
        lesson_data = {
            'title': lesson['title'],
            'language': language,
            'difficulty': lesson['difficulty'],
            'objectives': lesson['objectives'],
            'content': lesson['content'],
            'cultural_element': lesson['cultural_element'],
            'practice_activity': lesson['practice_activity'],
            'targeted_weaknesses': lesson['targeted_weaknesses'],
            'curriculum_id': request.curriculum_id,
            'user_id': user_id,
        }
        
        return lesson_data
        
    except Exception as e:
        logging.error(f"Error generating custom lesson: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_lesson_with_openai(patterns: List[dict], language: str, level: str) -> dict:
    """Use OpenAI to generate a custom lesson targeting specific weaknesses."""
    
    # Check if we should use mock mode (when OpenAI quota is exceeded)
    MOCK_MODE = os.getenv("MOCK_LESSON_GENERATION", "false").lower() == "true"
    
    if MOCK_MODE:
        # Return a mock lesson for testing
        pattern = patterns[0] if patterns else {"category": "grammar", "type": "verb tense", "frequency": 3}
        return {
            "title": f"Mastering {pattern['category'].title()}: {pattern['type'].title()}",
            "difficulty": level,
            "objectives": f"Practice {pattern['type']} usage and improve accuracy in {language} conversations",
            "content": f"Learn the correct usage of {pattern['type']} in {language} with practical examples and exercises",
            "cultural_element": f"Understand how {pattern['type']} is used in everyday {language} conversations",
            "practice_activity": f"Complete exercises focusing on {pattern['type']} and practice in conversation",
            "targeted_weaknesses": [f"{pattern['category']}", f"{pattern['type']}"]
        }
    
    # Build context about the weaknesses
    weakness_context = []
    for pattern in patterns[:5]:  # Focus on top 5 patterns
        examples = "; ".join([f"'{ex['error']}' → '{ex['correction']}'" for ex in pattern['examples'][:2]])
        weakness_context.append(
            f"- {pattern['category']} ({pattern['type']}): {pattern['frequency']} occurrences. "
            f"Examples: {examples}"
        )
    
    weakness_summary = "\n".join(weakness_context)
    
    prompt = f"""Create a custom {language} lesson for a {level} level student targeting their specific weaknesses.

WEAKNESS PATTERNS TO ADDRESS:
{weakness_summary}

Generate a lesson that specifically targets these weakness areas. The lesson should:
1. Focus on the most frequent and severe mistake patterns
2. Be written primarily in ENGLISH for clear understanding
3. Include examples in {language} to demonstrate the concepts
4. Be concise and practical
5. Be appropriate for {level} level

Respond with a JSON object in this exact format:
{{
    "title": "Concise lesson title focusing on the main weakness (in English)",
    "difficulty": "{level}",
    "objectives": "2-3 clear, specific learning objectives in English (max 150 characters)",
    "content": "Concise explanation of the grammar/vocabulary concept in English with {language} examples (max 300 characters)",
    "cultural_element": "Brief cultural context relevant to the lesson (max 150 characters)",
    "practice_activity": "Specific, actionable exercise description in English (max 200 characters)",
    "targeted_weaknesses": ["list", "of", "specific", "weakness", "types", "addressed"]
}}

Keep all text concise and focused. Use {language} only for examples within the English explanations.
"""

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "system", "content": prompt}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                # Check if it's a quota error
                if "insufficient_quota" in error_text or "quota" in error_text.lower():
                    raise Exception(f"OpenAI API quota exceeded. Please add credits to your OpenAI account or set MOCK_LESSON_GENERATION=true for testing.")
                raise Exception(f"OpenAI API error: {error_text}")
            
            response_data = await response.json()
            lesson_data = json.loads(response_data["choices"][0]["message"]["content"])
            
            return lesson_data

@app.get("/api/custom_lessons")
async def list_custom_lessons(curriculum_id: str, token: str = Query(...)):
    """List custom lessons for a curriculum."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('id').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        result = supabase.table('custom_lesson_templates').select('*').eq('curriculum_id', curriculum_id).eq('user_id', user_id).order('created_at', desc=True).execute()
        return result.data
        
    except Exception as e:
        logging.error(f"Error listing custom lessons: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/custom_lessons/{lesson_id}")
async def delete_custom_lesson(lesson_id: str, token: str = Query(...)):
    """Delete a custom lesson."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify ownership
        lesson = supabase.table('custom_lesson_templates').select('*').eq('id', lesson_id).eq('user_id', user_id).execute()
        if not lesson.data:
            raise HTTPException(status_code=404, detail="Custom lesson not found")
        
        supabase.table('custom_lesson_templates').delete().eq('id', lesson_id).eq('user_id', user_id).execute()
        return {"deleted": True}
        
    except Exception as e:
        logging.error(f"Error deleting custom lesson: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/start_custom_lesson_conversation")
async def start_custom_lesson_conversation(
    request: dict = Body(...),
    token: str = Query(...)
):
    """Start a conversation for a custom lesson."""
    custom_lesson_id = request.get('custom_lesson_id')
    curriculum_id = request.get('curriculum_id')
    
    if not custom_lesson_id or not curriculum_id:
        raise HTTPException(status_code=400, detail="custom_lesson_id and curriculum_id are required")
    
    user_payload = verify_jwt(token)
    user_id = user_payload["sub"]
    
    # Fetch custom lesson
    lesson_result = supabase.table('custom_lesson_templates').select('*').eq('id', custom_lesson_id).eq('user_id', user_id).execute()
    if not lesson_result.data:
        raise HTTPException(status_code=404, detail="Custom lesson not found")
    
    lesson = lesson_result.data[0]
    
    # Verify curriculum ownership
    curriculum_result = supabase.table('curriculums').select('*').eq('id', curriculum_id).eq('user_id', user_id).execute()
    if not curriculum_result.data:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    
    curriculum = curriculum_result.data[0]
    language = curriculum['language']
    level = lesson.get('difficulty', curriculum.get('start_level', 'A1'))
    
    # Map language code to full language name
    language_names = {
        'en': 'English',
        'es': 'Spanish', 
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'kn': 'Kannada'
    }
    language_name = language_names.get(language, language)
    
    # Create custom instructions for this lesson
    base_instructions = f"""
You are a {language_name} teacher conducting a custom lesson designed to address the student's specific weaknesses.

CRITICAL LANGUAGE INSTRUCTION: 
- You MUST speak in {language_name} throughout this lesson
- Conduct the entire lesson in {language_name} 
- Speak at the {level} CEFR level with appropriate complexity
- Your sentence length should match the {level} CEFR level (A1 = short, simple sentences)
- Only provide English explanations when absolutely necessary to clarify difficult concepts

LESSON DETAILS:
Title: {lesson.get('title', '')}
Difficulty: {lesson.get('difficulty', '')}
Targeted Weaknesses: {', '.join(lesson.get('targeted_weaknesses', []))}

LESSON OBJECTIVES:
{lesson.get('objectives', '')}

LESSON CONTENT:
{lesson.get('content', '')}

CULTURAL ELEMENT:
{lesson.get('cultural_element', '')}

PRACTICE ACTIVITY:
{lesson.get('practice_activity', '')}

IMPORTANT TEACHING INSTRUCTIONS:
- Focus specifically on the targeted weakness areas mentioned above
- Provide immediate corrections when students make the types of mistakes this lesson addresses
- Be patient and encouraging, as these are areas the student struggles with
- Use examples and exercises that directly relate to their common mistakes
- Try to keep the conversation flowing naturally in {language_name}
- If the conversation stalls, suggest practicing the same concepts repeatedly
"""
    
    # Create conversation
    conversation_result = supabase.table('conversations').insert({
        'user_id': user_id,
        'context': f"Custom Lesson: {lesson.get('title', '')}",
        'language': language,
        'level': level,
        'curriculum_id': curriculum_id,
        'custom_lesson_id': custom_lesson_id
    }).execute()
    
    conversation_id = conversation_result.data[0]['id']
    
    return {
        "conversation_id": conversation_id,
        "level": level,
        "language": language,
        "custom_instructions": base_instructions,
        "lesson_title": lesson.get('title', ''),
        "targeted_weaknesses": lesson.get('targeted_weaknesses', [])
    }

@app.post("/api/save_custom_lesson")
async def save_custom_lesson(
    request: dict = Body(...),
    token: str = Query(...)
):
    """Save a custom lesson after user preview and confirmation."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum_id = request.get('curriculum_id')
        curriculum = supabase.table('curriculums').select('id').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        # Save as custom lesson template
        custom_lesson = supabase.table('custom_lesson_templates').insert({
            'user_id': user_id,
            'curriculum_id': curriculum_id,
            'title': request.get('title'),
            'language': request.get('language'),
            'difficulty': request.get('difficulty'),
            'objectives': request.get('objectives'),
            'content': request.get('content'),
            'cultural_element': request.get('cultural_element'),
            'practice_activity': request.get('practice_activity'),
            'targeted_weaknesses': request.get('targeted_weaknesses', []),
            'order_num': 999  # Custom lessons get high order numbers
        }).execute()
        
        return custom_lesson.data[0]
        
    except Exception as e:
        logging.error(f"Error saving custom lesson: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# New lesson suggestion system endpoints

async def auto_generate_daily_suggestions(user_id: str, curriculum_id: str, threshold_check: dict) -> dict:
    """Auto-generate daily suggestions without counting against daily limit."""
    try:
        # Get curriculum data
        curriculum = supabase.table('curriculums').select('*').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise Exception("Curriculum not found")
        
        curriculum_data = curriculum.data[0]
        language = curriculum_data['language']
        level = curriculum_data['start_level']
        
        patterns = threshold_check["patterns"]
        if not patterns:
            raise Exception("No weakness patterns found")
        
        # Generate up to 3 lessons (one for each top pattern)
        generated_lessons = []
        for i, pattern in enumerate(patterns[:3]):
            try:
                lesson = await generate_lesson_with_openai([pattern], language, level)
                lesson['pattern_focus'] = f"{pattern['category']} - {pattern['type']}"
                lesson['pattern_frequency'] = pattern['frequency']
                generated_lessons.append(lesson)
            except Exception as e:
                logging.error(f"Error generating auto lesson {i+1}: {e}")
                continue
        
        if not generated_lessons:
            raise Exception("Failed to generate any lessons")
        
        # Save suggestions to database (mark as auto-generated)
        suggestion_data = {
            'user_id': user_id,
            'curriculum_id': curriculum_id,
            'suggestion_data': threshold_check,
            'generated_lessons': generated_lessons,
            'status': 'pending',
            'suggestions_count': len(generated_lessons)
        }
        
        saved_suggestion = supabase.table('lesson_suggestions').insert(suggestion_data).execute()
        
        return {
            "suggestion_id": saved_suggestion.data[0]['id'],
            "lessons": generated_lessons,
            "patterns_analyzed": len(patterns)
        }
        
    except Exception as e:
        logging.error(f"Error in auto_generate_daily_suggestions: {e}")
        raise

async def check_lesson_suggestion_threshold(user_id: str, curriculum_id: str) -> dict:
    """Check if user meets threshold for lesson suggestions based on recent mistakes."""
    try:
        # Get last 10 conversations for this curriculum
        conversations = supabase.table('conversations').select('id').eq('user_id', user_id).eq('curriculum_id', curriculum_id).order('created_at', desc=True).limit(10).execute()
        conversation_ids = [c['id'] for c in conversations.data]
        
        if not conversation_ids:
            return {"needs_suggestion": False, "reason": "No conversations found"}
        
        # Get all user messages from these conversations
        all_mistakes = []
        for conv_id in conversation_ids:
            messages = supabase.table('messages').select('id').eq('conversation_id', conv_id).eq('role', 'user').execute()
            message_ids = [m['id'] for m in messages.data]
            
            for msg_id in message_ids:
                feedback = supabase.table('message_feedback').select('mistakes').eq('message_id', msg_id).execute()
                for fb in feedback.data:
                    all_mistakes.extend(fb['mistakes'])
        
        if not all_mistakes:
            # Check if we're in mock mode for testing
            MOCK_MODE = os.getenv("MOCK_LESSON_GENERATION", "false").lower() == "true"
            if MOCK_MODE:
                # Create fake patterns for testing
                fake_patterns = [{
                    'category': 'grammar',
                    'type': 'verb tense',
                    'frequency': 5,
                    'severity_distribution': {'minor': 2, 'moderate': 3, 'critical': 0},
                    'examples': [
                        {'error': 'I go yesterday', 'correction': 'I went yesterday', 'explanation': 'Past tense needed'}
                    ],
                    'language_feature_tags': ['past_tense']
                }]
                return {
                    "needs_suggestion": True,
                    "reason": "Mock mode: fake threshold met",
                    "patterns": fake_patterns,
                    "severity_counts": {"minor": 2, "moderate": 3, "critical": 0}
                }
            return {"needs_suggestion": False, "reason": "No mistakes found"}
        
        # Count mistakes by severity
        severity_counts = {"minor": 0, "moderate": 0, "critical": 0}
        for mistake in all_mistakes:
            severity = mistake.get('severity', 'minor')
            severity_counts[severity] += 1
        
        # Check thresholds: 3+ moderate OR 2+ critical OR 5+ minor
        needs_suggestion = (
            severity_counts["moderate"] >= 3 or
            severity_counts["critical"] >= 2 or
            severity_counts["minor"] >= 5
        )
        
        if needs_suggestion:
            # Analyze patterns for suggestion
            patterns = analyze_mistake_patterns(all_mistakes, 'en')  # Will be improved with actual language
            return {
                "needs_suggestion": True,
                "reason": f"Threshold met: {severity_counts}",
                "patterns": patterns[:3],  # Top 3 patterns for suggestions
                "severity_counts": severity_counts
            }
        else:
            return {
                "needs_suggestion": False,
                "reason": f"Threshold not met: {severity_counts}",
                "severity_counts": severity_counts
            }
            
    except Exception as e:
        logging.error(f"Error checking suggestion threshold: {e}")
        return {"needs_suggestion": False, "reason": f"Error: {str(e)}"}

@app.get("/api/lesson_suggestions/check")
async def check_lesson_suggestions(
    curriculum_id: str, 
    auto_generate: bool = Query(default=False),
    token: str = Query(...)
):
    """Check if user has pending lesson suggestions or meets threshold for new ones."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('*').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        # Check for existing suggestions from today (pending or seen)
        today = datetime.now().date().isoformat()
        existing_suggestions = supabase.table('lesson_suggestions').select('*').eq('user_id', user_id).eq('curriculum_id', curriculum_id).in_('status', ['pending', 'seen']).gte('created_at', f'{today}T00:00:00').execute()
        
        if existing_suggestions.data:
            # Count total lessons across all suggestion records
            total_lesson_count = 0
            has_unseen = False
            for suggestion in existing_suggestions.data:
                generated_lessons = suggestion.get('generated_lessons', [])
                total_lesson_count += len(generated_lessons)
                if suggestion.get('status') == 'pending':
                    has_unseen = True
            
            return {
                "has_suggestions": True,
                "suggestion_count": total_lesson_count,
                "type": "existing",
                "suggestions": existing_suggestions.data,
                "from_today": True,
                "is_unseen": has_unseen
            }
        
        # Check if user meets threshold for new suggestions
        threshold_check = await check_lesson_suggestion_threshold(user_id, curriculum_id)
        
        if threshold_check["needs_suggestion"]:
            if auto_generate:
                # Auto-generate suggestions for daily check
                try:
                    suggestions = await auto_generate_daily_suggestions(user_id, curriculum_id, threshold_check)
                    return {
                        "has_suggestions": True,
                        "suggestion_count": len(suggestions.get("lessons", [])),
                        "type": "auto_generated",
                        "suggestions": [suggestions],
                        "from_today": True
                    }
                except Exception as e:
                    logging.error(f"Error auto-generating suggestions: {e}")
                    # Fall back to threshold_met response
                    pass
            
            return {
                "has_suggestions": True,
                "suggestion_count": 0,  # Will be generated manually
                "type": "threshold_met",
                "threshold_data": threshold_check
            }
        
        return {
            "has_suggestions": False,
            "suggestion_count": 0,
            "type": "none",
            "threshold_data": threshold_check
        }
        
    except Exception as e:
        logging.error(f"Error checking lesson suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lesson_suggestions/generate")
async def generate_lesson_suggestions(
    request: dict = Body(...),
    token: str = Query(...)
):
    """Generate up to 3 lesson suggestions based on user's mistake patterns."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        curriculum_id = request.get('curriculum_id')
        
        if not curriculum_id:
            raise HTTPException(status_code=400, detail="curriculum_id is required")
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('*').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        curriculum_data = curriculum.data[0]
        language = curriculum_data['language']
        level = curriculum_data['start_level']
        
        # Check daily limit
        today = datetime.now().date().isoformat()  # Convert to string
        limit_check = supabase.table('user_suggestion_limits').select('*').eq('user_id', user_id).eq('date', today).execute()
        
        current_count = 0
        if limit_check.data:
            current_count = limit_check.data[0]['suggestions_generated']
        
        if current_count >= 3:
            raise HTTPException(status_code=429, detail="Daily suggestion limit reached (3 per day)")
        
        # Get weakness patterns
        threshold_check = await check_lesson_suggestion_threshold(user_id, curriculum_id)
        
        if not threshold_check["needs_suggestion"]:
            raise HTTPException(status_code=400, detail="Threshold not met for suggestions")
        
        patterns = threshold_check["patterns"]
        if not patterns:
            raise HTTPException(status_code=400, detail="No weakness patterns found")
        
        # Generate up to 3 lessons (one for each top pattern)
        generated_lessons = []
        for i, pattern in enumerate(patterns[:3]):
            try:
                lesson = await generate_lesson_with_openai([pattern], language, level)
                lesson['pattern_focus'] = f"{pattern['category']} - {pattern['type']}"
                lesson['pattern_frequency'] = pattern['frequency']
                generated_lessons.append(lesson)
            except Exception as e:
                logging.error(f"Error generating lesson {i+1}: {e}")
                continue
        
        if not generated_lessons:
            raise HTTPException(status_code=500, detail="Failed to generate any lessons")
        
        # Save suggestions to database
        suggestion_data = {
            'user_id': user_id,
            'curriculum_id': curriculum_id,
            'suggestion_data': threshold_check,
            'generated_lessons': generated_lessons,
            'status': 'pending',
            'suggestions_count': len(generated_lessons)
        }
        
        saved_suggestion = supabase.table('lesson_suggestions').insert(suggestion_data).execute()
        
        # Update daily limit
        if limit_check.data:
            supabase.table('user_suggestion_limits').update({
                'suggestions_generated': current_count + 1
            }).eq('user_id', user_id).eq('date', today).execute()
        else:
            supabase.table('user_suggestion_limits').insert({
                'user_id': user_id,
                'date': today,
                'suggestions_generated': 1
            }).execute()
        
        return {
            "suggestion_id": saved_suggestion.data[0]['id'],
            "lessons": generated_lessons,
            "patterns_analyzed": len(patterns),
            "daily_count": current_count + 1
        }
        
    except Exception as e:
        logging.error(f"Error generating lesson suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lesson_suggestions/refresh")
async def refresh_lesson_suggestions(
    request: dict = Body(...),
    token: str = Query(...)
):
    """Force refresh/regenerate lesson suggestions for today."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        curriculum_id = request.get('curriculum_id')
        
        if not curriculum_id:
            raise HTTPException(status_code=400, detail="curriculum_id is required")
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('*').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        # Check daily limit (refreshes count against the limit)
        today = datetime.now().date().isoformat()
        limit_check = supabase.table('user_suggestion_limits').select('*').eq('user_id', user_id).eq('date', today).execute()
        
        current_count = 0
        if limit_check.data:
            current_count = limit_check.data[0]['suggestions_generated']
        
        if current_count >= 3:
            raise HTTPException(status_code=429, detail="Daily suggestion limit reached (3 per day)")
        
        # Mark any existing suggestions from today as refreshed first
        today_suggestions = supabase.table('lesson_suggestions').select('id').eq('user_id', user_id).eq('curriculum_id', curriculum_id).in_('status', ['pending', 'seen']).gte('created_at', f'{today}T00:00:00').execute()
        
        for suggestion in today_suggestions.data:
            supabase.table('lesson_suggestions').update({
                'status': 'refreshed',
                'updated_at': datetime.now().isoformat()
            }).eq('id', suggestion['id']).execute()
        
        # Get weakness patterns
        threshold_check = await check_lesson_suggestion_threshold(user_id, curriculum_id)
        
        if not threshold_check["needs_suggestion"]:
            return {
                "refreshed": True,
                "has_suggestions": False,
                "message": "No suggestions needed based on current mistake patterns"
            }
        
        patterns = threshold_check["patterns"]
        if not patterns:
            return {
                "refreshed": True,
                "has_suggestions": False,
                "message": "No weakness patterns found to target"
            }
        
        # Generate new suggestions using the same logic as manual generation
        curriculum_data = curriculum.data[0]
        language = curriculum_data['language']
        level = curriculum_data['start_level']
        
        generated_lessons = []
        for i, pattern in enumerate(patterns[:3]):
            try:
                lesson = await generate_lesson_with_openai([pattern], language, level)
                lesson['pattern_focus'] = f"{pattern['category']} - {pattern['type']}"
                lesson['pattern_frequency'] = pattern['frequency']
                generated_lessons.append(lesson)
            except Exception as e:
                logging.error(f"Error generating refresh lesson {i+1}: {e}")
                continue
        
        if not generated_lessons:
            raise HTTPException(status_code=500, detail="Failed to generate any lessons")
        
        # Save new suggestions to database
        suggestion_data = {
            'user_id': user_id,
            'curriculum_id': curriculum_id,
            'suggestion_data': threshold_check,
            'generated_lessons': generated_lessons,
            'status': 'pending',
            'suggestions_count': len(generated_lessons)
        }
        
        saved_suggestion = supabase.table('lesson_suggestions').insert(suggestion_data).execute()
        
        # Update daily limit
        if limit_check.data:
            supabase.table('user_suggestion_limits').update({
                'suggestions_generated': current_count + 1
            }).eq('user_id', user_id).eq('date', today).execute()
        else:
            supabase.table('user_suggestion_limits').insert({
                'user_id': user_id,
                'date': today,
                'suggestions_generated': 1
            }).execute()
        
        return {
            "refreshed": True,
            "has_suggestions": True,
            "suggestion_id": saved_suggestion.data[0]['id'],
            "lessons": generated_lessons,
            "suggestion_count": len(generated_lessons),
            "daily_count": current_count + 1
        }
        
    except Exception as e:
        logging.error(f"Error refreshing lesson suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lesson_suggestions/{suggestion_id}/mark_seen")
async def mark_suggestion_as_seen(suggestion_id: str, token: str = Query(...)):
    """Mark a lesson suggestion as seen (changes notification from red to grey)."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Update suggestion status to seen
        result = supabase.table('lesson_suggestions').update({
            'status': 'seen',
            'updated_at': datetime.now().isoformat()
        }).eq('id', suggestion_id).eq('user_id', user_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        
        return {"marked_seen": True}
        
    except Exception as e:
        logging.error(f"Error marking suggestion as seen: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lesson_suggestions/{suggestion_id}/dismiss")
async def dismiss_lesson_suggestion(
    suggestion_id: str, 
    request: dict = Body(default={}),
    token: str = Query(...)
):
    """Mark a lesson suggestion or individual lesson as dismissed."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        lesson_index = request.get('lesson_index')  # Optional: dismiss specific lesson
        
        if lesson_index is not None:
            # Dismiss individual lesson - remove it from the generated_lessons array
            suggestion = supabase.table('lesson_suggestions').select('*').eq('id', suggestion_id).eq('user_id', user_id).execute()
            
            if not suggestion.data:
                raise HTTPException(status_code=404, detail="Suggestion not found")
            
            suggestion_data = suggestion.data[0]
            generated_lessons = suggestion_data.get('generated_lessons', [])
            
            if lesson_index >= len(generated_lessons):
                raise HTTPException(status_code=400, detail="Invalid lesson index")
            
            # Remove the lesson at the specified index
            generated_lessons.pop(lesson_index)
            
            # If no lessons left, mark entire suggestion as dismissed
            if not generated_lessons:
                result = supabase.table('lesson_suggestions').update({
                    'status': 'dismissed',
                    'generated_lessons': [],
                    'suggestions_count': 0,
                    'updated_at': datetime.now().isoformat()
                }).eq('id', suggestion_id).execute()
            else:
                # Update with remaining lessons
                result = supabase.table('lesson_suggestions').update({
                    'generated_lessons': generated_lessons,
                    'suggestions_count': len(generated_lessons),
                    'updated_at': datetime.now().isoformat()
                }).eq('id', suggestion_id).execute()
        else:
            # Dismiss entire suggestion
            result = supabase.table('lesson_suggestions').update({
                'status': 'dismissed',
                'updated_at': datetime.now().isoformat()
            }).eq('id', suggestion_id).eq('user_id', user_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        
        return {"dismissed": True}
        
    except Exception as e:
        logging.error(f"Error dismissing suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lesson_suggestions/{suggestion_id}/use")
async def use_lesson_suggestion(
    suggestion_id: str,
    request: dict = Body(...),
    token: str = Query(...)
):
    """Create a custom lesson from a suggestion."""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        lesson_index = request.get('lesson_index', 0)
        
        # Get the suggestion
        suggestion = supabase.table('lesson_suggestions').select('*').eq('id', suggestion_id).eq('user_id', user_id).execute()
        
        if not suggestion.data:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        
        suggestion_data = suggestion.data[0]
        generated_lessons = suggestion_data['generated_lessons']
        
        if lesson_index >= len(generated_lessons):
            raise HTTPException(status_code=400, detail="Invalid lesson index")
        
        selected_lesson = generated_lessons[lesson_index]
        
        # Save as custom lesson template
        custom_lesson = supabase.table('custom_lesson_templates').insert({
            'user_id': user_id,
            'curriculum_id': suggestion_data['curriculum_id'],
            'title': selected_lesson['title'],
            'language': selected_lesson.get('language', 'en'),
            'difficulty': selected_lesson['difficulty'],
            'objectives': selected_lesson['objectives'],
            'content': selected_lesson['content'],
            'cultural_element': selected_lesson['cultural_element'],
            'practice_activity': selected_lesson['practice_activity'],
            'targeted_weaknesses': selected_lesson['targeted_weaknesses'],
            'order_num': 999
        }).execute()
        
        # Remove the used lesson from the suggestions
        generated_lessons.pop(lesson_index)
        
        # Update the suggestion record
        if not generated_lessons:
            # If no lessons left, mark entire suggestion as used
            supabase.table('lesson_suggestions').update({
                'status': 'used',
                'generated_lessons': [],
                'suggestions_count': 0,
                'updated_at': datetime.now().isoformat()
            }).eq('id', suggestion_id).execute()
        else:
            # Update with remaining lessons
            supabase.table('lesson_suggestions').update({
                'generated_lessons': generated_lessons,
                'suggestions_count': len(generated_lessons),
                'updated_at': datetime.now().isoformat()
            }).eq('id', suggestion_id).execute()
        
        return {
            "lesson_created": True,
            "lesson_id": custom_lesson.data[0]['id'],
            "lesson": custom_lesson.data[0]
        }
        
    except Exception as e:
        logging.error(f"Error using lesson suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Lesson Progress API Endpoints

@app.get("/api/lesson_progress/{progress_id}")
async def get_lesson_progress(progress_id: str, token: str = Query(...)):
    """Get detailed lesson progress information"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        progress = supabase.table('lesson_progress').select('*').eq('id', progress_id).eq('user_id', user_id).execute()
        
        if not progress.data:
            raise HTTPException(status_code=404, detail="Progress record not found")
        
        return progress.data[0]
        
    except Exception as e:
        logging.error(f"Error getting lesson progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/curriculums/{curriculum_id}/progress")
async def get_curriculum_progress(curriculum_id: str, token: str = Query(...)):
    """Get progress for all lessons in a curriculum"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('id').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        # Get all progress records for this curriculum
        progress = supabase.table('lesson_progress').select('*').eq('user_id', user_id).eq('curriculum_id', curriculum_id).execute()
        
        return progress.data
        
    except InvalidTokenError as e:
        logging.error(f"JWT authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting curriculum progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/curriculums/{curriculum_id}/lessons_with_progress")
async def get_lessons_with_progress(curriculum_id: str, language: str = Query(...), token: str = Query(...)):
    """Get all lesson templates with their progress status in one efficient call"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('id').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        # Get all lesson templates for the language
        lesson_templates = supabase.table('lesson_templates').select('*').eq('language', language).order('order_num', desc=False).execute()
        
        # Get all progress records for this curriculum
        progress_records = supabase.table('lesson_progress').select('*').eq('user_id', user_id).eq('curriculum_id', curriculum_id).execute()
        
        # Create a map of lesson_id to progress
        progress_map = {str(p['lesson_id']): p for p in progress_records.data if p.get('lesson_id')}
        
        # Combine lessons with their progress
        lessons_with_progress = []
        for lesson in lesson_templates.data:
            lesson_data = dict(lesson)
            lesson_id = str(lesson['id'])
            
            if lesson_id in progress_map:
                lesson_data['progress'] = progress_map[lesson_id]
            else:
                lesson_data['progress'] = {
                    'status': 'not_started',
                    'turns_completed': 0,
                    'required_turns': 7
                }
            
            lessons_with_progress.append(lesson_data)
        
        return lessons_with_progress
        
    except InvalidTokenError as e:
        logging.error(f"JWT authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting lessons with progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class CompleteLessonRequest(BaseModel):
    progress_id: str

@app.post("/api/lesson_progress/complete")
async def complete_lesson(
    request: CompleteLessonRequest,
    token: str = Query(...)
):
    """Complete a lesson and trigger knowledge update + snapshot creation"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        progress_id = request.progress_id
        
        # Add Sentry breadcrumb for lesson completion tracking
        if sentry_dsn:
            sentry_sdk.add_breadcrumb(
                message="Lesson completion initiated",
                data={
                    "progress_id": progress_id,
                    "user_id": user_id
                },
                level="info"
            )
        
        # Update lesson progress to completed
        result = supabase.table('lesson_progress').update({
            'status': 'completed',
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', progress_id).eq('user_id', user_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Progress record not found")
        
        progress_data = result.data[0]
        
        # Get curriculum and conversation info for the snapshot
        curriculum_id = progress_data.get('curriculum_id')
        conversation_id = progress_data.get('conversation_id')
        
        # Get language from the conversation
        language = None
        if conversation_id:
            conv_result = supabase.table('conversations').select('language').eq('id', conversation_id).execute()
            if conv_result.data:
                language = conv_result.data[0]['language']
        
        if language and curriculum_id:
            # Update user knowledge incrementally
            logging.info(f"Updating user knowledge for lesson completion: {progress_id}")
            await update_user_knowledge_incrementally(user_id, language)
            
            # Create verb knowledge snapshot for fast report card generation
            logging.info(f"Creating verb knowledge snapshot for lesson completion: {progress_id}")
            await create_verb_knowledge_snapshot(
                user_id, language, curriculum_id, progress_id, conversation_id
            )
        
        return {"success": True, "progress": progress_data}
        
    except Exception as e:
        logging.error(f"Error completing lesson: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/lessons/{lesson_id}/progress")
async def get_lesson_progress_by_lesson(
    lesson_id: str,
    curriculum_id: str = Query(...),
    token: str = Query(...)
):
    """Get progress for a specific lesson"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('id').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        # Get progress for this lesson (lesson_id is UUID, not integer)
        progress = supabase.table('lesson_progress').select('*').eq('user_id', user_id).eq('lesson_id', lesson_id).eq('curriculum_id', curriculum_id).execute()
        
        if not progress.data:
            return {"status": "not_started", "turns_completed": 0, "required_turns": 7}
        
        return progress.data[0]
        
    except InvalidTokenError as e:
        logging.error(f"JWT authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting lesson progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/custom_lessons/{custom_lesson_id}/progress")
async def get_custom_lesson_progress(
    custom_lesson_id: str,
    curriculum_id: str = Query(...),
    token: str = Query(...)
):
    """Get progress for a specific custom lesson"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        # Verify curriculum ownership
        curriculum = supabase.table('curriculums').select('id').eq('id', curriculum_id).eq('user_id', user_id).execute()
        if not curriculum.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        # Get progress for this custom lesson
        progress = supabase.table('lesson_progress').select('*').eq('user_id', user_id).eq('custom_lesson_id', custom_lesson_id).eq('curriculum_id', curriculum_id).execute()
        
        if not progress.data:
            return {"status": "not_started", "turns_completed": 0, "required_turns": 7}
        
        return progress.data[0]
        
    except Exception as e:
        logging.error(f"Error getting custom lesson progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Incremental User Knowledge Analysis Functions
@app.get("/api/lesson_progress/{progress_id}/summary")
async def get_lesson_summary(progress_id: str, token: str = Query(...)):
    """Get lesson completion summary with achievements and feedback analysis"""
    try:
        # Handle JWT verification separately to return proper 401 errors
        try:
            user_payload = verify_jwt(token)
            user_id = user_payload["sub"]
        except jwt.InvalidTokenError as e:
            logging.warning(f"[Lesson Summary] Invalid JWT token: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        except Exception as e:
            logging.warning(f"[Lesson Summary] JWT verification failed: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        logging.info(f"[Lesson Summary] Fetching summary for progress_id: {progress_id}, user_id: {user_id}")
        
        # Verify progress belongs to user
        progress = supabase.table('lesson_progress').select('*').eq('id', progress_id).eq('user_id', user_id).execute()
        
        if not progress.data:
            logging.error(f"[Lesson Summary] Progress record not found for id: {progress_id}")
            raise HTTPException(status_code=404, detail="Progress record not found")
        
        # Use the optimized approach (using snapshots)
        try:
            logging.info(f"[Lesson Summary] Attempting optimized summary generation...")
            summary = await get_lesson_summary_optimized(progress_id)
            logging.info(f"[Lesson Summary] ✅ Optimized summary generated successfully!")
            return summary
        except Exception as e:
            logging.error(f"[Lesson Summary] Failed to generate lesson summary: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Unable to generate lesson report card. This could be due to missing data snapshots or a technical issue. Please try again later or contact support if the problem persists."
            )

        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logging.error(f"Error getting lesson summary: {e}")
        logging.error(f"Error type: {type(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_verb_badge_achievements(user_id: str, conversation_id: str, curriculum_id: str) -> list:
    """Generate verb badge achievements by comparing before/after knowledge states"""
    achievements = []
    
    try:
        logging.info(f"[Verb Badges] Analyzing verb achievements for user {user_id}")
        
        # Get curriculum language
        curriculum = supabase.table('curriculums').select('language').eq('id', curriculum_id).execute()
        if not curriculum.data:
            logging.warning("[Verb Badges] Could not find curriculum")
            return achievements
        
        language = curriculum.data[0]['language']
        
        # Step 1: Get CURRENT knowledge (after lesson analysis)
        current_knowledge_record = supabase.table('user_knowledge').select('knowledge_json, analyzed_conversations').eq('user_id', user_id).eq('language', language).execute()
        if not current_knowledge_record.data:
            logging.info("[Verb Badges] No knowledge record found")
            return []
        
        current_knowledge = current_knowledge_record.data[0].get('knowledge_json', {})
        current_verbs = current_knowledge.get('verbs', {})
        analyzed_conversations = current_knowledge_record.data[0].get('analyzed_conversations', [])
        
        # Step 2: Determine if this conversation was just analyzed
        if conversation_id not in analyzed_conversations:
            logging.info("[Verb Badges] This conversation hasn't been analyzed yet")
            return []
        
        # Step 3: Reconstruct BEFORE state by re-analyzing without this conversation
        before_conversations = [conv_id for conv_id in analyzed_conversations if conv_id != conversation_id]
        if not before_conversations:
            # This was the first conversation - everything is new!
            logging.info("[Verb Badges] First conversation - awarding new verb discoveries")
            for verb_lemma, tenses in current_verbs.items():
                achievements.append({
                    'id': f'new_verb_{verb_lemma}',
                    'title': 'New Verb Explorer! 🆕',
                    'description': f'Used your first verb: {verb_lemma}',
                    'icon': '🌟',
                    'type': 'new',
                    'value': verb_lemma,
                    'category': 'major'  # Add category for frontend grouping
                })
            return achievements
        
        # Step 4: Get BEFORE knowledge by re-analyzing previous conversations
        before_knowledge = await analyze_conversations_incrementally(user_id, language, before_conversations)
        if not before_knowledge:
            logging.warning("[Verb Badges] Could not reconstruct before state")
            return []
        
        before_verbs = before_knowledge.get('verbs', {})
        
        # Step 5: Compare BEFORE vs AFTER to find discoveries
        major_discoveries = []  # New verbs, new tenses
        minor_discoveries = []  # New persons
        
        for verb_lemma, current_tenses in current_verbs.items():
            if verb_lemma not in before_verbs:
                # MAJOR: Completely new verb
                major_discoveries.append({
                    'type': 'new_verb',
                    'verb': verb_lemma,
                    'title': f'New Verb Explorer! 🆕',
                    'description': f'Used a brand new verb',
                    'value': verb_lemma
                })
                logging.info(f"[Verb Badges] New verb discovered: {verb_lemma}")
            else:
                # Verb exists - check for new tenses and persons
                before_tenses = before_verbs[verb_lemma]
                
                for tense, current_persons in current_tenses.items():
                    if tense not in before_tenses:
                        # MAJOR: New tense for existing verb
                        major_discoveries.append({
                            'type': 'new_tense',
                            'verb': verb_lemma,
                            'tense': tense,
                            'title': f'Tense Master! ⏰',
                            'description': f'Used existing verb in a new tense',
                            'value': f'{verb_lemma} ({tense})'
                        })
                        logging.info(f"[Verb Badges] New tense: {verb_lemma} in {tense}")
                    else:
                        # Check for new persons in existing tense
                        before_persons = set(before_tenses[tense])
                        new_persons = set(current_persons) - before_persons
                        
                        if new_persons:
                            # MINOR: New person for existing verb+tense
                            for person in new_persons:
                                minor_discoveries.append({
                                    'type': 'new_person',
                                    'verb': verb_lemma,
                                    'tense': tense,
                                    'person': person,
                                    'title': f'Person Shifter! 👥',
                                    'description': f'Used verb with a new grammatical person',
                                    'value': f'{verb_lemma} ({person})'
                                })
                                logging.info(f"[Verb Badges] New person: {verb_lemma} {tense} {person}")
        
        # Step 6: Generate achievements for ALL discoveries (no limits)
        # Award all major discoveries
        for discovery in major_discoveries:
            achievements.append({
                'id': f"{discovery['type']}_{discovery['verb']}_{discovery.get('tense', '')}",
                'title': discovery['title'],
                'description': discovery['description'],
                'icon': '🌟' if discovery['type'] == 'new_verb' else '⏰',
                'type': 'new' if discovery['type'] == 'new_verb' else 'improved',
                'value': discovery['value'],
                'category': 'major'  # Add category for frontend grouping
            })
        
        # Award all minor discoveries
        for discovery in minor_discoveries:
            achievements.append({
                'id': f"{discovery['type']}_{discovery['verb']}_{discovery['tense']}_{discovery['person']}",
                'title': discovery['title'],
                'description': discovery['description'],
                'icon': '👤',
                'type': 'improved',
                'value': discovery['value'],
                'category': 'minor'  # Add category for frontend grouping
            })
        
        # Step 7: Check for milestones
        total_verbs_now = len(current_verbs)
        total_verbs_before = len(before_verbs)
        
        milestones = [10, 25, 50, 100, 150, 200]
        for milestone in milestones:
            if total_verbs_before < milestone <= total_verbs_now:
                achievements.append({
                    'id': f'verb_milestone_{milestone}',
                    'title': f'Verb Collection Milestone! 📚',
                    'description': f'Reached {milestone} total verbs in your vocabulary',
                    'icon': '🏆',
                    'type': 'milestone',
                    'value': f'{total_verbs_now} verbs',
                    'category': 'milestone'  # Add category for frontend grouping
                })
                break  # Only one milestone per lesson
        
        # No limits - let frontend handle organization
        
        if achievements:
            logging.info(f"[Verb Badges] Generated {len(achievements)} verb achievements")
        
        return achievements
        
    except Exception as e:
        logging.error(f"[Verb Badges] Error generating achievements: {e}")
        import traceback
        logging.error(f"[Verb Badges] Traceback: {traceback.format_exc()}")
        return []



async def generate_achievements(user_id: str, progress_data: dict, user_messages: list, total_words: int, duration: timedelta, conversation_id: str = None) -> list:
    """Generate achievements based on lesson performance"""
    achievements = []
    
    try:
        logging.info(f"[Achievements] Generating achievements for user {user_id}")
        
        # Get user's historical data for comparison
        all_progress = supabase.table('lesson_progress').select('*').eq('user_id', user_id).eq('status', 'completed').execute()
        
        current_turns = progress_data.get('turns_completed', 0)
        current_duration_minutes = duration.total_seconds() / 60
        
        logging.info(f"[Achievements] Current turns: {current_turns}, duration: {current_duration_minutes:.1f}m")
        
        # Verb Badge Achievements - use knowledge analysis results
        if conversation_id:
            curriculum_id = progress_data.get('curriculum_id')
            if curriculum_id:
                verb_achievements = await generate_verb_badge_achievements(user_id, conversation_id, curriculum_id)
                achievements.extend(verb_achievements)
        
        # Achievement 1: Longest conversation
        if all_progress.data:
            max_turns = max([p.get('turns_completed', 0) for p in all_progress.data])
            if current_turns >= max_turns:
                achievements.append({
                    'id': 'longest_conversation',
                    'title': 'Marathon Talker! 🏃‍♂️',
                    'description': 'Your longest conversation yet!',
                    'icon': '💬',
                    'type': 'new' if current_turns > max_turns else 'improved',
                    'value': f'{current_turns} turns'
                })
        else:
            # First lesson completion
            achievements.append({
                'id': 'first_lesson',
                'title': 'Getting Started! 🌟',
                'description': 'Completed your first lesson',
                'icon': '🎉',
                'type': 'new',
                'value': 'First lesson'
            })
        
        # Achievement 2: Word usage
        if total_words > 100:
            achievements.append({
                'id': 'wordsmith',
                'title': 'Wordsmith! 📚',
                'description': 'Used lots of words in this conversation',
                'icon': '📝',
                'type': 'milestone',
                'value': f'{total_words} words'
            })
        
        # Achievement 3: Consistent practice
        recent_lessons = []
        for p in (all_progress.data or []):
            if p.get('completed_at'):
                try:
                    # Use the same safe datetime parsing
                    def parse_datetime_safe_achievements(datetime_str):
                        """Safely parse datetime string, handling microseconds"""
                        try:
                            if datetime_str.endswith('Z'):
                                datetime_str = datetime_str.replace('Z', '+00:00')
                            
                            if '.' in datetime_str:
                                date_part, time_part = datetime_str.split('.')
                                if '+' in time_part:
                                    microseconds, timezone_part = time_part.split('+')
                                    microseconds = microseconds[:6].ljust(6, '0')
                                    datetime_str = f"{date_part}.{microseconds}+{timezone_part}"
                                elif time_part.count(':') >= 2:
                                    microseconds = time_part[:6].ljust(6, '0')
                                    datetime_str = f"{date_part}.{microseconds}"
                            
                            return datetime.fromisoformat(datetime_str)
                        except:
                            if '.' in datetime_str:
                                datetime_str = datetime_str.split('.')[0] + '+00:00'
                            return datetime.fromisoformat(datetime_str)
                    
                    completed_date = parse_datetime_safe_achievements(p['completed_at'])
                    if completed_date > datetime.now(timezone.utc) - timedelta(days=7):
                        recent_lessons.append(p)
                except Exception as e:
                    logging.warning(f"[Achievements] Error parsing completed_at for progress {p.get('id')}: {e}")
                    continue
        
        if len(recent_lessons) >= 3:
            achievements.append({
                'id': 'consistent_learner',
                'title': 'Consistent Learner! 🔥',
                'description': 'Completed multiple lessons this week',
                'icon': '🔥',
                'type': 'improved',
                'value': f'{len(recent_lessons)} lessons'
            })
        
        # Achievement 4: Grammar variety (based on message complexity)
        complex_sentences = sum(1 for msg in user_messages if len(msg.get('content', '').split()) > 10)
        if complex_sentences >= 3:
            achievements.append({
                'id': 'complex_speaker',
                'title': 'Complex Speaker! 🧩',
                'description': 'Used complex sentence structures',
                'icon': '🎯',
                'type': 'improved',
                'value': f'{complex_sentences} complex sentences'
            })
        
        logging.info(f"[Achievements] Generated {len(achievements)} achievements")
        return achievements
        
    except Exception as e:
        logging.error(f"Error generating achievements: {e}")
        import traceback
        logging.error(f"Achievements traceback: {traceback.format_exc()}")
        # Return a basic achievement if generation fails
        return [{
            'id': 'lesson_completed',
            'title': 'Lesson Complete! 🎉',
            'description': 'Successfully completed the lesson',
            'icon': '✅',
            'type': 'milestone',
            'value': 'Completed'
        }]

async def get_unanalyzed_conversations(user_id: str, language: str) -> List[str]:
    """Get conversations that haven't been analyzed for user knowledge yet"""
    try:
        # Get the last analysis timestamp
        last_analysis = supabase.table('user_knowledge').select('updated_at').eq('user_id', user_id).eq('language', language).execute()
        
        last_update = None
        if last_analysis.data:
            last_update = last_analysis.data[0].get('updated_at')
        
        # Get conversations created after the last analysis
        conversations_query = supabase.table('conversations').select('id, created_at').eq('user_id', user_id).eq('language', language)
        
        if last_update:
            # Only get conversations created after the last knowledge update
            conversations_query = conversations_query.gt('created_at', last_update)
        
        conversations = conversations_query.order('created_at', desc=False).execute()
        
        # Extract conversation IDs
        unanalyzed = [conv['id'] for conv in conversations.data]
        
        logging.info(f"[Knowledge Analysis] Found {len(unanalyzed)} unanalyzed conversations for user {user_id} since {last_update or 'beginning'}")
        return unanalyzed
        
    except Exception as e:
        logging.error(f"Error getting unanalyzed conversations: {e}")
        return []

async def analyze_conversations_incrementally(user_id: str, language: str, conversation_ids: List[str]) -> Optional[dict]:
    """Analyze specific conversations and merge with existing knowledge"""
    try:
        if not conversation_ids:
            return None
        
        # Get messages from the specified conversations
        new_messages = []
        for conv_id in conversation_ids:
            messages = supabase.table('messages').select('content').eq('conversation_id', conv_id).eq('role', 'user').order('created_at', desc=False).execute()
            new_messages.extend([m['content'] for m in messages.data])
        
        if not new_messages:
            logging.info(f"[Knowledge Analysis] No new messages found in conversations")
            return None
        
        # Build prompt for new message analysis
        transcript = "\n".join(new_messages)
        prompt = f"""Analyze the following new {language} messages from a language learner. Extract vocabulary and grammar patterns they've used.

For each part of speech, provide a list of unique words/patterns the user has demonstrated:
- nouns: specific nouns they've used
- pronouns: pronouns they've used correctly
- adjectives: adjectives they've used
- verbs: for each verb, list the lemma and what tenses/persons they've used
- adverbs: adverbs they've used
- prepositions: prepositions they've used correctly
- conjunctions: conjunctions they've used
- articles: articles they've used correctly
- interjections: interjections they've used

Focus on words they used correctly and contextually appropriately. Don't include obvious mistakes.

Output ONLY a valid JSON object with this structure:
{{
  "nouns": ["word1", "word2"],
  "pronouns": ["word1", "word2"],
  "adjectives": ["word1", "word2"],
  "verbs": {{
    "lemma1": {{
      "present": ["1st_person", "3rd_person"],
      "past": ["1st_person"]
    }}
  }},
  "adverbs": ["word1", "word2"],
  "prepositions": ["word1", "word2"],
  "conjunctions": ["word1", "word2"],
  "articles": ["word1", "word2"],
  "interjections": ["word1", "word2"]
}}

Messages to analyze:
{transcript}"""

        # Call OpenAI API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4-turbo-preview",
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1500
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logging.error(f"OpenAI API error in knowledge analysis: {error_text}")
                    return None
                
                response_data = await response.json()
                result = response_data["choices"][0]["message"]["content"]
        
        # Parse the result
        new_knowledge = extract_json_from_response(result)
        if not new_knowledge:
            logging.error(f"Failed to parse knowledge analysis result")
            return None
        
        logging.info(f"[Knowledge Analysis] Analyzed {len(new_messages)} new messages")
        return new_knowledge
        
    except Exception as e:
        logging.error(f"Error in incremental knowledge analysis: {e}")
        return None

def merge_knowledge_data(existing: dict, new: dict) -> dict:
    """Merge new knowledge data with existing knowledge"""
    try:
        if not existing:
            return new
        if not new:
            return existing
        
        merged = {}
        
        # Merge simple lists (nouns, pronouns, etc.)
        simple_lists = ['nouns', 'pronouns', 'adjectives', 'adverbs', 'prepositions', 'conjunctions', 'articles', 'interjections']
        
        for category in simple_lists:
            existing_items = set(existing.get(category, []))
            new_items = set(new.get(category, []))
            merged[category] = sorted(list(existing_items | new_items))
        
        # Merge verb structures (more complex)
        merged['verbs'] = dict(existing.get('verbs', {}))
        new_verbs = new.get('verbs', {})
        
        for lemma, tenses in new_verbs.items():
            if lemma in merged['verbs']:
                # Merge tenses for existing verb
                for tense, persons in tenses.items():
                    if tense in merged['verbs'][lemma]:
                        # Merge persons for existing tense
                        existing_persons = set(merged['verbs'][lemma][tense])
                        new_persons = set(persons)
                        merged['verbs'][lemma][tense] = sorted(list(existing_persons | new_persons))
                    else:
                        # New tense for existing verb
                        merged['verbs'][lemma][tense] = sorted(persons)
            else:
                # New verb
                merged['verbs'][lemma] = {tense: sorted(persons) for tense, persons in tenses.items()}
        
        return merged
        
    except Exception as e:
        logging.error(f"Error merging knowledge data: {e}")
        return existing or new or {}

async def update_user_knowledge_incrementally(user_id: str, language: str, conversation_ids: List[str] = None) -> bool:
    """Update user knowledge with new conversation data"""
    try:
        # Get conversations to analyze
        if conversation_ids is None:
            conversation_ids = await get_unanalyzed_conversations(user_id, language)
        
        if not conversation_ids:
            logging.info(f"[Knowledge Update] No new conversations to analyze for user {user_id}")
            return True
        
        # Analyze new conversations
        new_knowledge = await analyze_conversations_incrementally(user_id, language, conversation_ids)
        if not new_knowledge:
            return False
        
        # Get existing knowledge
        existing_result = supabase.table('user_knowledge').select('*').eq('user_id', user_id).eq('language', language).execute()
        
        existing_knowledge = {}
        
        if existing_result.data:
            existing_knowledge = existing_result.data[0].get('knowledge_json', {})
        
        # Merge knowledge
        updated_knowledge = merge_knowledge_data(existing_knowledge, new_knowledge)
        
        # Save to database
        update_data = {
            'knowledge_json': updated_knowledge,
            'updated_at': datetime.now().isoformat()
        }
        
        if existing_result.data:
            # Update existing record
            supabase.table('user_knowledge').update(update_data).eq('user_id', user_id).eq('language', language).execute()
        else:
            # Create new record
            update_data.update({
                'user_id': user_id,
                'language': language
            })
            supabase.table('user_knowledge').insert(update_data).execute()
        
        logging.info(f"[Knowledge Update] Updated knowledge for user {user_id}, analyzed {len(conversation_ids)} new conversations")
        return True
        
    except Exception as e:
        logging.error(f"Error updating user knowledge incrementally: {e}")
        return False

def extract_json_from_response(text: str) -> Optional[dict]:
    """Extract JSON from LLM response text"""
    import re
    
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*', '', text)
        text = text.strip('`\n')
    
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except Exception:
            pass
    
    try:
        return json.loads(text)
    except Exception:
        return None

# Add a function to create verb knowledge snapshots
async def create_verb_knowledge_snapshot(user_id: str, language: str, curriculum_id: str, 
                                       lesson_progress_id: str, conversation_id: Optional[str] = None,
                                       snapshot_reason: str = "lesson_completion") -> bool:
    """Create a verb knowledge snapshot when a lesson is completed."""
    try:
        # Get current user knowledge
        result = supabase.table('user_knowledge').select('knowledge_json').eq(
            'user_id', user_id
        ).eq('language', language).execute()
        
        if not result.data:
            logging.warning(f"No user knowledge found for user {user_id}, language {language}")
            verb_knowledge = {}
        else:
            knowledge = result.data[0]['knowledge_json']
            verb_knowledge = knowledge.get('verbs', {}) if knowledge else {}
        
        # Create the snapshot
        snapshot_data = {
            'user_id': user_id,
            'language': language,
            'curriculum_id': curriculum_id,
            'lesson_progress_id': lesson_progress_id,
            'conversation_id': conversation_id,
            'snapshot_reason': snapshot_reason,
            'verb_knowledge': verb_knowledge,
            'snapshot_at': datetime.now(timezone.utc).isoformat()
        }
        
        snapshot_result = supabase.table('verb_knowledge_snapshots').insert(snapshot_data).execute()
        
        if snapshot_result.data:
            logging.info(f"Created verb knowledge snapshot for lesson {lesson_progress_id}")
            return True
        else:
            logging.error(f"Failed to create verb knowledge snapshot: {snapshot_result}")
            return False
            
    except Exception as e:
        logging.error(f"Error creating verb knowledge snapshot: {e}")
        return False

class InsightCard(BaseModel):
    id: str
    message: str
    type: str
    severity: str
    trend: str
    action: str
    chart_type: str
    chart_data: dict
    examples: Optional[List[dict]] = None
    improvement_percentage: Optional[float] = None

class InsightsResponse(BaseModel):
    insights: List[InsightCard]
    last_updated: datetime
    analysis_period: str
    summary: dict

class VerbProgressDataPoint(BaseModel):
    date: str
    verbs_total: int

class VerbProgressResponse(BaseModel):
    timeline_data: List[VerbProgressDataPoint]
    total_snapshots: int
    unique_dates: int
    date_range: Dict[str, Optional[str]]

class ProgressMetricDataPoint(BaseModel):
    date: str
    verbs_total: Optional[int] = None
    accuracy_rate: Optional[float] = None

class ProgressMetricResponse(BaseModel):
    timeline_data: List[ProgressMetricDataPoint]
    total_snapshots: int
    unique_dates: int
    date_range: Dict[str, Optional[str]]
    metric_type: str

async def analyze_feedback_patterns(user_id: str, curriculum_id: str, days: int = 30) -> dict:
    """Analyze user's feedback patterns over the specified time period"""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Get feedback data
    feedback_result = supabase.table('message_feedback') \
        .select('*, messages!inner(*, conversations!inner(*))') \
        .eq('messages.conversations.user_id', user_id) \
        .eq('messages.conversations.curriculum_id', curriculum_id) \
        .gte('created_at', start_date.isoformat()) \
        .execute()
    
    logging.info(f"Feedback query returned {len(feedback_result.data)} records for user {user_id}, curriculum {curriculum_id}, since {start_date.isoformat()}")
    
    if not feedback_result.data:
        logging.info(f"No feedback data found for user {user_id}, curriculum {curriculum_id}")
        return {}
    
    # Process feedback data
    mistake_patterns = defaultdict(lambda: {'count': 0, 'examples': [], 'conversations': set(), 'trend_data': []})
    conversation_quality = {'total_messages': 0, 'total_conversations': 0, 'mistake_free_conversations': 0}
    time_based_data = defaultdict(list)
    
    for feedback in feedback_result.data:
        conversation_id = feedback['messages']['conversation_id']
        
        # Handle datetime parsing with potential microseconds issues
        created_at_str = feedback['created_at'].replace('Z', '+00:00')
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            # Handle irregular microseconds format by padding or truncating to 6 digits
            import re
            # Find microseconds part and fix it
            match = re.search(r'\.(\d+)\+', created_at_str)
            if match:
                microseconds = match.group(1)
                # Pad or truncate to exactly 6 digits
                fixed_microseconds = microseconds.ljust(6, '0')[:6]
                created_at_str = re.sub(r'\.(\d+)\+', f'.{fixed_microseconds}+', created_at_str)
            created_at = datetime.fromisoformat(created_at_str)
        
        # Track conversation quality
        conversation_quality['total_messages'] += 1
        conversation_quality['total_conversations'] = len(set(f['messages']['conversation_id'] for f in feedback_result.data))
        
        # Process mistakes
        for mistake in feedback.get('mistakes', []):
            pattern_key = f"{mistake['category']}_{mistake['type']}"
            mistake_patterns[pattern_key]['count'] += 1
            mistake_patterns[pattern_key]['conversations'].add(conversation_id)
            mistake_patterns[pattern_key]['examples'].append({
                'error': mistake['error'],
                'correction': mistake['correction'],
                'explanation': mistake['explanation'],
                'severity': mistake['severity'],
                'date': created_at.date().isoformat()
            })
            
            # Track time-based data for trends
            week_key = created_at.strftime('%Y-W%U')
            time_based_data[pattern_key].append({
                'week': week_key,
                'date': created_at,
                'severity': mistake['severity']
            })
    
    # Calculate trends
    for pattern_key in mistake_patterns:
        pattern_data = time_based_data[pattern_key]
        if len(pattern_data) >= 2:
            # Simple trend calculation: compare first half vs second half
            pattern_data.sort(key=lambda x: x['date'])
            mid_point = len(pattern_data) // 2
            first_half = len(pattern_data[:mid_point])
            second_half = len(pattern_data[mid_point:])
            
            if second_half > first_half * 1.2:
                trend = 'increasing'
            elif second_half < first_half * 0.8:
                trend = 'decreasing'
            else:
                trend = 'stable'
            
            mistake_patterns[pattern_key]['trend'] = trend
        else:
            mistake_patterns[pattern_key]['trend'] = 'stable'
    
    # Convert sets to counts for serialization
    for pattern in mistake_patterns.values():
        pattern['conversation_count'] = len(pattern['conversations'])
        pattern['conversations'] = list(pattern['conversations'])
    
    return {
        'mistake_patterns': dict(mistake_patterns),
        'conversation_quality': conversation_quality,
        'analysis_period': f"{days} days",
        'total_feedback_items': len(feedback_result.data)
    }

async def generate_insight_cards(patterns_data: dict, user_id: str, language: str) -> List[InsightCard]:
    """Generate conversational insight cards using AI"""
    if not patterns_data or not patterns_data.get('mistake_patterns'):
        return []
    
    # Get user's current level for context
    try:
        user_result = supabase.table('users').select('*').eq('id', user_id).execute()
        user_level = user_result.data[0].get('level', 'B1') if user_result.data else 'B1'
    except:
        user_level = 'B1'
    
    client = AsyncOpenAI(api_key=API_KEY)
    
    # Prepare patterns for AI analysis
    top_patterns = sorted(
        patterns_data['mistake_patterns'].items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )[:5]  # Top 5 patterns
    
    patterns_summary = []
    for pattern_key, data in top_patterns:
        category, mistake_type = pattern_key.split('_', 1)
        patterns_summary.append({
            'category': category,
            'type': mistake_type.replace('_', ' '),
            'frequency': data['count'],
            'conversations_affected': data['conversation_count'],
            'trend': data['trend'],
            'recent_example': data['examples'][-1] if data['examples'] else None
        })
    
    prompt = f"""
    Generate 3-5 conversational insight cards for a {language} language learner (level: {user_level}).
    Based on their recent feedback data, create encouraging but actionable insights.
    
    Learning Data:
    - Total conversations: {patterns_data['conversation_quality']['total_conversations']}
    - Total messages analyzed: {patterns_data['conversation_quality']['total_messages']}
    - Analysis period: {patterns_data['analysis_period']}
    
    Top Mistake Patterns:
    {json.dumps(patterns_summary, indent=2)}
    
    For each insight, provide:
    1. A conversational message (friendly, encouraging, specific)
    2. The insight type (grammar_pattern, vocabulary_growth, progress_trend, etc.)
    3. Severity (low, moderate, high)
    4. Trend (increasing, decreasing, stable)
    5. Suggested action
    6. Appropriate chart type (frequency_over_time, category_comparison, progress_trend)
    
    Guidelines:
    - Mix improvement areas with positive progress
    - Be specific about mistakes (e.g., "ser vs estar confusion" not just "grammar")
    - Use emojis sparingly and appropriately
    - Keep messages under 100 characters
    - Focus on actionable insights
    
    Return as JSON array of insight objects.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        try:
            content = response.choices[0].message.content
            # Try to extract JSON if it's wrapped in markdown code blocks
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            ai_insights = json.loads(content)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse AI response as JSON: {e}")
            logging.error(f"AI response content: {response.choices[0].message.content}")
            return []
        
        # Convert AI insights to InsightCard objects with chart data
        insight_cards = []
        for i, insight in enumerate(ai_insights):
            chart_data = await generate_chart_data_for_insight(
                insight, patterns_data, top_patterns
            )
            
            card = InsightCard(
                id=str(uuid.uuid4()),
                message=insight.get('message', ''),
                type=insight.get('type', 'general'),
                severity=insight.get('severity', 'moderate'),
                trend=insight.get('trend', 'stable'),
                action=insight.get('action', ''),
                chart_type=insight.get('chart_type', 'frequency_over_time'),
                chart_data=chart_data,
                examples=insight.get('examples', []),
                improvement_percentage=insight.get('improvement_percentage')
            )
            insight_cards.append(card)
        
        return insight_cards
        
    except Exception as e:
        logging.error(f"Error generating insights: {e}")
        return []

async def generate_chart_data_for_insight(insight: dict, patterns_data: dict, top_patterns: list) -> dict:
    """Generate appropriate chart data for each insight"""
    chart_type = insight.get('chart_type', 'frequency_over_time')
    
    if chart_type == 'frequency_over_time':
        # Find the most relevant pattern for this insight
        relevant_pattern = None
        for pattern_key, data in top_patterns:
            if any(word in insight['message'].lower() for word in pattern_key.lower().split('_')):
                relevant_pattern = data
                break
        
        if relevant_pattern:
            # Create weekly frequency data
            examples = relevant_pattern['examples']
            weekly_data = defaultdict(int)
            for example in examples:
                week = datetime.fromisoformat(example['date']).strftime('%Y-W%U')
                weekly_data[week] += 1
            
            sorted_weeks = sorted(weekly_data.keys())
            return {
                'labels': [f"Week {w.split('-W')[1]}" for w in sorted_weeks],
                'data': [weekly_data[w] for w in sorted_weeks],
                'type': 'line'
            }
    
    elif chart_type == 'category_comparison':
        # Compare mistake categories
        category_counts = defaultdict(int)
        for pattern_key, data in top_patterns:
            category = pattern_key.split('_')[0]
            category_counts[category] += data['count']
        
        return {
            'labels': list(category_counts.keys()),
            'data': list(category_counts.values()),
            'type': 'bar'
        }
    
    elif chart_type == 'progress_trend':
        # Show overall progress trend
        total_conversations = patterns_data['conversation_quality']['total_conversations']
        total_mistakes = sum(data['count'] for _, data in top_patterns)
        
        return {
            'labels': ['Mistakes per Conversation'],
            'data': [total_mistakes / max(total_conversations, 1)],
            'target': 2.0,  # Target fewer than 2 mistakes per conversation
            'type': 'gauge'
        }
    
    # Default empty chart data
    return {'labels': [], 'data': [], 'type': 'line'}

@app.get("/api/insights", response_model=InsightsResponse)
async def get_user_insights(
    curriculum_id: str = Query(...),
    days: int = Query(default=30),
    refresh: bool = Query(default=False),
    token: str = Query(...)
):
    """Get AI-generated insights for user's language learning progress (cached)"""
    try:
        # Verify JWT token
        payload = verify_jwt(token)
        user_id = payload['sub']
        
        logging.info(f"Getting insights for user {user_id}, curriculum {curriculum_id}")
        
        # Get curriculum to determine language
        curriculum_result = supabase.table('curriculums') \
            .select('language') \
            .eq('id', curriculum_id) \
            .eq('user_id', user_id) \
            .execute()
        
        if not curriculum_result.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        language = curriculum_result.data[0]['language']
        logging.info(f"Curriculum language: {language}")
        
        # Use cached insights or generate new ones (or force refresh)
        if refresh:
            # Invalidate cache first if force refresh requested
            await invalidate_insights_cache(user_id, curriculum_id)
            logging.info(f"Force refresh requested - invalidated cache for user {user_id}, curriculum {curriculum_id}")
        
        try:
            # Add timeout handling for the full insights generation
            import asyncio
            return await asyncio.wait_for(
                get_cached_insights_or_generate(user_id, curriculum_id, language, days),
                timeout=30.0  # 30 second timeout
            )
        except asyncio.TimeoutError:
            logging.warning(f"Insights generation timed out for user {user_id}, curriculum {curriculum_id}")
            # Return simple insights as fallback
            try:
                # Quick fallback - get basic feedback data
                feedback_result = supabase.table('message_feedback') \
                    .select('mistakes, created_at, messages!inner(conversation_id, conversations!inner(user_id, curriculum_id))') \
                    .eq('messages.conversations.user_id', user_id) \
                    .eq('messages.conversations.curriculum_id', curriculum_id) \
                    .limit(100) \
                    .execute()
                
                if feedback_result.data and len(feedback_result.data) >= 3:
                    simple_insights = await generate_simple_insights(feedback_result.data, language)
                    unique_conversations = len(set(f['messages']['conversation_id'] for f in feedback_result.data))
                    
                    return InsightsResponse(
                        insights=simple_insights,
                        last_updated=datetime.now(timezone.utc),
                        analysis_period=f"{days} days (simplified due to timeout)",
                        summary={
                            'total_patterns': len(simple_insights),
                            'total_conversations': unique_conversations,
                            'improvement_areas': len([i for i in simple_insights if i.severity in ['moderate', 'high']])
                        }
                    )
            except Exception as fallback_error:
                logging.error(f"Fallback insights also failed: {fallback_error}")
            
            # Final fallback
            return InsightsResponse(
                insights=[],
                last_updated=datetime.now(timezone.utc),
                analysis_period=f"{days} days",
                summary={
                    'total_patterns': 0,
                    'total_conversations': 0,
                    'improvement_areas': 0
                }
            )
        except Exception as cache_error:
            logging.error(f"Error in caching function: {cache_error}")
            # Fallback: return empty insights instead of crashing
            return InsightsResponse(
                insights=[],
                last_updated=datetime.now(timezone.utc),
                analysis_period=f"{days} days",
                summary={
                    'total_patterns': 0,
                    'total_conversations': 0,
                    'improvement_areas': 0
                }
            )
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT token error: {e}")
        raise HTTPException(status_code=401, detail="Session expired. Please refresh the page and try again.")
    except Exception as e:
        logging.error(f"Error generating insights: {e}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate insights: {str(e)}")

@app.get("/api/insights/debug-curriculums")
async def debug_curriculums():
    """Debug endpoint to show available curriculums"""
    try:
        # Get all curriculums to see valid IDs
        curriculum_result = supabase.table('curriculums') \
            .select('id, user_id, language, created_at') \
            .execute()
        
        return {
            'total_curriculums': len(curriculum_result.data),
            'curriculums': curriculum_result.data
        }
        
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}

@app.get("/api/insights/debug-simple")
async def debug_insights_simple(curriculum_id: str = Query(...)):
    """Simple debug endpoint without JWT verification"""
    try:
        # For debugging, let's check data for your specific curriculum
        # Get curriculum info first
        curriculum_result = supabase.table('curriculums') \
            .select('user_id, language') \
            .eq('id', curriculum_id) \
            .execute()
        
        if not curriculum_result.data:
            return {'error': 'Curriculum not found', 'curriculum_id': curriculum_id}
        
        user_id = curriculum_result.data[0]['user_id']
        language = curriculum_result.data[0]['language']
        
        # Check feedback data for this curriculum
        feedback_result = supabase.table('message_feedback') \
            .select('*, messages!inner(*, conversations!inner(*))') \
            .eq('messages.conversations.user_id', user_id) \
            .eq('messages.conversations.curriculum_id', curriculum_id) \
            .execute()
        
        feedback_with_mistakes = []
        total_mistakes = 0
        mistake_categories = {}
        
        for feedback in feedback_result.data:
            mistakes = feedback.get('mistakes', [])
            if mistakes and len(mistakes) > 0:
                feedback_with_mistakes.append({
                    'message_id': feedback['message_id'],
                    'created_at': feedback['created_at'],
                    'mistake_count': len(mistakes),
                    'mistakes_sample': mistakes[:2]
                })
                total_mistakes += len(mistakes)
                
                for mistake in mistakes:
                    category = mistake.get('category', 'unknown')
                    mistake_categories[category] = mistake_categories.get(category, 0) + 1
        
        return {
            'curriculum_id': curriculum_id,
            'user_id': user_id,
            'language': language,
            'total_feedback_records': len(feedback_result.data),
            'feedback_with_mistakes': len(feedback_with_mistakes),
            'total_mistakes': total_mistakes,
            'mistake_categories': mistake_categories,
            'feedback_samples': feedback_with_mistakes[:5],
            'has_sufficient_data': len(feedback_with_mistakes) >= 3
        }
        
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}

@app.get("/api/insights/debug")
async def debug_insights_data(
    curriculum_id: str = Query(...),
    token: str = Query(...)
):
    """Debug endpoint to check what feedback data exists"""
    try:
        # Handle token format issues
        if not token or len(token.split('.')) != 3:
            return {'error': 'Invalid token format', 'token_segments': len(token.split('.')) if token else 0}
        
        # Verify JWT token
        payload = verify_jwt(token)
        user_id = payload['sub']
        
        # Get curriculum info
        curriculum_result = supabase.table('curriculums') \
            .select('language') \
            .eq('id', curriculum_id) \
            .eq('user_id', user_id) \
            .execute()
        
        if not curriculum_result.data:
            return {'error': 'Curriculum not found'}
        
        language = curriculum_result.data[0]['language']
        
        # Get feedback with joined data for this user and language
        feedback_result = supabase.table('message_feedback') \
            .select('*, messages!inner(*, conversations!inner(*))') \
            .eq('messages.conversations.user_id', user_id) \
            .eq('messages.conversations.curriculum_id', curriculum_id) \
            .execute()
        
        feedback_with_mistakes = []
        total_mistakes = 0
        mistake_categories = {}
        
        for feedback in feedback_result.data:
            mistakes = feedback.get('mistakes', [])
            if mistakes and len(mistakes) > 0:
                feedback_with_mistakes.append({
                    'message_id': feedback['message_id'],
                    'created_at': feedback['created_at'],
                    'mistake_count': len(mistakes),
                    'mistakes_sample': mistakes[:2]  # First 2 mistakes
                })
                total_mistakes += len(mistakes)
                
                # Count by category
                for mistake in mistakes:
                    category = mistake.get('category', 'unknown')
                    mistake_categories[category] = mistake_categories.get(category, 0) + 1
        
        return {
            'user_id': user_id,
            'curriculum_id': curriculum_id,
            'language': language,
            'total_feedback_records': len(feedback_result.data),
            'feedback_with_mistakes': len(feedback_with_mistakes),
            'total_mistakes': total_mistakes,
            'mistake_categories': mistake_categories,
            'feedback_samples': feedback_with_mistakes[:5],  # First 5
            'raw_query_result_count': len(feedback_result.data),
            'has_sufficient_data': len(feedback_with_mistakes) >= 3
        }
        
    except Exception as e:
        logging.error(f"Debug error: {e}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        return {'error': str(e), 'traceback': traceback.format_exc()}

@app.get("/api/insights/demo", response_model=InsightsResponse)
async def get_demo_insights(language: str = Query(default="es")):
    """Get demo insights for testing purposes"""
    demo_insights = [
        InsightCard(
            id="demo-1",
            message="You've been mixing up 'ser' and 'estar' in 8 out of 10 conversations 🤔",
            type="grammar_pattern",
            severity="moderate",
            trend="stable",
            action="Practice the fundamental differences between ser (permanent) and estar (temporary)",
            chart_type="frequency_over_time",
            chart_data={
                "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                "data": [3, 2, 4, 1],
                "type": "line"
            },
            examples=[
                {
                    "error": "Mi hermana está doctora",
                    "correction": "Mi hermana es doctora",
                    "explanation": "Use 'ser' for permanent characteristics like professions",
                    "date": "2024-01-15"
                },
                {
                    "error": "El café es caliente",
                    "correction": "El café está caliente",
                    "explanation": "Use 'estar' for temporary states like temperature",
                    "date": "2024-01-16"
                }
            ]
        ),
        InsightCard(
            id="demo-2",
            message="Your past tense conjugations have improved 40% this month! 🌟",
            type="progress_trend",
            severity="low",
            trend="decreasing",
            action="Keep practicing past tense verbs to maintain your progress",
            chart_type="progress_trend",
            chart_data={
                "labels": ["Past Tense Accuracy"],
                "data": [85],
                "target": 90,
                "type": "gauge"
            },
            improvement_percentage=40
        ),
        InsightCard(
            id="demo-3",
            message="You learned 15 new words this week but only used 3 in conversations 💭",
            type="vocabulary_usage",
            severity="moderate",
            trend="stable",
            action="Try to actively use new vocabulary words in your next conversation",
            chart_type="category_comparison",
            chart_data={
                "labels": ["Words Learned", "Words Used"],
                "data": [15, 3],
                "type": "bar"
            }
        ),
        InsightCard(
            id="demo-4",
            message="Your subjunctive mood usage is getting stronger! 💪",
            type="grammar_improvement",
            severity="low",
            trend="improving",
            action="Continue practicing with complex sentence structures",
            chart_type="frequency_over_time",
            chart_data={
                "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                "data": [1, 2, 3, 5],
                "type": "line"
            },
            improvement_percentage=25
        )
    ]
    
    return InsightsResponse(
        insights=demo_insights,
        last_updated=datetime.now(timezone.utc),
        analysis_period="30 days",
        summary={
            "total_patterns": 8,
            "total_conversations": 12,
            "improvement_areas": 2
        }
    )

# Add after the existing models, around line 3460
class CachedInsights(BaseModel):
    curriculum_id: str
    user_id: str
    insights_data: dict
    last_feedback_count: int
    created_at: datetime
    updated_at: datetime

# Add this function after analyze_feedback_patterns function, around line 3560
async def get_cached_insights_or_generate(user_id: str, curriculum_id: str, language: str, days: int = 30) -> InsightsResponse:
    """Get cached insights or generate new ones if data has changed"""
    
    logging.info(f"Getting insights for user {user_id}, curriculum {curriculum_id}, language {language}")
    
    # First, get current feedback count for this curriculum using SQL
    try:
        feedback_count_result = supabase.rpc('get_feedback_count_for_curriculum', {
            'p_user_id': user_id,
            'p_curriculum_id': curriculum_id
        }).execute()
        
        current_feedback_count = feedback_count_result.data if feedback_count_result.data else 0
        if isinstance(current_feedback_count, list) and len(current_feedback_count) > 0:
            current_feedback_count = current_feedback_count[0]
    except Exception as e:
        logging.warning(f"Failed to get feedback count via RPC, falling back to direct SQL: {e}")
        # Fallback: use a simpler approach
        try:
            # Get all conversations for this curriculum/user and count their feedback
            conversations_result = supabase.table('conversations') \
                .select('id') \
                .eq('user_id', user_id) \
                .eq('curriculum_id', curriculum_id) \
                .execute()
            
            if conversations_result.data:
                conversation_ids = [conv['id'] for conv in conversations_result.data]
                if conversation_ids:
                    # Get messages for these conversations
                    messages_result = supabase.table('messages') \
                        .select('id') \
                        .in_('conversation_id', conversation_ids) \
                        .execute()
                    
                    if messages_result.data:
                        message_ids = [msg['id'] for msg in messages_result.data]
                        if message_ids:
                            # Count feedback for these messages
                            feedback_result = supabase.table('message_feedback') \
                                .select('id', count='exact') \
                                .in_('message_id', message_ids) \
                                .execute()
                            current_feedback_count = feedback_result.count or 0
                        else:
                            current_feedback_count = 0
                    else:
                        current_feedback_count = 0
                else:
                    current_feedback_count = 0
            else:
                current_feedback_count = 0
        except Exception as fallback_error:
            logging.error(f"Fallback feedback counting also failed: {fallback_error}")
            current_feedback_count = 0
    
    # Check if we have cached insights
    cached_result = supabase.table('cached_insights') \
        .select('*') \
        .eq('curriculum_id', curriculum_id) \
        .eq('user_id', user_id) \
        .execute()
    
    # If we have cached insights and feedback count hasn't changed, return cached
    if cached_result.data and len(cached_result.data) > 0:
        cached = cached_result.data[0]
        if cached['last_feedback_count'] == current_feedback_count:
            logging.info(f"Returning cached insights for user {user_id}, curriculum {curriculum_id}")
            insights_data = cached['insights_data']
            try:
                # Parse the datetime safely
                last_updated = insights_data['last_updated']
                if isinstance(last_updated, str):
                    # Remove timezone info if present for parsing
                    if last_updated.endswith('Z'):
                        last_updated = last_updated[:-1] + '+00:00'
                    last_updated_dt = datetime.fromisoformat(last_updated)
                else:
                    last_updated_dt = datetime.now(timezone.utc)
                
                return InsightsResponse(
                    insights=[InsightCard(**insight) for insight in insights_data['insights']],
                    last_updated=last_updated_dt,
                    analysis_period=insights_data['analysis_period'],
                    summary=insights_data['summary']
                )
            except Exception as parse_error:
                logging.error(f"Error parsing cached insights: {parse_error}")
                # If parsing fails, regenerate insights
                logging.info("Regenerating insights due to parse error")
                # Continue to generate fresh insights
    
    # Generate new insights since cache is stale or doesn't exist
    logging.info(f"Generating fresh insights for user {user_id}, curriculum {curriculum_id}")
    
    # Analyze feedback patterns
    patterns_data = await analyze_feedback_patterns(user_id, curriculum_id, days)
    
    if not patterns_data:
        # Return empty insights for new users
        empty_response = InsightsResponse(
            insights=[],
            last_updated=datetime.now(timezone.utc),
            analysis_period=f"{days} days",
            summary={
                'total_patterns': 0,
                'total_conversations': 0,
                'improvement_areas': 0
            }
        )
        return empty_response
    
    # Generate AI insights
    insight_cards = await generate_insight_cards(patterns_data, user_id, language)
    
    # Create summary
    summary = {
        'total_patterns': len(patterns_data.get('mistake_patterns', {})),
        'total_conversations': patterns_data.get('conversation_quality', {}).get('total_conversations', 0),
        'improvement_areas': len([card for card in insight_cards if card.severity in ['moderate', 'high']])
    }
    
    # Create response
    response = InsightsResponse(
        insights=insight_cards,
        last_updated=datetime.now(timezone.utc),
        analysis_period=f"{days} days",
        summary=summary
    )
    
    # Cache the insights
    insights_data = {
        'insights': [card.dict() for card in insight_cards],
        'last_updated': response.last_updated.isoformat(),
        'analysis_period': response.analysis_period,
        'summary': response.summary
    }
    
    # Upsert cached insights
    if cached_result.data and len(cached_result.data) > 0:
        # Update existing cache
        supabase.table('cached_insights') \
            .update({
                'insights_data': insights_data,
                'last_feedback_count': current_feedback_count,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }) \
            .eq('curriculum_id', curriculum_id) \
            .eq('user_id', user_id) \
            .execute()
    else:
        # Insert new cache
        supabase.table('cached_insights') \
            .insert({
                'curriculum_id': curriculum_id,
                'user_id': user_id,
                'insights_data': insights_data,
                'last_feedback_count': current_feedback_count,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }) \
            .execute()
    
    return response

# Function to invalidate insights cache when new feedback is added
async def invalidate_insights_cache(user_id: str, curriculum_id: str):
    """Invalidate cached insights for a specific user/curriculum"""
    try:
        supabase.table('cached_insights') \
            .delete() \
            .eq('curriculum_id', curriculum_id) \
            .eq('user_id', user_id) \
            .execute()
        logging.info(f"Invalidated insights cache for user {user_id}, curriculum {curriculum_id}")
    except Exception as e:
        logging.error(f"Error invalidating insights cache: {e}")

async def process_conversation_completion(user_id: str, conversation_id: str, language: str, turns: int):
    """
    Comprehensive post-conversation processing for analytics, insights, and knowledge updates.
    This runs after conversation ends to avoid impacting conversation fluency.
    """
    try:
        logging.info(f"[Post-Conversation] Starting analysis for conversation {conversation_id}, {turns} turns")
        
        # Get conversation details
        def get_conversation():
            return supabase.table('conversations').select('*').eq('id', conversation_id).execute()
        
        conversation_result = await db_manager.execute_query(get_conversation)
        if not conversation_result.data:
            logging.error(f"[Post-Conversation] Conversation not found: {conversation_id}")
            return
        
        conversation = conversation_result.data[0]
        curriculum_id = conversation.get('curriculum_id')
        
        # 1. Update user knowledge with conversation data
        logging.info(f"[Post-Conversation] Updating user knowledge for {user_id}")
        await update_user_knowledge_incrementally(user_id, language, [conversation_id])
        
        # 2. Process language tags from all feedback in this conversation
        logging.info(f"[Post-Conversation] Processing language tags for conversation {conversation_id}")
        await process_conversation_language_tags(conversation_id, language)
        
        # 3. Invalidate insights cache to reflect new data
        if curriculum_id:
            logging.info(f"[Post-Conversation] Invalidating insights cache for curriculum {curriculum_id}")
            await invalidate_insights_cache(user_id, curriculum_id)
        
        # 4. Generate achievements and badges if applicable
        logging.info(f"[Post-Conversation] Generating achievements for conversation {conversation_id}")
        await generate_conversation_achievements(user_id, conversation_id, curriculum_id, turns)
        
        # 5. Create verb knowledge snapshot for lessons
        lesson_id = conversation.get('lesson_id')
        custom_lesson_id = conversation.get('custom_lesson_id')
        if lesson_id or custom_lesson_id:
            logging.info(f"[Post-Conversation] Creating verb knowledge snapshot for lesson")
            # Get lesson progress to create snapshot
            def get_progress():
                return supabase.table('lesson_progress') \
                    .select('id') \
                    .eq('conversation_id', conversation_id) \
                    .execute()
            
            progress_result = await db_manager.execute_query(get_progress)
            if progress_result.data:
                progress_id = progress_result.data[0]['id']
                await create_verb_knowledge_snapshot(
                    user_id, language, curriculum_id, progress_id, 
                    conversation_id, "conversation_completion"
                )
        
        logging.info(f"[Post-Conversation] Completed analysis for conversation {conversation_id}")
        
    except Exception as e:
        logging.error(f"[Post-Conversation] Error processing conversation completion: {e}")

async def process_conversation_language_tags(conversation_id: str, language: str):
    """Process language tags from all feedback in a conversation"""
    try:
        # Get all feedback for this conversation
        def get_feedback():
            return supabase.table('message_feedback') \
                .select('mistakes, messages!inner(conversation_id)') \
                .eq('messages.conversation_id', conversation_id) \
                .execute()
        
        feedback_result = await db_manager.execute_query(get_feedback)
        
        all_tags = []
        for feedback in feedback_result.data:
            for mistake in feedback.get('mistakes', []):
                if mistake.get('languageFeatureTags'):
                    all_tags.extend(mistake['languageFeatureTags'])
        
        if all_tags:
            await record_language_tags(all_tags, language)
            logging.info(f"[Post-Conversation] Processed {len(all_tags)} language tags")
        
    except Exception as e:
        logging.error(f"[Post-Conversation] Error processing language tags: {e}")

async def generate_conversation_achievements(user_id: str, conversation_id: str, curriculum_id: str, turns: int):
    """Generate achievements and badges for completed conversation"""
    try:
        # Generate verb badge achievements if applicable
        if curriculum_id:
            await generate_verb_badge_achievements(user_id, conversation_id, curriculum_id)
            logging.info(f"[Post-Conversation] Generated verb badges for conversation {conversation_id}")
        
    except Exception as e:
        logging.error(f"[Post-Conversation] Error generating achievements: {e}")

@app.get("/api/verb_progress", 
         response_model=VerbProgressResponse,
         summary="Get Verb Learning Progress",
         description="Retrieve a timeline of verb learning progress showing daily verb counts over time")
async def get_verb_progress(
    language: str = Query(..., description="Language code (e.g., 'es', 'fr', 'de')"),
    curriculum_id: str = Query(..., description="Curriculum ID for the specific learning path"),
    limit: int = Query(default=100, description="Maximum number of snapshots to return", ge=1, le=365),
    token: str = Query(..., description="JWT authentication token")
):
    """
    Get verb learning progress timeline from verb knowledge snapshots.
    
    Returns daily aggregated data showing the total number of unique verbs
    learned over time. Data is grouped by date, taking the maximum verb
    count for each day if multiple snapshots exist.
    
    **Response Format:**
    - `timeline_data`: Array of date/verb count pairs
    - `total_snapshots`: Total number of snapshots found
    - `unique_dates`: Number of unique dates with data
    - `date_range`: Start and end dates of the timeline
    """
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Get verb knowledge snapshots
        verb_snapshots = supabase.table('verb_knowledge_snapshots').select(
            'snapshot_at, verb_knowledge'
        ).eq('user_id', user_id).eq('language', language).eq(
            'curriculum_id', curriculum_id
        ).order('snapshot_at').limit(limit).execute()
        
        if not verb_snapshots.data:
            return {"timeline_data": [], "message": "No verb progress data found"}
        
        # Process verb snapshots - group by date and count unique verbs
        from collections import defaultdict
        daily_verb_counts = defaultdict(int)
        
        for snapshot in verb_snapshots.data:
            date = snapshot['snapshot_at'][:10]  # Get YYYY-MM-DD
            verb_knowledge = snapshot.get('verb_knowledge', {})
            verb_count = len(verb_knowledge) if verb_knowledge else 0
            # Take maximum count for each date (in case of multiple snapshots per day)
            daily_verb_counts[date] = max(daily_verb_counts[date], verb_count)
        
        # Convert to timeline format
        timeline_data = []
        for date in sorted(daily_verb_counts.keys()):
            timeline_data.append({
                'date': date,
                'verbs_total': daily_verb_counts[date]
            })
        
        return {
            "timeline_data": timeline_data,
            "total_snapshots": len(verb_snapshots.data),
            "unique_dates": len(daily_verb_counts),
            "date_range": {
                "start": timeline_data[0]['date'] if timeline_data else None,
                "end": timeline_data[-1]['date'] if timeline_data else None
            }
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error in verb progress endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch verb progress: {str(e)}")

@app.get("/api/progress_metrics", 
         response_model=ProgressMetricResponse,
         summary="Get Progress Metrics",
         description="Retrieve timeline data for various progress metrics (verbs, accuracy, etc.)")
async def get_progress_metrics(
    metric_type: str = Query(..., description="Type of metric: 'verbs_total' or 'accuracy_rate'"),
    language: str = Query(..., description="Language code (e.g., 'es', 'fr', 'de')"),
    curriculum_id: str = Query(..., description="Curriculum ID for the specific learning path"),
    limit: int = Query(default=100, description="Maximum number of data points to return", ge=1, le=365),
    token: str = Query(..., description="JWT authentication token")
):
    """
    Get progress metrics timeline for different metric types.
    
    **Supported Metrics:**
    - `verbs_total`: Total number of unique verbs learned over time
    - `accuracy_rate`: Percentage of messages with no mistakes over time
    
    **Response Format:**
    - `timeline_data`: Array of date/metric value pairs
    - `total_snapshots`: Total number of data points found
    - `unique_dates`: Number of unique dates with data
    - `date_range`: Start and end dates of the timeline
    - `metric_type`: The requested metric type
    """
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        if metric_type == "verbs_total":
            # Get verb knowledge snapshots
            verb_snapshots = supabase.table('verb_knowledge_snapshots').select(
                'snapshot_at, verb_knowledge'
            ).eq('user_id', user_id).eq('language', language).eq(
                'curriculum_id', curriculum_id
            ).order('snapshot_at').limit(limit).execute()
            
            if not verb_snapshots.data:
                return {
                    "timeline_data": [], 
                    "total_snapshots": 0,
                    "unique_dates": 0,
                    "date_range": {"start": None, "end": None},
                    "metric_type": metric_type
                }
            
            # Process verb snapshots - group by date and count unique verbs
            from collections import defaultdict
            daily_verb_counts = defaultdict(int)
            
            for snapshot in verb_snapshots.data:
                date = snapshot['snapshot_at'][:10]  # Get YYYY-MM-DD
                verb_knowledge = snapshot.get('verb_knowledge', {})
                verb_count = len(verb_knowledge) if verb_knowledge else 0
                # Take maximum count for each date (in case of multiple snapshots per day)
                daily_verb_counts[date] = max(daily_verb_counts[date], verb_count)
            
            # Convert to timeline format
            timeline_data = []
            for date in sorted(daily_verb_counts.keys()):
                timeline_data.append({
                    'date': date,
                    'verbs_total': daily_verb_counts[date]
                })
            
            return {
                "timeline_data": timeline_data,
                "total_snapshots": len(verb_snapshots.data),
                "unique_dates": len(daily_verb_counts),
                "date_range": {
                    "start": timeline_data[0]['date'] if timeline_data else None,
                    "end": timeline_data[-1]['date'] if timeline_data else None
                },
                "metric_type": metric_type
            }
            
        elif metric_type == "accuracy_rate":
            # Get messages and their feedback for accuracy calculation
            messages_query = supabase.table('messages').select(
                'id, created_at, role, conversations!inner(curriculum_id)'
            ).eq('role', 'user').eq('conversations.curriculum_id', curriculum_id).order('created_at').limit(limit * 10)
            
            messages_result = await db_manager.execute_query(lambda: messages_query.execute())
            
            if not messages_result.data:
                return {
                    "timeline_data": [], 
                    "total_snapshots": 0,
                    "unique_dates": 0,
                    "date_range": {"start": None, "end": None},
                    "metric_type": metric_type
                }
            
            # Get feedback for these messages
            message_ids = [msg['id'] for msg in messages_result.data]
            feedback_query = supabase.table('message_feedback').select(
                'message_id, mistakes'
            ).in_('message_id', message_ids)
            
            feedback_result = await db_manager.execute_query(lambda: feedback_query.execute())
            
            # Create feedback lookup
            feedback_map = {}
            for feedback in feedback_result.data:
                feedback_map[feedback['message_id']] = feedback.get('mistakes', [])
            
            # Group by date and calculate accuracy
            from collections import defaultdict
            daily_stats = defaultdict(lambda: {'total': 0, 'perfect': 0})
            
            for message in messages_result.data:
                date = message['created_at'][:10]  # Get YYYY-MM-DD
                mistakes = feedback_map.get(message['id'], [])
                
                daily_stats[date]['total'] += 1
                if len(mistakes) == 0:  # No mistakes = perfect message
                    daily_stats[date]['perfect'] += 1
            
            # Convert to timeline format
            timeline_data = []
            for date in sorted(daily_stats.keys()):
                stats = daily_stats[date]
                accuracy = (stats['perfect'] / stats['total']) * 100 if stats['total'] > 0 else 0
                timeline_data.append({
                    'date': date,
                    'accuracy_rate': round(accuracy, 1)
                })
            
            return {
                "timeline_data": timeline_data,
                "total_snapshots": len(messages_result.data),
                "unique_dates": len(daily_stats),
                "date_range": {
                    "start": timeline_data[0]['date'] if timeline_data else None,
                    "end": timeline_data[-1]['date'] if timeline_data else None
                },
                "metric_type": metric_type
            }
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported metric type: {metric_type}")
            
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error in progress metrics endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch progress metrics: {str(e)}")

class CompleteConversationRequest(BaseModel):
    conversation_id: str

@app.post("/api/conversations/complete")
async def complete_conversation(
    request: CompleteConversationRequest,
    token: str = Query(...)
):
    """Complete a regular conversation and generate report card"""
    try:
        user_payload = verify_jwt(token)
        user_id = user_payload["sub"]
        
        conversation_id = request.conversation_id
        
        # Verify user owns the conversation
        conv_result = supabase.table('conversations').select('*').eq('id', conversation_id).eq('user_id', user_id).execute()
        if not conv_result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conversation = conv_result.data[0]
        language = conversation['language']
        curriculum_id = conversation.get('curriculum_id')
        
        # Update conversation as completed (add a completed_at timestamp)
        supabase.table('conversations').update({
            'updated_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', conversation_id).execute()
        
        if language and curriculum_id:
            # Update user knowledge incrementally
            logging.info(f"Updating user knowledge for conversation completion: {conversation_id}")
            await update_user_knowledge_incrementally(user_id, language, [conversation_id])
            
            # Create verb knowledge snapshot for the conversation
            logging.info(f"Creating verb knowledge snapshot for conversation completion: {conversation_id}")
            await create_verb_knowledge_snapshot(
                user_id, language, curriculum_id, None, conversation_id, "conversation_completion"
            )
        
        return {"message": "Conversation completed successfully", "conversation_id": conversation_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error completing conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations/{conversation_id}/summary")
async def get_conversation_summary(conversation_id: str, token: str = Query(...)):
    """Generate a conversation summary/report card using unified modular approach"""
    try:
        # Handle JWT verification separately to return proper 401 errors
        try:
            user_payload = verify_jwt(token)
            user_id = user_payload["sub"]
        except jwt.InvalidTokenError as e:
            logging.warning(f"[Conversation Summary] Invalid JWT token: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        except Exception as e:
            logging.warning(f"[Conversation Summary] JWT verification failed: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        logging.info(f"[Conversation Summary] Fetching summary for conversation_id: {conversation_id}, user_id: {user_id}")
        
        # Verify user owns the conversation
        conv_result = supabase.table('conversations').select('*').eq('id', conversation_id).eq('user_id', user_id).execute()
        if not conv_result.data:
            logging.error(f"[Conversation Summary] Conversation not found for id: {conversation_id}")
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Use the new unified data fetcher and report card generator
        from report_card_shared import get_conversation_data, generate_unified_report_card
        
        # Fetch standardized conversation data
        conversation_data = await get_conversation_data(conversation_id)
        
        # Get verb knowledge snapshots for before/after comparison
        before_snapshot = None
        after_snapshot = None
        
        curriculum_id = conv_result.data[0].get('curriculum_id')
        if curriculum_id:
            try:
                # Find snapshot for this conversation
                snapshot_result = supabase.table('verb_knowledge_snapshots').select('*').eq('user_id', user_id).eq('language', conversation_data['language']).eq('conversation_id', conversation_id).execute()
                if snapshot_result.data:
                    after_snapshot = snapshot_result.data[0].get('verb_knowledge', {})
                
                # Try to find a previous snapshot for comparison
                prev_snapshot_result = supabase.table('verb_knowledge_snapshots').select('*').eq('user_id', user_id).eq('language', conversation_data['language']).neq('conversation_id', conversation_id).order('created_at', desc=True).limit(1).execute()
                if prev_snapshot_result.data:
                    before_snapshot = prev_snapshot_result.data[0].get('verb_knowledge', {})
                
            except Exception as e:
                logging.warning(f"Could not get verb snapshots for conversation {conversation_id}: {e}")
        
        # Generate the unified report card
        summary_data = await generate_unified_report_card(conversation_data, before_snapshot, after_snapshot)
        
        logging.info(f"[Conversation Summary] Generated summary with {len(summary_data.get('achievements', []))} achievements and {summary_data.get('totalMistakes', 0)} mistakes")
        
        return summary_data
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating conversation summary: {e}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

def parse_datetime_safe_achievements(datetime_str):
    """Safely parse datetime string for achievements calculation"""
    try:
        if datetime_str.endswith('Z'):
            datetime_str = datetime_str.replace('Z', '+00:00')
        return datetime.fromisoformat(datetime_str)
    except Exception as e:
        logging.error(f"Error parsing datetime '{datetime_str}': {e}")
        return datetime.now(timezone.utc)

@app.get("/api/insights/fast", response_model=InsightsResponse)
async def get_user_insights_fast(
    curriculum_id: str = Query(...),
    days: int = Query(default=30),
    token: str = Query(...)
):
    """Fast insights endpoint with optimized queries and caching"""
    try:
        # Verify JWT token
        payload = verify_jwt(token)
        user_id = payload['sub']
        
        logging.info(f"Getting fast insights for user {user_id}, curriculum {curriculum_id}")
        
        # Get curriculum to determine language
        curriculum_result = supabase.table('curriculums') \
            .select('language') \
            .eq('id', curriculum_id) \
            .eq('user_id', user_id) \
            .execute()
        
        if not curriculum_result.data:
            raise HTTPException(status_code=404, detail="Curriculum not found")
        
        language = curriculum_result.data[0]['language']
        
        # Check for cached insights first (but don't force regeneration)
        cached_result = supabase.table('cached_insights') \
            .select('*') \
            .eq('curriculum_id', curriculum_id) \
            .eq('user_id', user_id) \
            .execute()
        
        # If we have recent cached insights (less than 2 hours old), return them
        if cached_result.data and len(cached_result.data) > 0:
            cached = cached_result.data[0]
            try:
                updated_at = datetime.fromisoformat(cached['updated_at'].replace('Z', '+00:00'))
                age_hours = (datetime.now(timezone.utc) - updated_at).total_seconds() / 3600
                
                if age_hours < 2:  # Use cache if less than 2 hours old
                    logging.info(f"Returning recent cached insights (age: {age_hours:.1f}h)")
                    insights_data = cached['insights_data']
                    
                    return InsightsResponse(
                        insights=[InsightCard(**insight) for insight in insights_data['insights']],
                        last_updated=updated_at,
                        analysis_period=insights_data['analysis_period'],
                        summary=insights_data['summary']
                    )
            except Exception as parse_error:
                logging.warning(f"Error parsing cached insights: {parse_error}")
                # Continue to generate new insights
        
        # Generate simplified insights for speed
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Simplified feedback query - just get basic counts
        feedback_result = supabase.table('message_feedback') \
            .select('mistakes, created_at, messages!inner(conversation_id, conversations!inner(user_id, curriculum_id))') \
            .eq('messages.conversations.user_id', user_id) \
            .eq('messages.conversations.curriculum_id', curriculum_id) \
            .gte('created_at', start_date.isoformat()) \
            .limit(500) \
            .execute()
        
        if not feedback_result.data or len(feedback_result.data) < 3:
            # Not enough data for insights
            return InsightsResponse(
                insights=[],
                last_updated=datetime.now(timezone.utc),
                analysis_period=f"{days} days",
                summary={
                    'total_patterns': 0,
                    'total_conversations': 0,
                    'improvement_areas': 0
                }
            )
        
        # Generate simplified insight cards without AI
        insights = await generate_simple_insights(feedback_result.data, language)
        
        # Create summary
        unique_conversations = len(set(f['messages']['conversation_id'] for f in feedback_result.data))
        total_mistakes = sum(len(f.get('mistakes', [])) for f in feedback_result.data)
        
        summary = {
            'total_patterns': len(insights),
            'total_conversations': unique_conversations,
            'improvement_areas': len([i for i in insights if i.severity in ['moderate', 'high']])
        }
        
        response = InsightsResponse(
            insights=insights,
            last_updated=datetime.now(timezone.utc),
            analysis_period=f"{days} days",
            summary=summary
        )
        
        # Cache the results
        insights_data = {
            'insights': [card.dict() for card in insights],
            'last_updated': response.last_updated.isoformat(),
            'analysis_period': response.analysis_period,
            'summary': response.summary
        }
        
        # Upsert cached insights
        if cached_result.data and len(cached_result.data) > 0:
            supabase.table('cached_insights') \
                .update({
                    'insights_data': insights_data,
                    'last_feedback_count': len(feedback_result.data),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }) \
                .eq('curriculum_id', curriculum_id) \
                .eq('user_id', user_id) \
                .execute()
        else:
            supabase.table('cached_insights') \
                .insert({
                    'curriculum_id': curriculum_id,
                    'user_id': user_id,
                    'insights_data': insights_data,
                    'last_feedback_count': len(feedback_result.data),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }) \
                .execute()
        
        return response
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT token error: {e}")
        raise HTTPException(status_code=401, detail="Session expired. Please refresh the page and try again.")
    except Exception as e:
        logging.error(f"Error generating fast insights: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate insights: {str(e)}")

async def generate_simple_insights(feedback_data: list, language: str) -> List[InsightCard]:
    """Generate insights without AI for faster response"""
    insights = []
    
    # Count mistakes by category
    mistake_counts = defaultdict(int)
    total_mistakes = 0
    recent_mistakes = []
    
    for feedback in feedback_data:
        for mistake in feedback.get('mistakes', []):
            category = mistake.get('category', 'unknown')
            mistake_counts[category] += 1
            total_mistakes += 1
            
            # Track recent mistakes for examples
            try:
                created_at = datetime.fromisoformat(feedback['created_at'].replace('Z', '+00:00'))
                recent_mistakes.append((created_at, mistake, category))
            except:
                recent_mistakes.append((datetime.now(), mistake, category))
    
    if total_mistakes == 0:
        return []
    
    # Sort mistakes by recency and category frequency
    recent_mistakes.sort(key=lambda x: x[0], reverse=True)
    top_categories = sorted(mistake_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Generate insights based on patterns
    for i, (category, count) in enumerate(top_categories):
        percentage = (count / total_mistakes) * 100
        
        # Find examples for this category
        examples = [m[1] for m in recent_mistakes if m[2] == category][:2]
        
        if percentage > 40:
            severity = 'high'
            trend = 'increasing'
            message = f"Your {category} mistakes make up {percentage:.0f}% of all errors"
            action = f"Focus on {category} rules and practice specific exercises"
        elif percentage > 20:
            severity = 'moderate'  
            trend = 'stable'
            message = f"{category.title()} needs attention ({percentage:.0f}% of mistakes)"
            action = f"Review {category} fundamentals and practice regularly"
        else:
            severity = 'low'
            trend = 'stable'
            message = f"Minor {category} issues ({percentage:.0f}% of mistakes)"
            action = f"Occasional {category} review recommended"
        
        insights.append(InsightCard(
            id=str(uuid.uuid4()),
            message=message,
            type=f"{category}_pattern",
            severity=severity,
            trend=trend,
            action=action,
            chart_type='category_comparison',
            chart_data={
                'category': category,
                'count': count,
                'percentage': percentage,
                'examples': examples[:2]
            }
        ))
    
    # Add overall progress insight
    if len(feedback_data) >= 10:
        insights.append(InsightCard(
            id=str(uuid.uuid4()),
            message=f"Analyzed {len(feedback_data)} messages with {total_mistakes} total mistakes",
            type='progress_summary',
            severity='low',
            trend='stable',
            action="Keep practicing to see improvement trends",
            chart_type='progress_trend',
            chart_data={
                'total_feedback': len(feedback_data),
                'total_mistakes': total_mistakes,
                'avg_mistakes_per_message': total_mistakes / len(feedback_data)
            }
        ))
    
    return insights[:4]  # Limit to 4 insights for fast response

@app.post("/api/generate_targeted_lesson")
async def generate_targeted_lesson(
    request: dict = Body(...),
    token: str = Query(...)
):
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Extract request data
        curriculum_id = request.get('curriculum_id')
        insight_data = request.get('insight_data', {})
        language = request.get('language', 'es')
        
        # Get curriculum to determine level
        curriculum_result = supabase.table('curriculums').select('start_level').eq('id', curriculum_id).execute()
        level = 'A1'  # Default
        if curriculum_result.data:
            level = curriculum_result.data[0]['start_level']
        
        # Extract insight information
        category = insight_data.get('category', 'grammar')
        message = insight_data.get('message', '')
        severity = insight_data.get('severity', 'medium')
        examples = insight_data.get('chart_data', {}).get('examples', [])
        
        # Generate lesson using OpenAI
        lesson_data = await generate_targeted_lesson_with_openai(
            category, message, severity, examples, language, level
        )
        
        return lesson_data
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error generating targeted lesson: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate lesson: {str(e)}")

async def generate_targeted_lesson_with_openai(
    category: str, 
    insight_message: str, 
    severity: str, 
    examples: list, 
    language: str, 
    level: str
) -> dict:
    """Generate a targeted lesson using OpenAI based on specific insights"""
    
    # Map languages to their names
    language_names = {
        'es': 'Spanish',
        'en': 'English', 
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'kn': 'Kannada'
    }
    
    language_name = language_names.get(language, language)
    
    # Create examples text
    examples_text = ""
    if examples:
        examples_text = "\n".join([f"- Error: '{ex.get('error', '')}' → Correction: '{ex.get('correction', '')}'" for ex in examples[:3]])
    
    prompt = f"""
Create a targeted {language_name} lesson for level {level} that addresses this specific learning need:

**Issue Identified:** {insight_message}
**Category:** {category}
**Severity:** {severity}
**Examples from user's mistakes:**
{examples_text}

Generate a lesson that directly targets this weakness with:

1. **Title**: A clear, specific lesson title
2. **Difficulty**: Choose from "Easy", "Medium", or "Challenging" 
3. **Objectives**: What the student will learn/practice (be specific to the identified issue)
4. **Content**: Key grammar/vocabulary points to cover (focus on the problem area)
5. **Cultural Element**: A relevant cultural context for this language feature
6. **Practice Activity**: A conversation scenario that will practice this specific skill

Format as JSON:
{{
  "title": "...",
  "difficulty": "...",
  "objectives": "...",
  "content": "...",
  "cultural_element": "...",
  "practice_activity": "..."
}}

Make this lesson directly address the user's specific weakness while being engaging and culturally relevant.
"""

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON response
        import json
        try:
            lesson_data = json.loads(content)
            return lesson_data
        except json.JSONDecodeError:
            # If not valid JSON, try to extract JSON from the content
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                lesson_data = json.loads(json_match.group())
                return lesson_data
            else:
                raise ValueError("Could not parse lesson data as JSON")
                
    except Exception as e:
        logging.error(f"Error generating targeted lesson with OpenAI: {e}")
        raise

# User Interests API Endpoints

class UserInterest(BaseModel):
    parent_interest: str
    child_interest: Optional[str] = None
    context: str

class SaveInterestsRequest(BaseModel):
    interests: List[UserInterest]

@app.get("/api/user_interests")
async def get_user_interests(token: str = Query(...)):
    """Get all interests for the authenticated user"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Get user interests from database
        result = supabase.table('user_interests').select('*').eq('user_id', user_id).order('parent_interest, child_interest').execute()
        
        # Group interests by parent category
        grouped_interests = {}
        for interest in result.data:
            parent = interest['parent_interest']
            if parent not in grouped_interests:
                grouped_interests[parent] = []
            
            if interest['child_interest']:
                grouped_interests[parent].append({
                    'child_interest': interest['child_interest'],
                    'context': interest['context']
                })
        
        return {
            'interests': grouped_interests
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error fetching user interests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch interests: {str(e)}")

@app.post("/api/user_interests")
async def save_user_interests(request: SaveInterestsRequest, token: str = Query(...)):
    """Save user interests, replacing all existing interests"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Delete all existing interests for this user
        supabase.table('user_interests').delete().eq('user_id', user_id).execute()
        
        # Insert new interests
        interests_to_insert = []
        for interest in request.interests:
            interests_to_insert.append({
                'user_id': user_id,
                'parent_interest': interest.parent_interest,
                'child_interest': interest.child_interest,
                'context': interest.context,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
        
        if interests_to_insert:
            result = supabase.table('user_interests').insert(interests_to_insert).execute()
            
            # Trigger personalized context generation in the background
            asyncio.create_task(generate_contexts_for_new_interests(user_id))
            
        return {
            'message': f'Successfully saved {len(interests_to_insert)} interests',
            'count': len(interests_to_insert)
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error saving user interests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save interests: {str(e)}")

@app.delete("/api/user_interests/{parent_interest}")
async def delete_parent_interest(parent_interest: str, token: str = Query(...)):
    """Delete all interests under a parent category"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Delete all interests for this parent category
        result = supabase.table('user_interests').delete().eq('user_id', user_id).eq('parent_interest', parent_interest).execute()
        
        # Trigger personalized context regeneration in the background
        asyncio.create_task(generate_contexts_for_new_interests(user_id))
        
        return {
            'message': f'Successfully deleted all interests under {parent_interest}',
            'deleted_count': len(result.data) if result.data else 0
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error deleting parent interest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete interest: {str(e)}")

@app.delete("/api/user_interests/{parent_interest}/{child_interest}")
async def delete_child_interest(parent_interest: str, child_interest: str, token: str = Query(...)):
    """Delete a specific child interest"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Delete the specific child interest
        result = supabase.table('user_interests').delete().eq('user_id', user_id).eq('parent_interest', parent_interest).eq('child_interest', child_interest).execute()
        
        # Trigger personalized context regeneration in the background
        asyncio.create_task(generate_contexts_for_new_interests(user_id))
        
        return {
            'message': f'Successfully deleted {child_interest} from {parent_interest}',
            'deleted_count': len(result.data) if result.data else 0
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error deleting child interest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete interest: {str(e)}")

@app.delete("/api/user_interests")
async def clear_all_user_interests(token: str = Query(...)):
    """Delete all user interests and personalized contexts"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Delete all user interests
        interests_result = supabase.table('user_interests').delete().eq('user_id', user_id).execute()
        
        # Delete all personalized contexts
        contexts_result = supabase.table('personalized_contexts').delete().eq('user_id', user_id).execute()
        
        logging.info(f"Cleared all interests for user {user_id}")
        
        return {
            'success': True,
            'message': 'All interests and personalized contexts have been cleared successfully.',
            'deleted_interests': len(interests_result.data) if interests_result.data else 0,
            'deleted_contexts': len(contexts_result.data) if contexts_result.data else 0
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error clearing all interests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear interests: {str(e)}")

# Personalized Contexts API Endpoints

class PersonalizedContext(BaseModel):
    id: str
    title: str
    description: str
    icon: str
    context_instructions: str
    interest_tags: List[str]

class GenerateContextsRequest(BaseModel):
    count: int = 6  # Number of contexts to generate

@app.get("/api/personalized_contexts")
async def get_personalized_contexts(token: str = Query(...)):
    """Get all personalized contexts for the authenticated user"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Get personalized contexts from database
        result = supabase.table('personalized_contexts').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        
        contexts = []
        for context in result.data:
            contexts.append({
                'id': context['id'],
                'title': context['title'],
                'description': context['description'],
                'icon': context['icon'],
                'interest_tags': context['interest_tags']
            })
        
        return {
            'contexts': contexts,
            'count': len(contexts)
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error fetching personalized contexts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch contexts: {str(e)}")

@app.post("/api/personalized_contexts/generate")
async def generate_personalized_contexts(request: GenerateContextsRequest, token: str = Query(...)):
    """Generate new personalized contexts based on user interests"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Get user interests from database
        interests_result = supabase.table('user_interests').select('*').eq('user_id', user_id).execute()
        
        if not interests_result.data:
            raise HTTPException(status_code=400, detail="No user interests found. Please set your interests first.")
        
        # Format interests for prompt - group by parent category to make relationships clear
        interests_by_parent = {}
        for interest in interests_result.data:
            parent = interest['parent_interest']
            if parent not in interests_by_parent:
                interests_by_parent[parent] = {'parent_context': None, 'children': []}
            
            if interest['child_interest']:
                interests_by_parent[parent]['children'].append({
                    'child': interest['child_interest'],
                    'context': interest['context']
                })
            else:
                interests_by_parent[parent]['parent_context'] = interest['context']
        
        # Format for clear parent-child relationships
        interests_text = []
        for parent, data in interests_by_parent.items():
            if data['parent_context']:
                interests_text.append(f"**{parent}** (general interest: {data['parent_context']})")
            else:
                interests_text.append(f"**{parent}**:")
            
            for child_data in data['children']:
                interests_text.append(f"  - {parent} → {child_data['child']} ({child_data['context']})")
            
            interests_text.append("")  # Add blank line between categories
        
        interests_formatted = "\n".join(interests_text)
        
        # Get existing contexts to avoid duplicates
        existing_contexts_result = supabase.table('personalized_contexts').select('title, description').eq('user_id', user_id).execute()
        existing_contexts = existing_contexts_result.data if existing_contexts_result.data else []
        
        # Generate contexts using OpenAI
        generated_contexts = await generate_contexts_with_openai(interests_formatted, request.count, existing_contexts)
        
        # Save contexts to database
        contexts_to_insert = []
        import time
        timestamp = int(time.time())
        
        for i, context in enumerate(generated_contexts):
            # Add timestamp and index to ensure unique IDs for Load More functionality
            context_id = f"user_{user_id[:8]}_{context['id_suffix']}_{timestamp}_{i}"
            
            # Extract level-specific phrases from OpenAI response
            level_phrases = context.get('level_phrases', {})
            
            contexts_to_insert.append({
                'id': context_id,
                'user_id': user_id,
                'title': context['title'],
                'description': context['description'],
                'icon': context['icon'],
                'context_instructions': context['context_instructions'],
                'interest_tags': context['interest_tags'],
                'a1_phrases': level_phrases.get('a1', []),
                'a2_phrases': level_phrases.get('a2', []),
                'b1_phrases': level_phrases.get('b1', []),
                'b2_phrases': level_phrases.get('b2', []),
                'c1_phrases': level_phrases.get('c1', []),
                'c2_phrases': level_phrases.get('c2', []),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
        
        if contexts_to_insert:
            result = supabase.table('personalized_contexts').insert(contexts_to_insert).execute()
            
        return {
            'message': f'Successfully generated {len(contexts_to_insert)} personalized contexts',
            'contexts': [
                {
                    'id': ctx['id'],
                    'title': ctx['title'],
                    'description': ctx['description'],
                    'icon': ctx['icon'],
                    'interest_tags': ctx['interest_tags']
                } for ctx in contexts_to_insert
            ],
            'count': len(contexts_to_insert)
        }
        
    except HTTPException:
        raise
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error generating personalized contexts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate contexts: {str(e)}")

async def generate_contexts_with_openai(interests_text: str, count: int, existing_contexts: List[dict] = None) -> List[dict]:
    """Generate personalized conversation contexts with level-specific starter phrases using OpenAI"""
    
    # Format existing contexts for the prompt if provided
    existing_context_text = ""
    if existing_contexts:
        existing_context_text = "\n\nEXISTING CONTEXTS TO AVOID DUPLICATING:\n"
        for ctx in existing_contexts:
            existing_context_text += f"- {ctx.get('title', 'N/A')}: {ctx.get('description', 'N/A')}\n"
        existing_context_text += "\nPlease ensure new contexts are significantly different from these existing ones in theme, setting, and approach.\n"
    
    prompt = f"""
Based on the following user interests, generate EXACTLY {count} engaging conversation contexts for language learning practice:

User Interests:
{interests_text}{existing_context_text}

IMPORTANT: You MUST generate exactly {count} different contexts. Each context should be unique and cover different aspects of the user's interests.

CRITICAL RULES FOR INTEREST COMBINATIONS:
1. Child interests (like "South East Asia", "Italian", etc.) should ONLY be combined with their specific parent category
2. DO NOT mix child interests from one category with parent categories they don't belong to
3. CORRECT EXAMPLES:
   - "Travel → South East Asia" generates travel contexts about Southeast Asia
   - "Cooking & Food → Italian" generates cooking contexts about Italian cuisine
   - "Sports & Fitness → Football" generates sports contexts about football
4. INCORRECT EXAMPLES (DO NOT DO):
   - "Travel → South East Asia" generating business contexts about Southeast Asia
   - "Cooking & Food → Italian" generating travel contexts about Italy
   - Mixing "South East Asia" with unrelated categories like "Technology" or "Business"
5. Each context should focus on ONE coherent interest combination, not multiple unrelated interests
6. Respect the arrow (→) relationships shown in the user interests - they indicate which child belongs to which parent

For each context, create a unique conversation scenario that incorporates their interests. Each context should include:

1. **id_suffix**: A short, descriptive identifier (e.g., "travel_southeast_asia", "cooking_italian")
2. **title**: An engaging title for the context card (e.g., "Planning Your Trip to Southeast Asia")
3. **description**: A brief description of what the conversation will involve
4. **icon**: A single emoji that represents the context
5. **context_instructions**: Detailed roleplay instructions for the AI (similar to restaurant/market contexts)
6. **interest_tags**: Array of relevant interest tags
7. **level_phrases**: Object containing starter phrases for each CEFR level (A1, A2, B1, B2, C1, C2)

LEVEL-SPECIFIC STARTER PHRASES REQUIREMENTS:
For each level, generate exactly 6 phrases in SPANISH:
- 3 starter questions (conversation initiators) 
- 3 interesting conversational phrases (deeper engagement topics that include statements with follow-up questions, opinions with hooks, or invitations to ask back)

IMPORTANT: Conversational phrases should NOT be just questions. They should be statements that naturally invite response, like:
- "Me gusta [topic], ¿a ti también?" / "I like [topic], do you too?"
- "Tengo [experience], ¿qué piensas?" / "I have [experience], what do you think?"
- "[Opinion], pero es difícil, ¿tú qué opinas?" / "[Opinion], but it's hard, what's your opinion?"

CRITICAL TENSE CONSTRAINTS - ENFORCE STRICTLY:
- A1: ONLY present tense (simple present only) - NO past, future, conditional, or subjunctive tenses. Use "tienes", "es", "vives", "te gusta", NOT "has estado", "has ido", "fuiste", "irás"
- A2: Present tense + simple past tense only (preterite/indefinido like "fui", "comí", "hablé")
- B1: Present, past, and simple future tenses
- B2: All major tenses including conditional and subjunctive
- C1: All tenses with complex grammatical structures
- C2: All tenses with advanced nuanced expressions

PHRASE COMPLEXITY SCALING:
- A1: Very simple, basic vocabulary (150-250 words), short sentences (3-5 words max)
- A2: Simple vocabulary (250-500 words), slightly longer sentences (5-8 words)
- B1: Intermediate vocabulary (500-1000 words), more complex structures (8-12 words)
- B2: Advanced vocabulary (1000-2000 words), natural conversation flow (12-18 words)
- C1: Sophisticated vocabulary (2000-4000 words), cultural nuances (15-25 words)
- C2: Native-like complexity (4000+ words), advanced expressions (20-30 words)

CORRECT A1 PHRASE EXAMPLES for a "cycling" context (ONLY present tense) - NOTE: These should be conversational, not just questions:
A1 starter questions: "¿Te gusta montar en bicicleta?", "¿Dónde montas en bicicleta?", "¿Haces ejercicio?"
A1 interesting conversational phrases: "Me gusta montar en bicicleta, ¿a ti también?", "Tengo una bicicleta roja, ¿qué bicicleta tienes?", "Montar en bicicleta es difícil, ¿tú qué piensas?"

INCORRECT A1 EXAMPLES (DO NOT USE - these contain past/perfect tenses):
❌ "¿Has estado en Asia?" (perfect tense - NOT allowed for A1)
❌ "¿Fuiste al parque?" (past tense - NOT allowed for A1)
❌ "¿Has viajado mucho?" (perfect tense - NOT allowed for A1)

C2 advanced examples:
C2 starter questions: "¿Qué opinas sobre el ciclismo como medio de transporte sostenible?", "¿Consideras participar en competiciones de alto rendimiento?", "¿Cómo has evolucionado técnicamente desde que comenzaste?"
C2 interesting phrases: "¿Cuál ha sido tu experiencia más desafiante en ruta?", "¿Qué modificaciones has realizado en tu equipamiento?", "¿Cómo influye la aerodinámica en tu rendimiento?"

The context_instructions should be detailed roleplay guidelines that:
- Create an immersive scenario related to their interests
- Provide specific character backgrounds and settings
- Include variation instructions for different conversations
- Encourage natural language practice while staying in character
- Provide examples of conversation starters and interactions

Format as JSON object with an "contexts" array:
{{
  "contexts": [
    {{
      "id_suffix": "...",
      "title": "...",
      "description": "...",
      "icon": "...",
      "context_instructions": "...",
      "interest_tags": ["...", "..."],
      "level_phrases": {{
        "a1": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
        "a2": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
        "b1": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
        "b2": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
        "c1": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
        "c2": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"]
      }}
    }}
  ]
}}

Make each context unique, engaging, and directly relevant to their specific interests. Ensure each context stays within the logical boundaries of the interest categories and that all phrases are contextually relevant and follow the tense constraints strictly.
"""

    try:
        logging.info(f"[OPENAI] Generating {count} contexts for interests:\n{interests_text}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.8,
                    "response_format": {"type": "json_object"}
                }
            ) as response:
                logging.info(f"[OPENAI] Response status: {response.status}")
                
                if response.status != 200:
                    response_text = await response.text()
                    logging.error(f"[OPENAI] API error: {response_text}")
                    raise Exception(f"OpenAI API error: {response_text}")
                
                response_data = await response.json()
                result = response_data["choices"][0]["message"]["content"]
                logging.info(f"[OPENAI] Raw response: {result[:200]}...")
                
                # Parse JSON response
                import json
                contexts_data = json.loads(result)
                logging.info(f"[OPENAI] Parsed data type: {type(contexts_data)}")
                logging.info(f"[OPENAI] Parsed data keys: {list(contexts_data.keys()) if isinstance(contexts_data, dict) else 'Not a dict'}")
                
                # If the response is wrapped in an object with a key, extract the array
                if isinstance(contexts_data, dict):
                    if "contexts" in contexts_data:
                        contexts_data = contexts_data["contexts"]
                        logging.info(f"[OPENAI] Extracted contexts array with {len(contexts_data)} items")
                    elif len(contexts_data) == 1:
                        key = list(contexts_data.keys())[0]
                        if isinstance(contexts_data[key], list):
                            contexts_data = contexts_data[key]
                            logging.info(f"[OPENAI] Extracted array from key '{key}' with {len(contexts_data)} items")
                
                if not isinstance(contexts_data, list):
                    logging.error(f"[OPENAI] Expected array, got: {type(contexts_data)}")
                    logging.error(f"[OPENAI] Full response data: {contexts_data}")
                    raise Exception(f"Expected array of contexts from OpenAI, got {type(contexts_data)}")
                
                # Validate that we got the expected number of contexts
                if len(contexts_data) != count:
                    logging.warning(f"[OPENAI] Expected {count} contexts but got {len(contexts_data)}")
                
                # Validate each context has required fields
                for i, context in enumerate(contexts_data):
                    required_fields = ['id_suffix', 'title', 'description', 'icon', 'context_instructions', 'interest_tags', 'level_phrases']
                    missing_fields = [field for field in required_fields if field not in context]
                    if missing_fields:
                        logging.error(f"[OPENAI] Context {i} missing fields: {missing_fields}")
                    
                    # Validate level_phrases structure
                    if 'level_phrases' in context:
                        expected_levels = ['a1', 'a2', 'b1', 'b2', 'c1', 'c2']
                        level_phrases = context['level_phrases']
                        if isinstance(level_phrases, dict):
                            for level in expected_levels:
                                if level not in level_phrases:
                                    logging.error(f"[OPENAI] Context {i} missing level '{level}' in level_phrases")
                                elif not isinstance(level_phrases[level], list) or len(level_phrases[level]) != 6:
                                    logging.error(f"[OPENAI] Context {i} level '{level}' should have exactly 6 phrases, got {len(level_phrases[level]) if isinstance(level_phrases[level], list) else 'not a list'}")
                        else:
                            logging.error(f"[OPENAI] Context {i} level_phrases is not a dict: {type(level_phrases)}")
                    
                logging.info(f"[OPENAI] Successfully generated {len(contexts_data)} contexts")
                return contexts_data
                
    except Exception as e:
        logging.error(f"[OPENAI] Error generating contexts: {e}", exc_info=True)
        raise Exception(f"Failed to generate contexts: {str(e)}")

# Update the context instructions function to handle personalized contexts
def get_context_specific_instructions_extended(context: str, language: str, user_id: str = None) -> str:
    """Generate context-specific instructions for the AI, including personalized contexts"""
    
    # First check if it's a personalized context
    if context.startswith('user_') and user_id:
        try:
            result = supabase.table('personalized_contexts').select('context_instructions').eq('id', context).eq('user_id', user_id).execute()
            if result.data:
                return result.data[0]['context_instructions']
            else:
                logging.warning(f"Personalized context {context} not found for user {user_id}, falling back to default")
        except Exception as e:
            logging.error(f"Error fetching personalized context instructions: {e}")
    
    # Fall back to original context instructions
    return get_context_specific_instructions(context, language)

async def generate_contexts_for_new_interests(user_id: str):
    """Background task to generate personalized contexts when user saves interests"""
    try:
        # Mark generation as in progress
        context_generation_status[user_id] = True
        logging.info(f"[BACKGROUND] Starting context generation for user {user_id}")
        
        # Clear existing personalized contexts first to ensure fresh content
        logging.info(f"[BACKGROUND] Clearing existing contexts for user {user_id}")
        delete_result = supabase.table('personalized_contexts').delete().eq('user_id', user_id).execute()
        deleted_count = len(delete_result.data) if delete_result.data else 0
        logging.info(f"[BACKGROUND] Deleted {deleted_count} existing contexts")
        
        # Get user interests
        interests_result = supabase.table('user_interests').select('*').eq('user_id', user_id).execute()
        logging.info(f"[BACKGROUND] Found {len(interests_result.data)} interests for user {user_id}")
        
        if not interests_result.data:
            logging.warning(f"[BACKGROUND] No interests found for user {user_id}, contexts cleared but none generated")
            # Mark generation as complete
            context_generation_status[user_id] = False
            return
        
        # Format interests for prompt - group by parent category to make relationships clear
        interests_by_parent = {}
        for interest in interests_result.data:
            parent = interest['parent_interest']
            if parent not in interests_by_parent:
                interests_by_parent[parent] = {'parent_context': None, 'children': []}
            
            if interest['child_interest']:
                interests_by_parent[parent]['children'].append({
                    'child': interest['child_interest'],
                    'context': interest['context']
                })
            else:
                interests_by_parent[parent]['parent_context'] = interest['context']
        
        # Format for clear parent-child relationships
        interests_text = []
        for parent, data in interests_by_parent.items():
            if data['parent_context']:
                interests_text.append(f"**{parent}** (general interest: {data['parent_context']})")
            else:
                interests_text.append(f"**{parent}**:")
            
            for child_data in data['children']:
                interests_text.append(f"  - {parent} → {child_data['child']} ({child_data['context']})")
            
            interests_text.append("")  # Add blank line between categories
        
        interests_formatted = "\n".join(interests_text)
        logging.info(f"[BACKGROUND] Formatted interests:\n{interests_formatted}")
        
        # Generate 6 initial contexts
        logging.info(f"[BACKGROUND] Calling OpenAI to generate contexts...")
        generated_contexts = await generate_contexts_with_openai(interests_formatted, 6)
        logging.info(f"[BACKGROUND] OpenAI returned {len(generated_contexts)} contexts")
        
        # Save contexts to database
        contexts_to_insert = []
        for context in generated_contexts:
            context_id = f"user_{user_id[:8]}_{context['id_suffix']}"
            
            # Extract level-specific phrases from OpenAI response
            level_phrases = context.get('level_phrases', {})
            
            contexts_to_insert.append({
                'id': context_id,
                'user_id': user_id,
                'title': context['title'],
                'description': context['description'],
                'icon': context['icon'],
                'context_instructions': context['context_instructions'],
                'interest_tags': context['interest_tags'],
                'a1_phrases': level_phrases.get('a1', []),
                'a2_phrases': level_phrases.get('a2', []),
                'b1_phrases': level_phrases.get('b1', []),
                'b2_phrases': level_phrases.get('b2', []),
                'c1_phrases': level_phrases.get('c1', []),
                'c2_phrases': level_phrases.get('c2', []),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
        
        if contexts_to_insert:
            logging.info(f"[BACKGROUND] Inserting {len(contexts_to_insert)} contexts to database...")
            result = supabase.table('personalized_contexts').insert(contexts_to_insert).execute()
            logging.info(f"[BACKGROUND] Successfully saved {len(result.data)} contexts for user {user_id}")
        else:
            logging.warning(f"[BACKGROUND] No contexts to insert for user {user_id}")
        
    except Exception as e:
        logging.error(f"[BACKGROUND] Error generating contexts for user {user_id}: {e}", exc_info=True)
    finally:
        # Mark generation as complete
        context_generation_status[user_id] = False
        logging.info(f"[BACKGROUND] Context generation completed for user {user_id}")

async def generate_phrases_for_existing_context(context_id: str, context_data: dict, language: str = "es") -> dict:
    """Generate level-specific phrases for an existing context"""
    try:
        # Create a focused prompt for generating just the phrases
        context_title = context_data.get('title', 'Unknown Context')
        context_description = context_data.get('description', '')
        context_instructions = context_data.get('context_instructions', '')
        
        # Extract key themes from the context for better phrase generation
        context_summary = f"Context: {context_title}\nDescription: {context_description}\nScenario: {context_instructions[:200]}..."
        
        prompt = f"""
Generate level-specific conversation starter phrases for this language learning context:

{context_summary}

Generate exactly 6 phrases in {LANGUAGES.get(language, 'Spanish')} for each CEFR level (A1-C2):
- 3 starter questions (conversation initiators)
- 3 interesting conversational phrases (deeper engagement topics that include statements with follow-up questions, opinions with hooks, or invitations to ask back)

IMPORTANT: Conversational phrases should NOT be just questions. They should be statements that naturally invite response, like:
- "Me gusta [topic], ¿a ti también?" / "I like [topic], do you too?"
- "Tengo [experience], ¿qué piensas?" / "I have [experience], what do you think?"
- "[Opinion], pero es difícil, ¿tú qué opinas?" / "[Opinion], but it's hard, what's your opinion?"

CRITICAL TENSE CONSTRAINTS - ENFORCE STRICTLY:
- A1: ONLY present tense (simple present only) - NO past, future, conditional, or subjunctive tenses. Use "tienes", "es", "vives", "te gusta", NOT "has estado", "has ido", "fuiste", "irás"
- A2: Present tense + simple past tense only (preterite/indefinido like "fui", "comí", "hablé")
- B1: Present, past, and simple future tenses
- B2: All major tenses including conditional and subjunctive
- C1: All tenses with complex grammatical structures
- C2: All tenses with advanced nuanced expressions

PHRASE COMPLEXITY SCALING:
- A1: Very simple, basic vocabulary (150-250 words), short sentences (3-5 words max)
- A2: Simple vocabulary (250-500 words), slightly longer sentences (5-8 words)
- B1: Intermediate vocabulary (500-1000 words), more complex structures (8-12 words)
- B2: Advanced vocabulary (1000-2000 words), natural conversation flow (12-18 words)
- C1: Sophisticated vocabulary (2000-4000 words), cultural nuances (15-25 words)
- C2: Native-like complexity (4000+ words), advanced expressions (20-30 words)

CORRECT A1 EXAMPLES (ONLY present tense):
✅ "¿Te gusta esto?" / "¿Dónde vives?" / "¿Qué tienes?"

INCORRECT A1 EXAMPLES (DO NOT USE):
❌ "¿Has estado aquí?" (perfect tense)
❌ "¿Fuiste ayer?" (past tense)
❌ "¿Irás mañana?" (future tense)

All phrases must be directly relevant to this specific context theme. Ensure tense constraints are strictly followed.

Format as JSON:
{{
  "level_phrases": {{
    "a1": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
    "a2": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
    "b1": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
    "b2": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
    "c1": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"],
    "c2": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5", "phrase6"]
  }}
}}
"""

        logging.info(f"[PHRASES] Generating phrases for context {context_id}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"}
                }
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logging.error(f"[PHRASES] OpenAI API error: {response_text}")
                    raise Exception(f"OpenAI API error: {response_text}")
                
                response_data = await response.json()
                result = response_data["choices"][0]["message"]["content"]
                
                # Parse JSON response
                import json
                phrases_data = json.loads(result)
                
                if "level_phrases" in phrases_data:
                    return phrases_data["level_phrases"]
                else:
                    logging.error(f"[PHRASES] Invalid response format for context {context_id}")
                    return {}
                
    except Exception as e:
        logging.error(f"[PHRASES] Error generating phrases for context {context_id}: {e}")
        return {}

async def populate_phrases_for_existing_contexts(user_id: str = None, language: str = "es"):
    """Populate level-specific phrases for existing contexts that don't have them"""
    try:
        logging.info(f"[POPULATE] Starting phrase population for existing contexts (user: {user_id})")
        
        # Build query based on whether user_id is provided
        query = supabase.table('personalized_contexts').select('*')
        
        if user_id:
            query = query.eq('user_id', user_id)
        
        # Find contexts that don't have phrases populated
        result = query.execute()
        
        contexts_to_update = []
        for context in result.data:
            # Check if any level phrases are missing or empty
            needs_phrases = (
                not context.get('a1_phrases') or
                not context.get('a2_phrases') or
                not context.get('b1_phrases') or
                not context.get('b2_phrases') or
                not context.get('c1_phrases') or
                not context.get('c2_phrases')
            )
            
            if needs_phrases:
                contexts_to_update.append(context)
        
        logging.info(f"[POPULATE] Found {len(contexts_to_update)} contexts needing phrase generation")
        
        # Generate phrases for each context
        for context in contexts_to_update:
            context_id = context['id']
            logging.info(f"[POPULATE] Generating phrases for context {context_id}")
            
            # Generate the phrases
            level_phrases = await generate_phrases_for_existing_context(context_id, context, language)
            
            if level_phrases:
                # Update the context in the database
                update_data = {
                    'a1_phrases': level_phrases.get('a1', []),
                    'a2_phrases': level_phrases.get('a2', []),
                    'b1_phrases': level_phrases.get('b1', []),
                    'b2_phrases': level_phrases.get('b2', []),
                    'c1_phrases': level_phrases.get('c1', []),
                    'c2_phrases': level_phrases.get('c2', []),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                
                supabase.table('personalized_contexts').update(update_data).eq('id', context_id).execute()
                logging.info(f"[POPULATE] Successfully updated phrases for context {context_id}")
            else:
                logging.warning(f"[POPULATE] Failed to generate phrases for context {context_id}")
        
        logging.info(f"[POPULATE] Completed phrase population for {len(contexts_to_update)} contexts")
        return len(contexts_to_update)
        
    except Exception as e:
        logging.error(f"[POPULATE] Error populating phrases: {e}", exc_info=True)
        return 0

# Add a simple in-memory store to track context generation status
context_generation_status = {}

@app.get("/api/personalized_contexts/status")
async def get_context_generation_status(token: str = Query(...)):
    """Check if contexts are currently being generated for the user"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        # Check if generation is in progress
        is_generating = context_generation_status.get(user_id, False)
        
        return {
            'is_generating': is_generating,
            'user_id': user_id
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error checking context generation status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")

@app.post("/api/personalized_contexts/populate_phrases")
async def populate_context_phrases(
    language: str = Query(default="es", description="Language code (e.g., 'es', 'fr', 'de')"),
    token: str = Query(...)
):
    """Populate level-specific phrases for existing contexts that don't have them"""
    try:
        # Verify JWT token and get user ID
        payload = verify_jwt(token)
        user_id = payload.get("sub") or payload.get("user_id")
        
        logging.info(f"[API] Phrase population requested by user {user_id} for language {language}")
        
        # Run the population function
        updated_count = await populate_phrases_for_existing_contexts(user_id, language)
        
        return {
            'success': True,
            'updated_contexts': updated_count,
            'message': f"Successfully populated phrases for {updated_count} contexts"
        }
        
    except jwt.InvalidTokenError as e:
        logging.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logging.error(f"Error populating context phrases: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to populate phrases: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 