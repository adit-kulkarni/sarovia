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

def get_level_specific_instructions(level: str) -> str:
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
        "You are a Spanish language tutor. Your primary goal is to help students learn Spanish through natural conversation. "
        "Speak primarily in Spanish, using English only when necessary for explanations. Maintain a patient, encouraging, and supportive tone throughout the conversation.\n\n"
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
        f"Level-specific guidelines: {level_guidelines.get(level, level_guidelines['A1'])}"
    )
    return base_instructions

async def handle_openai_response(ws: websockets.WebSocketClientProtocol, client_ws: WebSocket, level: str):
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
                        "instructions": get_level_specific_instructions(level),
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
                            "model": "whisper-1"
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
    
    # Get the level from the client's initial message
    try:
        initial_data = await websocket.receive_json()
        level = initial_data.get('level', 'A1')  # Default to A1 if not specified
    except:
        level = 'A1'  # Default to A1 if there's any error
    
    # Connect to OpenAI
    openai_ws = await connect_to_openai()
    if not openai_ws:
        await websocket.close()
        return

    # Start handling OpenAI responses in a separate task
    openai_handler = asyncio.create_task(handle_openai_response(openai_ws, websocket, level))

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