from fastapi import FastAPI, WebSocket, Query, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import json
import base64
import asyncio
import websockets
import os
from dotenv import load_dotenv
from supabase import create_client
import os
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import requests
import logging
import uuid
from pydantic import BaseModel
from typing import List, Optional
import aiohttp
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
import httpx
import re
from openai import AsyncOpenAI
import warnings
from supabase import create_client, Client
import numpy as np
from collections import defaultdict, Counter
import spacy

# Import the optimized lesson summary
from optimized_lesson_summary import get_lesson_summary_optimized

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
supabase = create_client(url, key)

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
        logging.warning(f"spaCy model {model_name} not found, falling back to English model")
        if 'en' not in nlp_models:
            nlp_models['en'] = spacy.load('en_core_web_sm')
        nlp_models[language] = nlp_models['en']
        return nlp_models[language]

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
        # Add spelling and punctuation for text interactions
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
    allow_origins=["http://localhost:3000", "https://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        return payload
    except ExpiredSignatureError:
        raise jwt.InvalidTokenError("Token has expired")
    except Exception as e:
        print(f"JWT verification error: {str(e)}")  # Add detailed logging
        raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")

async def connect_to_openai():
    """Establish WebSocket connection with OpenAI"""
    try:
        ws = await websockets.connect(
            WS_URL,
            extra_headers={
                'Authorization': f'Bearer {API_KEY}',
                'OpenAI-Beta': 'realtime=v1'
            }
        )
        return ws
    except Exception as e:
        print(f"Failed to connect to OpenAI: {e}")
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
            f"You are a {LANGUAGES[language]} restaurant server at a specific restaurant. Your role is to:\n"
            "- Start with a specific, authentic greeting (e.g., 'Welcome to Trattoria Bella, how many people do you need a table for?')\n"
            "- Be knowledgeable about your specific restaurant's menu, specialties, and daily specials\n"
            "- Make personalized recommendations based on customer preferences\n"
            "- Handle special requests naturally (e.g., 'We can definitely modify that dish to be gluten-free')\n"
            "- Maintain a friendly but professional demeanor\n"
            "- Keep the conversation flowing naturally while managing your other tables\n\n"
            "Example authentic interactions:\n"
            "- 'Good evening! We have a lovely table by the window available. Would you like to see our wine list?'\n"
            "- 'Our chef's special today is the fresh sea bass with local herbs. It's been very popular.'\n"
            "- 'I notice you're looking at our pasta selection. Our homemade ravioli is made fresh daily.'"
        ),
        "drinks": (
            f"You are at a specific {LANGUAGES[language]} bar or café. Your role is to:\n"
            "- Start with a specific, authentic greeting based on the venue (e.g., 'This is my favorite spot for craft cocktails')\n"
            "- Share genuine interests and experiences related to the venue\n"
            "- Respond naturally to conversation while maintaining appropriate boundaries\n"
            "- Show personality while being respectful\n"
            "- Keep the conversation engaging and authentic\n\n"
            "Example authentic interactions:\n"
            "- 'I come here every Thursday for their live jazz night. The atmosphere is amazing.'\n"
            "- 'Have you tried their signature cocktail? The bartender makes it with local ingredients.'\n"
            "- 'I'm actually here celebrating my friend's art exhibition opening next door.'"
        ),
        "introduction": (
            f"You are meeting someone new in a specific {LANGUAGES[language]} setting. Your role is to:\n"
            "- Start with a context-appropriate introduction (e.g., 'I'm here for the photography workshop too')\n"
            "- Share specific, genuine details about yourself and your interests\n"
            "- Show interest in the other person's background and experiences\n"
            "- Find natural connection points in the conversation\n"
            "- Keep the conversation light but meaningful\n\n"
            "Example authentic interactions:\n"
            "- 'I noticed you're reading that book. I actually met the author at a signing last month.'\n"
            "- 'I'm here visiting my sister who just moved to the city. How long have you lived here?'\n"
            "- 'That's an interesting camera you have. Are you into street photography as well?'"
        ),
        "market": (
            f"You are a vendor at a specific {LANGUAGES[language]} market or shop. Your role is to:\n"
            "- Start with a specific, authentic greeting (e.g., 'Welcome to our family's olive oil shop, we've been here for 50 years')\n"
            "- Be knowledgeable about your specific products and their unique qualities\n"
            "- Share personal stories about your products or business\n"
            "- Handle negotiations naturally while maintaining professionalism\n"
            "- Keep the conversation informative but friendly\n\n"
            "Example authentic interactions:\n"
            "- 'These tomatoes are from my cousin's farm in the countryside. They're picked fresh every morning.'\n"
            "- 'Would you like to try our award-winning olive oil? We won first place at the regional fair.'\n"
            "- 'I can give you a better price if you're buying for your restaurant. Are you a chef?'"
        ),
        "karaoke": (
            f"You are at a specific {LANGUAGES[language]} karaoke bar or event. Your role is to:\n"
            "- Start with a specific, authentic greeting (e.g., 'This place has the best sound system in town')\n"
            "- Share genuine enthusiasm for music and the venue\n"
            "- Encourage participation naturally without being pushy\n"
            "- Share personal experiences with specific songs or performances\n"
            "- Keep the energy high but authentic\n\n"
            "Example authentic interactions:\n"
            "- 'I saw you checking out the song list. Do you have a favorite genre to sing?'\n"
            "- 'The crowd here loves 80s hits. I usually go for 'Sweet Caroline' - it gets everyone singing.'\n"
            "- 'Have you been here before? They have this amazing duet section we could try.'"
        ),
        "city": (
            f"You are a local resident or tour guide in a specific {LANGUAGES[language]} city. Your role is to:\n"
            "- Start with a specific, authentic greeting (e.g., 'Welcome to Barcelona! I see you're near the Gothic Quarter')\n"
            "- Share insider knowledge about specific neighborhoods and attractions\n"
            "- Make personalized recommendations based on the visitor's interests\n"
            "- Share local stories and cultural insights\n"
            "- Keep the conversation informative and engaging\n\n"
            "Example authentic interactions:\n"
            "- 'If you're interested in architecture, you should check out the hidden courtyards in the old town.'\n"
            "- 'The best tapas place is actually around the corner. It's where the locals go, not the tourists.'\n"
            "- 'I live in this neighborhood. The Sunday market here is much better than the one in the center.'"
        )
    }
    return context_guidelines.get(context, context_guidelines["restaurant"])

def get_level_specific_instructions(level: str, context: str, language: str) -> str:
    """Generate level-specific instructions for the AI"""
    level_guidelines = {
        "A1": "Use basic vocabulary and present tense only. Speak slowly and clearly. Use simple sentences. Provide frequent English support.",
        "A2": "Introduce past tense and basic compound sentences. Use more vocabulary but keep it simple. Provide moderate English support.",
        "B1": "Use complex structures and introduce subjunctive. Include idiomatic expressions. Provide minimal English support.",
        "B2": "Use advanced grammar and nuanced expressions. Focus on natural conversation flow. Provide English support only when necessary.",
        "C1": "Use native-like complexity and cultural context. Focus on subtle nuances. Provide English support only for complex concepts.",
        "C2": "Use fully native-like complexity. Focus on cultural nuances and advanced expressions. Provide English support only when absolutely necessary."
    }
    
    base_instructions = (
        f"You are a {LANGUAGES[language]} language tutor. Your primary goal is to help students learn {LANGUAGES[language]} through natural conversation. "
        "Speak primarily in the target language, using English only when necessary for explanations. Maintain a patient, encouraging, and supportive tone throughout the conversation.\n\n"
        "When interacting with students:\n"
        "- Identify and correct errors in grammar (verb conjugations, gender agreement), vocabulary (word choice, idioms), pronunciation, and sentence structure\n"
        "- Provide immediate but non-disruptive corrections\n"
        "- Give clear, concise explanations for each correction\n"
        "- Categorize corrections appropriately (grammar, vocabulary, etc.)\n"
        "- Adapt your speech rate and language complexity to match the student's level\n"
        "- Focus on creating a natural, conversational flow while ensuring learning objectives are met\n\n"
        "Remember to:\n"
        "- Be encouraging and supportive\n"
        "- Provide clear explanations\n"
        "- Maintain a balance between correction and conversation flow\n"
        "- Use appropriate examples to illustrate corrections\n\n"
        f"STUDENT LEVEL: {level}\n"
        f"Level-specific guidelines: {level_guidelines.get(level, level_guidelines['A1'])}\n\n"
        f"CONVERSATION CONTEXT:\n{get_context_specific_instructions(context, language)}"
    )
    return base_instructions

async def process_feedback_background(message_id: str, language: str, level: str, client_ws: WebSocket, interaction_type: str = "audio"):
    """Process feedback in the background without blocking the conversation"""
    try:
        # Get the message from the database
        message_result = supabase.table('messages').select('*').eq('id', message_id).execute()
        if not message_result.data:
            logging.error(f"[Background] Message not found: message_id={message_id}")
            return
        
        message = message_result.data[0]
        original_message = message['content']
        
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
        Note: For audio interactions, focus on spoken language patterns and avoid feedback that would only apply to written text.
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
                    "model": "gpt-4-turbo-preview",
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
        
        # Invalidate insights cache since we have new feedback data
        try:
            # Get the conversation/curriculum info to invalidate the right cache
            # First get the message to find the conversation
            message_result = supabase.table('messages') \
                .select('conversation_id') \
                .eq('id', message_id) \
                .execute()
            
            if message_result.data and len(message_result.data) > 0:
                conversation_id = message_result.data[0]['conversation_id']
                
                # Now get the conversation details
                conversation_result = supabase.table('conversations') \
                    .select('user_id, curriculum_id') \
                    .eq('id', conversation_id) \
                    .execute()
                
                if conversation_result.data and len(conversation_result.data) > 0:
                    conv_data = conversation_result.data[0]
                    user_id = conv_data['user_id']
                    curriculum_id = conv_data['curriculum_id']
                    
                    if curriculum_id:  # Only invalidate if we have a curriculum_id
                        await invalidate_insights_cache(user_id, curriculum_id)
                        logging.info(f"[Background] Invalidated insights cache for user {user_id}, curriculum {curriculum_id}")
        except Exception as e:
            logging.error(f"[Background] Error invalidating insights cache: {e}")
            # Don't fail the feedback processing if cache invalidation fails
        
        # Record language feature tags from all mistakes
        all_tags = []
        for mistake in feedback.mistakes:
            if mistake.languageFeatureTags:
                all_tags.extend(mistake.languageFeatureTags)
        
        if all_tags:
            await record_language_tags(all_tags, language)
        
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
            # Forward all events to client for debugging (optional)
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
                # Now send session config and response.create to OpenAI
                instructions_to_send = custom_instructions if custom_instructions else get_level_specific_instructions(level, context, language)
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
                logging.info(f"[Handler {handler_id}] response.create sent. Guard flag set to True.")
            # Save assistant messages (final transcript) and update turn count
            elif event_type == 'response.audio_transcript.done' and conversation_id:
                transcript = data.get('transcript', '')
                if transcript:
                    asyncio.create_task(save_message(conversation_id, 'assistant', transcript))
                    # Only increment turn count if there was a pending user message (complete exchange)
                    if pending_user_message:
                        current_turns += 1
                        asyncio.create_task(update_lesson_progress_turns(conversation_id, current_turns, client_ws))
                        pending_user_message = False  # Reset for next exchange
                        logging.info(f"[Handler {handler_id}] Complete turn exchange: user → AI. Turn count: {current_turns}")
                        
                        # Trigger knowledge update every 5 turns for ongoing analysis
                        if user_id and current_turns % 5 == 0:
                            logging.info(f"[Handler {handler_id}] Triggering knowledge update after {current_turns} turns")
                            asyncio.create_task(update_user_knowledge_incrementally(user_id, language, [conversation_id]))
                    else:
                        logging.info(f"[Handler {handler_id}] AI response without pending user message - no turn increment")
            # Save user messages (transcription) and generate feedback
            elif event_type == 'conversation.item.input_audio_transcription.completed' and conversation_id:
                transcript = data.get('transcript', '')
                if transcript:
                    async def save_and_generate_feedback_and_emit():
                        try:
                            message_result = await save_message(conversation_id, 'user', transcript)
                            if message_result and message_result.data:
                                message_id = message_result.data[0]['id']
                                logging.info(f"[WebSocket] Emitting user message event for message_id={message_id}, transcript={transcript}")
                                await client_ws.send_json({
                                    "type": "conversation.item.input_audio_transcription.completed",
                                    "message_id": message_id,
                                    "transcript": transcript
                                })
                                asyncio.create_task(process_feedback_background(message_id, language, level, client_ws, INTERACTION_MODE))
                                logging.info(f"[WebSocket] Started background feedback generation for message_id={message_id}")
                        except Exception as e:
                            logging.error(f"[WebSocket] Error in save_and_generate_feedback_and_emit: {e}")
                    asyncio.create_task(save_and_generate_feedback_and_emit())
                    pending_user_message = True
                    logging.info(f"[Handler {handler_id}] User message received - pending AI response for turn completion")
    except Exception as e:
        logging.error(f"[Handler {handler_id}] Error handling OpenAI response: {e}")
    finally:
        # Final knowledge update when conversation ends
        if user_id and conversation_id and current_turns > 0:
            logging.info(f"[Handler {handler_id}] Triggering final knowledge update for conversation {conversation_id}")
            asyncio.create_task(update_user_knowledge_incrementally(user_id, language, [conversation_id]))
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
        logging.debug(f"[save_message] conversation_id={conversation_id}, role={role}, content={content}")
        result = supabase.table('messages').insert({
            'conversation_id': conversation_id,
            'role': role,
            'content': content
        }).execute()
        logging.debug(f"[save_message] result: {result}")
        return result
    except Exception as e:
        logging.error(f"Error saving message: {e}")
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
        # Get conversation details to find user_id
        conversation = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
        if not conversation.data:
            return
        
        conv_data = conversation.data[0]
        user_id = conv_data['user_id']
        
        # Get or create progress record
        progress = await get_or_create_lesson_progress(conversation_id, user_id)
        if not progress:
            return
        
        # Update turn count
        supabase.table('lesson_progress').update({
            'turns_completed': turns,
            'updated_at': datetime.now().isoformat()
        }).eq('id', progress['id']).execute()
        
        # Send progress update to client
        can_complete = turns >= progress['required_turns']
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
    try:
        # Verify token before accepting the connection
        try:
            user_payload = verify_jwt(token)
            user_id = user_payload["sub"]
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

async def generate_hint(level: str, context: str, language: str, conversation_history: list) -> str:
    """Generate a conversation hint using OpenAI's chat completions API"""
    try:
        # Get the conversation context and instructions
        instructions = get_level_specific_instructions(level, context, language)
        
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
                    "model": "gpt-4-turbo-preview",
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

class HintRequest(BaseModel):
    conversation_id: str

@app.post("/api/hint")
async def get_hint(
    request: HintRequest,
    token: str = Query(...)
):
    conversation_id = request.conversation_id
    logging.debug(f"[get_hint] Incoming request: conversation_id={conversation_id}, token={token}")
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
        
        # Generate hint
        hint = await generate_hint(
            conversation.data[0]['level'],
            conversation.data[0]['context'],
            conversation.data[0]['language'],
            messages.data
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
    instructions = get_level_specific_instructions(conversation['level'], conversation['context'], conversation['language'])
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
                "model": "gpt-4-turbo-preview",
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
    
    # Create custom instructions for this lesson
    base_instructions = f"""
You are a {language} teacher conducting a custom lesson designed to address the student's specific weaknesses.

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

IMPORTANT INSTRUCTIONS:
- Focus specifically on the targeted weakness areas mentioned above
- Provide immediate corrections when students make the types of mistakes this lesson addresses
- Be patient and encouraging, as these are areas the student struggles with
- Use examples and exercises that directly relate to their common mistakes
- Speak at the {level} CEFR level with appropriate complexity
- Provide English explanations when needed to clarify difficult concepts
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
        
        # Convert lesson_id to int since lesson_templates uses integer IDs
        try:
            lesson_id_int = int(lesson_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid lesson ID format")
        
        # Get progress for this lesson
        progress = supabase.table('lesson_progress').select('*').eq('user_id', user_id).eq('lesson_id', lesson_id_int).eq('curriculum_id', curriculum_id).execute()
        
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
            return await get_cached_insights_or_generate(user_id, curriculum_id, language, days)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 