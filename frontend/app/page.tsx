'use client';

import { useEffect, useState, useRef } from 'react';

export default function Home() {
  const [backendStatus, setBackendStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const [openaiStatus, setOpenaiStatus] = useState<'disconnected' | 'connected'>('disconnected');
  const [messages, setMessages] = useState<string[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [assistantResponse, setAssistantResponse] = useState('');

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioBufferRef = useRef<Int16Array[]>([]);
  const isPlayingRef = useRef(false);

  // Initialize AudioContext
  const initAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
    }
  };

  // Function to play next chunk in buffer
  const playNextChunk = async () => {
    if (isPlayingRef.current || audioBufferRef.current.length === 0) return;

    isPlayingRef.current = true;
    const audioData = audioBufferRef.current.shift();

    if (!audioData || !audioContextRef.current) {
      isPlayingRef.current = false;
      return;
    }

    try {
      // Convert Int16Array to Float32Array
      const float32Data = new Float32Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        float32Data[i] = audioData[i] / 32768.0;
      }

      // Create audio buffer
      const audioBuffer = audioContextRef.current.createBuffer(1, float32Data.length, 24000);
      audioBuffer.getChannelData(0).set(float32Data);

      // Create source and play
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);

      // Set up the onended handler before starting
      source.onended = () => {
        isPlayingRef.current = false;
        // Play next chunk if available
        if (audioBufferRef.current.length > 0) {
          playNextChunk();
        }
      };

      // Start playback
      source.start();
    } catch (error) {
      console.error('Error playing audio chunk:', error);
      isPlayingRef.current = false;
      // Try to play next chunk if this one failed
      if (audioBufferRef.current.length > 0) {
        playNextChunk();
      }
    }
  };

  useEffect(() => {
    // Initialize WebSocket connection
    wsRef.current = new WebSocket('ws://localhost:8000/ws');

    wsRef.current.onopen = () => {
      setBackendStatus('connected');
      setMessages(prev => [...prev, 'Connected to backend WebSocket']);
      initAudioContext();
    };

    wsRef.current.onclose = () => {
      setBackendStatus('disconnected');
      setMessages(prev => [...prev, 'Disconnected from backend WebSocket']);
    };

    wsRef.current.onerror = (error) => {
      setBackendStatus('disconnected');
      setMessages(prev => [...prev, `WebSocket error: ${error}`]);
    };

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages(prev => [...prev, `Received: ${JSON.stringify(data)}`]);
      
      // Handle different message types
      switch (data.type) {
        case 'session.created':
          setOpenaiStatus('connected');
          break;
        case 'conversation.item.input_audio_transcription.completed':
          setTranscript(data.transcript);
          break;
        case 'response.audio_transcript.done':
          setAssistantResponse(data.transcript);
          break;
        case 'response.audio.delta':
          // Handle audio data
          try {
            const audioData = atob(data.delta);
            const audioArray = new Int16Array(audioData.length / 2);
            for (let i = 0; i < audioData.length; i += 2) {
              audioArray[i / 2] = (audioData.charCodeAt(i) | (audioData.charCodeAt(i + 1) << 8));
            }
            audioBufferRef.current.push(audioArray);
            playNextChunk();
          } catch (error) {
            console.error('Error processing audio data:', error);
          }
          break;
        case 'error':
          setMessages(prev => [...prev, `Error: ${data.error.message}`]);
          break;
      }
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Create AudioContext with the correct sample rate
      audioContextRef.current = new AudioContext({
        sampleRate: 24000 // OpenAI expects 24kHz
      });

      // Create audio source from the stream
      const source = audioContextRef.current.createMediaStreamSource(stream);
      
      // Create a script processor to handle the audio data
      const processor = audioContextRef.current.createScriptProcessor(1024, 1, 1);
      
      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          // Get the audio data
          const inputData = e.inputBuffer.getChannelData(0);
          
          // Convert Float32Array to Int16Array
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            // Convert float to int16
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          
          // Convert to base64
          const uint8Array = new Uint8Array(pcmData.buffer);
          const base64Audio = btoa(
            Array.from(uint8Array)
              .map(byte => String.fromCharCode(byte))
              .join('')
          );
          
          // Send to backend
          wsRef.current.send(JSON.stringify({
            type: 'input_audio_buffer.append',
            audio: base64Audio
          }));
        }
      };

      // Connect the nodes
      source.connect(processor);
      processor.connect(audioContextRef.current.destination);

      setIsRecording(true);
      setMessages(prev => [...prev, 'Started recording']);
    } catch (error) {
      console.error('Error starting recording:', error);
      setMessages(prev => [...prev, `Error starting recording: ${error}`]);
    }
  };

  const stopRecording = () => {
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setIsRecording(false);
    setMessages(prev => [...prev, 'Stopped recording']);
  };

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-4">Voice Chat Demo</h1>
        
        <div className="space-y-4">
          {/* Connection Status */}
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${
                backendStatus === 'connected' ? 'bg-green-500' : 
                backendStatus === 'connecting' ? 'bg-yellow-500' : 
                'bg-red-500'
              }`} />
              <span>Backend: {backendStatus}</span>
            </div>

            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${
                openaiStatus === 'connected' ? 'bg-green-500' : 'bg-red-500'
              }`} />
              <span>OpenAI: {openaiStatus}</span>
            </div>
          </div>

          {/* Recording Controls */}
          <div className="flex justify-center space-x-4">
            <button
              onClick={isRecording ? stopRecording : startRecording}
              className={`px-4 py-2 rounded-lg ${
                isRecording 
                  ? 'bg-red-500 hover:bg-red-600' 
                  : 'bg-blue-500 hover:bg-blue-600'
              } text-white transition-colors`}
            >
              {isRecording ? 'Stop Recording' : 'Start Recording'}
            </button>
          </div>

          {/* Transcripts */}
          <div className="space-y-4">
            {transcript && (
              <div className="bg-gray-100 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Your Message:</h3>
                <p>{transcript}</p>
              </div>
            )}
            
            {assistantResponse && (
              <div className="bg-blue-100 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Assistant:</h3>
                <p>{assistantResponse}</p>
              </div>
            )}
          </div>

          {/* Debug Messages */}
          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-2">Debug Messages:</h2>
            <div className="bg-gray-100 p-4 rounded-lg h-96 overflow-y-auto">
              {messages.map((msg, index) => (
                <div key={index} className="mb-2 text-sm">
                  {msg}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
} 