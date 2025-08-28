import { useState, useRef, useCallback, useEffect } from 'react';

interface VoiceOptions {
  continuous?: boolean;
  interimResults?: boolean;
  lang?: string;
}

export function useVoice() {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const synthesisRef = useRef<SpeechSynthesisUtterance | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const vadRef = useRef<any>(null); // Voice Activity Detection
  
  // Voice Activity Detection state
  const [isVoiceDetected, setIsVoiceDetected] = useState(false);
  const silenceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Check for speech recognition support
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const supported = !!(SpeechRecognition && window.speechSynthesis);
    setIsSupported(supported);
    
    if (supported) {
      recognitionRef.current = new SpeechRecognition();
    }
  }, []);

  // Initialize Voice Activity Detection
  const initializeVAD = useCallback(async () => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        }
      });

      mediaStreamRef.current = stream;
      
      const source = audioContextRef.current.createMediaStreamSource(stream);
      const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1);
      
      processor.onaudioprocess = (event) => {
        const inputBuffer = event.inputBuffer.getChannelData(0);
        const volume = calculateVolume(inputBuffer);
        
        // Simple VAD based on volume threshold
        const isVoice = volume > 0.01;
        setIsVoiceDetected(isVoice);
        
        if (isVoice) {
          // Reset silence timeout
          if (silenceTimeoutRef.current) {
            clearTimeout(silenceTimeoutRef.current);
            silenceTimeoutRef.current = null;
          }
        } else {
          // Start silence timeout
          if (!silenceTimeoutRef.current) {
            silenceTimeoutRef.current = setTimeout(() => {
              // Auto-stop listening after 3 seconds of silence
              if (isListening) {
                stopListening();
              }
            }, 3000);
          }
        }
      };
      
      source.connect(processor);
      processor.connect(audioContextRef.current.destination);
      processorRef.current = processor;
      
    } catch (error) {
      console.error('Error initializing VAD:', error);
    }
  }, [isListening]);

  const calculateVolume = (buffer: Float32Array): number => {
    let sum = 0;
    for (let i = 0; i < buffer.length; i++) {
      sum += buffer[i] * buffer[i];
    }
    return Math.sqrt(sum / buffer.length);
  };

  const startListening = useCallback(async (
    onResult: (transcript: string, isFinal: boolean) => void,
    options: VoiceOptions = {}
  ) => {
    if (!isSupported || !recognitionRef.current) {
      console.error('Speech recognition not supported');
      return;
    }

    try {
      // Initialize VAD
      await initializeVAD();

      const recognition = recognitionRef.current;
      
      recognition.continuous = options.continuous ?? true;
      recognition.interimResults = options.interimResults ?? true;
      recognition.lang = options.lang ?? 'en-US';

      recognition.onstart = () => {
        console.log('Speech recognition started');
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }

        // Call the callback with the transcript
        const fullTranscript = finalTranscript || interimTranscript;
        if (fullTranscript.trim()) {
          onResult(fullTranscript, !!finalTranscript);
        }
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        console.log('Speech recognition ended');
        setIsListening(false);
        cleanupVAD();
      };

      recognition.start();
      
    } catch (error) {
      console.error('Error starting speech recognition:', error);
      setIsListening(false);
    }
  }, [isSupported, initializeVAD]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
      cleanupVAD();
    }
  }, [isListening]);

  const cleanupVAD = useCallback(() => {
    // Clean up audio processing
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current);
      silenceTimeoutRef.current = null;
    }
    
    setIsVoiceDetected(false);
  }, []);

  const speak = useCallback(async (
    text: string,
    options: {
      voice?: string;
      rate?: number;
      pitch?: number;
      volume?: number;
      onStart?: () => void;
      onEnd?: () => void;
    } = {}
  ) => {
    if (!window.speechSynthesis) {
      console.error('Speech synthesis not supported');
      return;
    }

    // Stop any existing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    
    // Set voice options
    utterance.rate = options.rate ?? 1;
    utterance.pitch = options.pitch ?? 1;
    utterance.volume = options.volume ?? 1;

    // Find and set the specified voice
    if (options.voice) {
      const voices = window.speechSynthesis.getVoices();
      const selectedVoice = voices.find(voice => 
        voice.name.includes(options.voice!) || voice.lang.includes(options.voice!)
      );
      if (selectedVoice) {
        utterance.voice = selectedVoice;
      }
    }

    utterance.onstart = () => {
      setIsSpeaking(true);
      options.onStart?.();
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      options.onEnd?.();
    };

    utterance.onerror = (event) => {
      console.error('Speech synthesis error:', event.error);
      setIsSpeaking(false);
    };

    synthesisRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  }, []);

  const getAvailableVoices = useCallback(() => {
    return window.speechSynthesis?.getVoices() || [];
  }, []);

  // Enhanced transcription with preprocessing
  const transcribeAudio = useCallback(async (audioBlob: Blob): Promise<string> => {
    try {
      // Convert audio blob to base64
      const base64Audio = await blobToBase64(audioBlob);
      
      // Send to backend for transcription
      const response = await fetch('/api/voice/transcribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify({
          audio_data: base64Audio,
          format: 'wav',
          language: 'en',
        }),
      });

      if (!response.ok) {
        throw new Error(`Transcription failed: ${response.status}`);
      }

      const result = await response.json();
      return result.text || '';
      
    } catch (error) {
      console.error('Error transcribing audio:', error);
      throw error;
    }
  }, []);

  // Enhanced synthesis with agent-specific voices
  const synthesizeWithAgent = useCallback(async (
    text: string,
    agentId: string,
    options: { streaming?: boolean } = {}
  ): Promise<void> => {
    try {
      const response = await fetch('/api/voice/synthesize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify({
          text,
          agent_id: agentId,
          voice_settings: {
            streaming: options.streaming ?? false,
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`Synthesis failed: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.audio_url) {
        // Play the generated audio
        const audio = new Audio(result.audio_url);
        
        audio.onplay = () => setIsSpeaking(true);
        audio.onended = () => setIsSpeaking(false);
        audio.onerror = () => setIsSpeaking(false);
        
        await audio.play();
      }
      
    } catch (error) {
      console.error('Error synthesizing speech:', error);
      // Fallback to browser TTS
      await speak(text);
    }
  }, [speak]);

  // Barge-in functionality
  const enableBargeIn = useCallback(() => {
    if (isListening && isSpeaking) {
      // Stop current speech and continue listening
      stopSpeaking();
    }
  }, [isListening, isSpeaking, stopSpeaking]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopListening();
      stopSpeaking();
      cleanupVAD();
    };
  }, [stopListening, stopSpeaking, cleanupVAD]);

  return {
    // State
    isListening,
    isSpeaking,
    isSupported,
    isVoiceDetected,
    
    // Basic functions
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    getAvailableVoices,
    
    // Advanced functions
    transcribeAudio,
    synthesizeWithAgent,
    enableBargeIn,
  };
}

// Helper functions
function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove data URL prefix
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function getAuthToken(): string {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('auth_token') || '';
  }
  return '';
}

// Type declarations for Speech API
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
    AudioContext: any;
    webkitAudioContext: any;
  }
}