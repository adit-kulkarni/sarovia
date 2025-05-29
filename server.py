from fastapi import FastAPI, WebSocket, Query, Body, HTTPException
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

async def handle_openai_response_with_callback(ws: websockets.WebSocketClientProtocol, client_ws: WebSocket, level: str, context: str, language: str, on_openai_session_created):
    """Handle responses from OpenAI, call on_openai_session_created after OpenAI session.created, and forward events to client_ws"""
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
            logging.debug(f"[Handler {handler_id}] Received event: {event_type}")
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
                session_config = {
                    "type": "session.update",
                    "session": {
                        "instructions": get_level_specific_instructions(level, context, language),
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
            logging.info(f"[WebSocket] New connection: connection_id={connection_id}, user_id={user_id}")
        except Exception as e:
            logging.debug(f"[Connection {connection_id}] Authentication failed: {str(e)}")
            await websocket.close(code=4001, reason="Invalid authentication token")
            return
            
        # Accept the connection
        await websocket.accept()
        connection_established = True
        logging.debug(f"[Connection {connection_id}] Websocket connection established")
        
        # Get the level, context, language, and curriculum_id from the client's initial message
        try:
            initial_data = await websocket.receive_json()
            level = initial_data.get('level', 'A1')
            context = initial_data.get('context', 'restaurant')
            language = initial_data.get('language', 'en')
            curriculum_id = initial_data.get('curriculum_id')
            if not curriculum_id:
                raise ValueError("curriculum_id is required to start a conversation")
            logging.debug(f"[Connection {connection_id}] Received initial data: level={level}, context={context}, language={language}, curriculum_id={curriculum_id}")
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
            
        logging.debug(f"[Connection {connection_id}] Successfully connected to OpenAI")
        
        # Create callback for when OpenAI session is created
        async def on_openai_session_created():
            nonlocal conversation_id
            conversation_id = await create_conversation(user_id, context, language, level, curriculum_id)
            logging.debug(f"[Connection {connection_id}] Created new conversation: {conversation_id}")
            
            # Send conversation.created to frontend
            await websocket.send_json({
                "type": "conversation.created",
                "conversation": {
                    "conversation_id": conversation_id,
                    "level": level,
                    "context": context,
                    "language": language,
                    "curriculum_id": curriculum_id
                }
            })
            return conversation_id
        
        # Start handling OpenAI responses
        openai_handler = asyncio.create_task(
            handle_openai_response_with_callback(
                openai_ws, websocket, level, context, language, on_openai_session_created
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
            logging.debug(f"[Connection {connection_id}] Cleaning up handler and closing OpenAI connection")
            openai_handler.cancel()
            await openai_ws.close()
            
    except Exception as e:
        logging.error(f"[Connection {connection_id}] Unexpected error: {e}")
    finally:
        if connection_established:
            try:
                logging.debug(f"[Connection {connection_id}] Closing websocket connection")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 