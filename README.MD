# OpenAI Realtime API Demo

This is a Python application that demonstrates the use of OpenAI's Realtime API for voice conversations. The application allows for real-time voice interaction with an AI assistant, with features like:

- Real-time voice input and output
- Conversation history tracking
- Function calling capabilities
- Automatic feedback loop prevention

## Setup

1. Create a virtual environment:
```bash
python3 -m venv venv
```

2. Activate the virtual environment:
```bash
source venv/bin/activate  # On macOS/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Running the Application

1. Make sure your virtual environment is activated
2. Run the application:
```bash
python realtime.py
```

## Features

- Real-time voice conversation with AI
- Automatic transcription of both user and AI speech
- Conversation history tracking
- Function calling support (weather, notepad)
- Feedback loop prevention during AI speech

## Requirements

- Python 3.9+
- PyAudio
- WebSocket client
- PySocks
- OpenAI API key

- **Initialize Audio Interface**

  - Use `pyaudio.PyAudio()` to create the `p` audio interface, managing both microphone and speaker audio streams.

  **Configure Microphone and Speaker Streams**

  - Configure 

    ```
    mic_stream
    ```

     for microphone input and 

    ```
    speaker_stream
    ```

     for speaker output:

    - `mic_stream` uses `mic_callback` to capture audio frames, placing each frame in the `mic_queue` for later transmission over WebSocket.
    - `speaker_stream` uses `speaker_callback` to retrieve audio data from `audio_buffer` for playback, handling timing and buffering of audio frames.

  **Start Audio Streams**

  - Start audio capture and playback by calling `mic_stream.start_stream()` and `speaker_stream.start_stream()`.

  **Establish WebSocket Connection**

  - The 

    ```
    connect_to_openai()
    ```

     function initiates a WebSocket connection with OpenAI's API for real-time data exchange. This function spawns two threads:

    - **Send Microphone Audio**: `send_mic_audio_to_websocket` pulls audio data from `mic_queue`, encodes it in base64, and sends it via WebSocket in the `input_audio_buffer.append` format.
    - **Receive Audio and Responses**: `receive_audio_from_websocket` listens for WebSocket messages from OpenAI, handling responses based on message `type`.

  **Handle WebSocket Events and Message Types**

  - In `receive_audio_from_websocket`, the following message types are processed:
    - **`session.created`**: Indicates a successful session creation. This triggers `send_fc_session_update()` to configure session parameters, such as transcription and voice activity detection (VAD) settings.
    - **`input_audio_buffer.speech_started`**: Indicates that the AI has detected speech in the audio input. This triggers:
      - `clear_audio_buffer()` to remove any existing data in `audio_buffer`.
      - `stop_audio_playback()` to halt the speaker stream, ensuring only new audio data is played.
    - **`response.audio.delta`**: Contains audio data in the `delta` field, encoded in base64. This data is decoded and appended to `audio_buffer`, where `speaker_callback` can access it for real-time playback.
    - **`response.audio.done`**: Marks the end of the AI's audio response, signaling that no further audio data for the current response will be received.
    - **`response.function_call_arguments.done`**: Indicates the AI's request for a function call. The `handle_function_call` function decodes the request arguments, performs the specified action (such as `