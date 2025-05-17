from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import json
import base64
import asyncio
import websockets
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
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
            f"You are a {LANGUAGES[language]} restaurant server. Your role is to:\n"
            "- Take orders and make recommendations\n"
            "- Handle special requests and dietary restrictions\n"
            "- Maintain a friendly and professional demeanor\n"
            "- Keep the conversation flowing naturally\n"
            "- Ask about preferences and satisfaction\n"
            "- Suggest dishes and drinks when appropriate"
        ),
        "drinks": (
            f"You are a potential date at a {LANGUAGES[language]} bar. Your role is to:\n"
            "- Show interest in the conversation\n"
            "- Respond to advances appropriately\n"
            "- Share your interests and experiences\n"
            "- Maintain appropriate boundaries\n"
            "- Keep the conversation engaging\n"
            "- Suggest activities or topics to discuss"
        ),
        "introduction": (
            f"You are a new acquaintance in {LANGUAGES[language]}. Your role is to:\n"
            "- Be friendly and approachable\n"
            "- Share basic information about yourself\n"
            "- Show interest in the other person\n"
            "- Find common interests\n"
            "- Keep the conversation light and engaging\n"
            "- Ask relevant follow-up questions"
        ),
        "market": (
            f"You are a {LANGUAGES[language]} market vendor. Your role is to:\n"
            "- Describe your products and their qualities\n"
            "- Negotiate prices appropriately\n"
            "- Maintain a business relationship\n"
            "- Keep the conversation professional but friendly\n"
            "- Offer alternatives when needed\n"
            "- Explain the value of your products"
        ),
        "karaoke": (
            f"You are a friend at a {LANGUAGES[language]} karaoke night. Your role is to:\n"
            "- Encourage participation\n"
            "- Share enthusiasm for music\n"
            "- Maintain a fun atmosphere\n"
            "- Suggest songs and activities\n"
            "- Keep the energy high\n"
            "- Share experiences and preferences"
        ),
        "city": (
            f"You are a local resident/tour guide in a {LANGUAGES[language]} city. Your role is to:\n"
            "- Share knowledge about the city\n"
            "- Make personalized recommendations\n"
            "- Consider the visitor's interests\n"
            "- Keep the conversation informative and engaging\n"
            "- Suggest activities and attractions\n"
            "- Share local insights and tips"
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

async def handle_openai_response(ws: websockets.WebSocketClientProtocol, client_ws: WebSocket, level: str, context: str, language: str):
    """Handle responses from OpenAI and forward to client"""
    try:
        while True:
            message = await ws.recv()
            if not message:
                break

            # Parse the message
            data = json.loads(message)
            event_type = data.get('type')

            # Forward the message to the client
            await client_ws.send_json(data)

            # Handle specific events
            if event_type == 'session.created':
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

    except Exception as e:
        print(f"Error handling OpenAI response: {e}")
    finally:
        await ws.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Get the level, context, and language from the client's initial message
    try:
        initial_data = await websocket.receive_json()
        level = initial_data.get('level', 'A1')  # Default to A1 if not specified
        context = initial_data.get('context', 'restaurant')  # Default to restaurant if not specified
        language = initial_data.get('language', 'en')  # Default to English if not specified
    except:
        level = 'A1'  # Default to A1 if there's any error
        context = 'restaurant'  # Default to restaurant if there's any error
        language = 'en'  # Default to English if there's any error
    
    # Connect to OpenAI
    openai_ws = await connect_to_openai()
    if not openai_ws:
        await websocket.close()
        return

    # Start handling OpenAI responses in a separate task
    openai_handler = asyncio.create_task(handle_openai_response(openai_ws, websocket, level, context, language))

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Forward audio data to OpenAI
            if data.get('type') == 'input_audio_buffer.append':
                await forward_to_openai(openai_ws, data)

    except Exception as e:
        print(f"Error in websocket connection: {e}")
    finally:
        openai_handler.cancel()
        await openai_ws.close()
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 