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
from datetime import datetime

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

WS_URL = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17'

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

async def process_feedback_background(message_id: str, language: str, level: str, client_ws: WebSocket):
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
        
        # Prepare the prompt for OpenAI
        prompt = f"""Analyze the following message in {language} for language learning feedback.
        Student Level: {level}
        Context: {conversation['context']}
        
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
                    "category": "grammar|vocabulary|spelling|punctuation|syntax|word choice|register/formality|other",
                    "type": "<specific mistake type>",
                    "error": "<incorrect text>",
                    "correction": "<corrected text>",
                    "explanation": "<clear explanation>",
                    "severity": "minor|moderate|critical",
                    "languageFeatureTags": ["tag1", "tag2"]
                }}
            ]
        }}
        
        Categories and types must be from the predefined lists:
        - grammar: verb tense, verb usage, subject-verb agreement, article usage, preposition usage, pluralization, auxiliary verb usage, modal verb usage, pronoun agreement, negation, comparatives/superlatives, conditional structures, passive voice, question formation, other
        - vocabulary: word meaning error, false friend, missing word, extra word, word form, other
        - spelling: common spelling error, homophone confusion, other
        - punctuation: missing punctuation, comma splice, run-on sentence, quotation mark error, other
        - syntax: word order, run-on sentence, fragment/incomplete sentence, other
        - word choice: unnatural phrasing, contextually inappropriate word, idiomatic error, register mismatch, other
        - register/formality: informal in formal context, formal in informal context, other
        
        Important: If the message is perfect for the student's level, return an empty mistakes array.
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

async def handle_openai_response_with_callback(ws, client_ws, level, context, language, on_openai_session_created, custom_instructions=None):
    handler_id = str(uuid.uuid4())[:8]
    response_created = False
    conversation_id = None
    openai_session_confirmed = False
    on_openai_session_created_called = False
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
                    logging.info(f"[Handler {handler_id}] OpenAI session.created confirmed, conversation_id: {conversation_id}")
                else:
                    logging.warning(f"[Handler {handler_id}] Duplicate OpenAI session.created event ignored.")
                # Now send session config and response.create to OpenAI
                instructions_to_send = custom_instructions if custom_instructions else get_level_specific_instructions(level, context, language)
                logging.info(f"[Handler {handler_id}] Sending session.update with instructions:\n{instructions_to_send}")
                session_config = {
                    "type": "session.update",
                    "session": {
                        "instructions": instructions_to_send,
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.5,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 500
                        },
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
            # Save assistant messages (final transcript)
            elif event_type == 'response.audio_transcript.done' and conversation_id:
                transcript = data.get('transcript', '')
                if transcript:
                    asyncio.create_task(save_message(conversation_id, 'assistant', transcript))
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
                                asyncio.create_task(process_feedback_background(message_id, language, level, client_ws))
                                logging.info(f"[WebSocket] Started background feedback generation for message_id={message_id}")
                        except Exception as e:
                            logging.error(f"[WebSocket] Error in save_and_generate_feedback_and_emit: {e}")
                    asyncio.create_task(save_and_generate_feedback_and_emit())
    except Exception as e:
        logging.error(f"[Handler {handler_id}] Error handling OpenAI response: {e}")
    finally:
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
                openai_ws, websocket, level, context, language, on_openai_session_created, custom_instructions
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
        
        # Generate feedback
        await process_feedback_background(
            request.message_id,
            conversation.data[0]['language'],
            conversation.data[0]['level'],
            dummy_ws
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
    # Check if already exists
    existing = supabase.table('user_knowledge').select('id').eq('user_id', user_id).eq('language', language).execute()
    if existing.data:
        return {"error": "Knowledge report already exists. Delete it first if you want to regenerate."}
    # Fetch all user messages for this language
    conversations = supabase.table('conversations').select('id').eq('user_id', user_id).eq('language', language).execute()
    conversation_ids = [c['id'] for c in conversations.data]
    messages = []
    for cid in conversation_ids:
        res = supabase.table('messages').select('content', 'role').eq('conversation_id', cid).eq('role', 'user').order('created_at', desc=False).execute()
        messages.extend([m['content'] for m in res.data if m['role'] == 'user'])
    if not messages:
        return {"error": "No user messages found for this language."}
    # Build prompt
    transcript = "\n".join(messages)
    prompt = f"""
You are a language learning assistant. Analyze the following transcript of a user's {language} messages. For each part of speech, provide a list of unique words the user has used:\n- nouns\n- pronouns\n- adjectives\n- verbs (for each verb, list the lemma, and for each lemma, all tenses and persons used)\n- adverbs\n- prepositions\n- conjunctions\n- articles\n- interjections\n\nOutput ONLY a valid JSON object with this structure, and nothing else (no markdown, no explanation, no code block):\n{{\n  \"nouns\": [\"...\"],\n  \"pronouns\": [\"...\"],\n  \"adjectives\": [\"...\"],\n  \"verbs\": {{\n    \"lemma\": {{\n      \"tense\": [\"person1\", \"person2\", ...],\n      ...\n    }},\n    ...\n  }},\n  \"adverbs\": [\"...\"],\n  \"prepositions\": [\"...\"],\n  \"conjunctions\": [\"...\"],\n  \"articles\": [\"...\"],\n  \"interjections\": [\"...\"]\n}}\n\nHere is the transcript:\n{transcript}\n"""
    # Call OpenAI API (sync for now)
    import aiohttp
    import re
    async def analyze_with_openai(prompt):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4-turbo-preview",
            "messages": [{"role": "system", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1500
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()
                return data["choices"][0]["message"]["content"]
    def extract_json_from_response(text):
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
    result = await analyze_with_openai(prompt)
    parsed = extract_json_from_response(result)
    if parsed is None:
        return {"error": "Failed to parse LLM output as JSON.", "raw": result}
    # Store in DB
    supabase.table('user_knowledge').insert({
        'user_id': user_id,
        'language': language,
        'knowledge_json': parsed
    }).execute()
    return {"knowledge": parsed}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 