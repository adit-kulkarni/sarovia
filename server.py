from fastapi import FastAPI, WebSocket, Query
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
    allow_origins=["*"],  # In production, replace with your frontend URL
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

async def handle_openai_response(ws: websockets.WebSocketClientProtocol, client_ws: WebSocket, level: str, context: str, language: str, conversation_id: str):
    """Handle responses from OpenAI and forward to client"""
    handler_id = str(uuid.uuid4())[:8]
    response_created = False  # Ensure response.create is only sent once
    
    try:
        while True:
            message = await ws.recv()
            if not message:
                break

            # Parse the message
            data = json.loads(message)
            event_type = data.get('type')

            logging.debug(f"[Handler {handler_id}] Received event: {event_type}")

            # Forward the message to the client
            await client_ws.send_json(data)

            # Handle specific events
            if event_type == 'session.created' and not response_created:
                logging.debug(f"[Handler {handler_id}] Received 'session.created' event. Sending session_config and response.create.")
                # Send session configuration
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
                
                # Send response.create to initiate conversation
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
                logging.debug(f"[Handler {handler_id}] response.create sent. Guard flag set to True.")
            
            # Save assistant messages (final transcript)
            elif event_type == 'response.audio_transcript.done' and conversation_id:
                transcript = data.get('transcript', '')
                if transcript:
                    await save_message(conversation_id, 'assistant', transcript)
            # Save user messages (transcription)
            elif event_type == 'conversation.item.input_audio_transcription.completed' and conversation_id:
                transcript = data.get('transcript', '')
                if transcript:
                    await save_message(conversation_id, 'user', transcript)

    except Exception as e:
        logging.error(f"[Handler {handler_id}] Error handling OpenAI response: {e}")
    finally:
        await ws.close()

async def create_conversation(user_id: str, context: str, language: str, level: str) -> str:
    """Create a new conversation and return its ID"""
    try:
        logging.info(f"[create_conversation] user_id={user_id}, context={context}, language={language}, level={level}")
        result = supabase.table('conversations').insert({
            'user_id': user_id,
            'context': context,
            'language': language,
            'level': level
        }).execute()
        logging.info(f"[create_conversation] result: {result}")
        return result.data[0]['id']
    except Exception as e:
        logging.error(f"Error creating conversation: {e}")
        raise

async def save_message(conversation_id: str, role: str, content: str):
    """Save a message to the database"""
    try:
        logging.info(f"[save_message] conversation_id={conversation_id}, role={role}, content={content}")
        result = supabase.table('messages').insert({
            'conversation_id': conversation_id,
            'role': role,
            'content': content
        }).execute()
        logging.info(f"[save_message] result: {result}")
    except Exception as e:
        logging.error(f"Error saving message: {e}")
        raise

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    connection_id = str(uuid.uuid4())[:8]
    connection_established = False
    conversation_id = None
    
    try:
        # Verify token before accepting the connection
        try:
            user_payload = verify_jwt(token)
            user_id = user_payload["sub"]
            logging.debug(f"[Connection {connection_id}] New websocket connection attempt from user {user_id}")
        except Exception as e:
            logging.debug(f"[Connection {connection_id}] Authentication failed: {str(e)}")
            await websocket.close(code=4001, reason="Invalid authentication token")
            return
            
        # Accept the connection
        await websocket.accept()
        connection_established = True
        logging.debug(f"[Connection {connection_id}] Websocket connection established")
        
        # Get the level, context, and language from the client's initial message
        try:
            initial_data = await websocket.receive_json()
            level = initial_data.get('level', 'A1')
            context = initial_data.get('context', 'restaurant')
            language = initial_data.get('language', 'en')
            logging.debug(f"[Connection {connection_id}] Received initial data: level={level}, context={context}, language={language}")
            
            # Create a new conversation
            conversation_id = await create_conversation(user_id, context, language, level)
            logging.debug(f"[Connection {connection_id}] Created new conversation: {conversation_id}")
            
        except Exception as e:
            logging.error(f"[Connection {connection_id}] Error receiving initial data: {e}")
            level = 'A1'
            context = 'restaurant'
            language = 'en'
        
        # Connect to OpenAI
        openai_ws = await connect_to_openai()
        if not openai_ws:
            if connection_established:
                logging.error(f"[Connection {connection_id}] Failed to connect to OpenAI service")
                await websocket.send_json({"error": "Failed to connect to OpenAI service"})
                await websocket.close(code=1011, reason="Failed to connect to OpenAI service")
            return
            
        logging.debug(f"[Connection {connection_id}] Successfully connected to OpenAI, creating handler")
        # Start handling OpenAI responses in a separate task, pass conversation_id
        openai_handler = asyncio.create_task(handle_openai_response(openai_ws, websocket, level, context, language, conversation_id))
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()
                data_type = data.get('type')
                logging.info(f"[websocket_endpoint] ***MESSAGE RECEIVED***: {data_type}, conversation_id: {conversation_id}")
                logging.info(f"[websocket_endpoint] data_type == 'conversation.item.input_audio_transcription.completed': {data_type == 'conversation.item.input_audio_transcription.completed'}")
                logging.info(f"[websocket_endpoint] conversation_id truthy: {bool(conversation_id)}")

                if data_type == 'input_audio_buffer.append':
                    await forward_to_openai(openai_ws, data)
                elif data_type == 'conversation.item.input_audio_transcription.completed' and conversation_id:
                    logging.info(f"[websocket_endpoint] ENTERED transcription block")
                    transcript = data.get('transcript', '')
                    logging.info(f"[websocket_endpoint] transcript: {transcript}")
                    if transcript:
                        try:
                            logging.info(f"[websocket_endpoint] Calling save_message for user transcript")
                            await save_message(conversation_id, 'user', transcript)
                            logging.info(f"[websocket_endpoint] save_message completed for user transcript")
                        except Exception as e:
                            logging.error(f"[websocket_endpoint] Exception in save_message for user transcript: {e}")
                elif data_type == 'user_message' and conversation_id:
                    await save_message(conversation_id, 'user', data.get('content', ''))
                    
        except Exception as e:
            logging.error(f"[Connection {connection_id}] Error in websocket connection: {e}")
        finally:
            logging.info(f"[Connection {connection_id}] Cleaning up handler and closing OpenAI connection")
            openai_handler.cancel()
            await openai_ws.close()
            
    except Exception as e:
        logging.error(f"[Connection {connection_id}] Unexpected error: {e}")
    finally:
        if connection_established:
            try:
                logging.info(f"[Connection {connection_id}] Closing websocket connection")
                await websocket.close()
            except RuntimeError:
                # Ignore "Cannot call send once a close message has been sent" error
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
        result = supabase.table('messages').select('*').eq('conversation_id', conversation_id).order('created_at', asc=True).execute()
        
        return result.data
    except Exception as e:
        logging.error(f"Error getting conversation messages: {e}")
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 