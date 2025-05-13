import { io } from 'socket.io-client';

class AudioService {
  constructor() {
    this.socket = null;
    this.mediaRecorder = null;
    this.audioContext = null;
    this.audioQueue = [];
    this.isProcessing = false;
  }

  connect() {
    console.log('Attempting to connect to WebSocket server...');
    this.socket = io('http://localhost:5000', {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5
    });

    this.socket.on('connect', () => {
      console.log('✅ Connected to WebSocket server');
    });

    this.socket.on('connect_error', (error) => {
      console.error('❌ WebSocket connection error:', error);
    });

    this.socket.on('disconnect', (reason) => {
      console.log('❌ Disconnected from WebSocket server:', reason);
    });

    this.socket.on('audio', (data) => {
      console.log('🎵 Received audio from server:', data);
      this.handleIncomingAudio(data);
    });

    this.socket.on('transcript', (data) => {
      console.log('📝 Received transcript from server:', data);
      window.dispatchEvent(new CustomEvent('newTranscript', { detail: data }));
    });
  }

  async startRecording(onData) {
    try {
      console.log('🎤 Requesting microphone access...');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('✅ Microphone access granted');
      
      this.mediaRecorder = new MediaRecorder(stream);
      
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          console.log('🎤 Audio data available:', event.data.size, 'bytes');
          onData(event.data);
        }
      };

      this.mediaRecorder.onerror = (error) => {
        console.error('❌ MediaRecorder error:', error);
      };

      this.mediaRecorder.start(100);
      console.log('✅ MediaRecorder started');
    } catch (error) {
      console.error('❌ Error accessing microphone:', error);
      throw error;
    }
  }

  stopRecording() {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      console.log('🛑 Stopping MediaRecorder...');
      this.mediaRecorder.stop();
      this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
      console.log('✅ MediaRecorder stopped');
    }
  }

  async handleIncomingAudio(audioData) {
    try {
      if (!this.audioContext) {
        console.log('🎵 Creating AudioContext...');
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }

      const arrayBuffer = await audioData.arrayBuffer();
      const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
      
      this.audioQueue.push(audioBuffer);
      console.log('🎵 Added audio to queue, current length:', this.audioQueue.length);
      
      if (!this.isProcessing) {
        this.processAudioQueue();
      }
    } catch (error) {
      console.error('❌ Error processing incoming audio:', error);
    }
  }

  async processAudioQueue() {
    if (this.audioQueue.length === 0) {
      this.isProcessing = false;
      return;
    }

    this.isProcessing = true;
    const audioBuffer = this.audioQueue.shift();
    
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);
    
    source.onended = () => {
      console.log('🎵 Finished playing audio chunk');
      this.processAudioQueue();
    };

    console.log('🎵 Playing audio chunk...');
    source.start();
  }

  disconnect() {
    console.log('Disconnecting audio service...');
    if (this.socket) {
      this.socket.disconnect();
    }
    if (this.mediaRecorder) {
      this.stopRecording();
    }
    if (this.audioContext) {
      this.audioContext.close();
    }
    console.log('✅ Audio service disconnected');
  }
}

export const audioService = new AudioService(); 