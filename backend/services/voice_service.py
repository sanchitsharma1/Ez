import logging
import asyncio
import io
import wave
import json
import httpx
import tempfile
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import base64

import numpy as np
import librosa
import noisereduce as nr
from pydub import AudioSegment
from pydub.utils import which

from core.config import settings
from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# Set ffmpeg path for pydub
AudioSegment.converter = which("ffmpeg")
AudioSegment.ffmpeg = which("ffmpeg")
AudioSegment.ffprobe = which("ffprobe")

class VoiceService:
    """Voice processing service for transcription and synthesis"""
    
    def __init__(self):
        self.faster_whisper_model = None
        self.silero_vad_model = None
        self.elevenlabs_api_key = settings.ELEVENLABS_API_KEY
        self.elevenlabs_base_url = "https://api.elevenlabs.io/v1"
        self.coqui_tts_model = None
        
        # Voice activity detection settings
        self.vad_threshold = 0.5
        self.min_speech_duration = 0.3  # Minimum 300ms of speech
        self.min_silence_duration = 0.5  # Minimum 500ms of silence to stop
        
        # Audio preprocessing settings
        self.target_sample_rate = 16000
        self.noise_reduction_enabled = True
        
    async def initialize(self):
        """Initialize voice processing models"""
        try:
            await self._initialize_faster_whisper()
            await self._initialize_silero_vad()
            # await self._initialize_coqui_tts()
            
            logger.info("Voice service initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing voice service: {e}")
            raise
    
    async def _initialize_faster_whisper(self):
        """Initialize Faster-Whisper for transcription"""
        try:
            # Import here to handle optional dependency
            from faster_whisper import WhisperModel
            
            # Use small model for faster processing, can be configured
            model_size = getattr(settings, 'WHISPER_MODEL_SIZE', 'small')
            device = getattr(settings, 'WHISPER_DEVICE', 'cpu')
            
            self.faster_whisper_model = WhisperModel(
                model_size,
                device=device,
                compute_type="float32" if device == "cpu" else "float16"
            )
            
            logger.info(f"Faster-Whisper model ({model_size}) initialized on {device}")
            
        except ImportError:
            logger.warning("Faster-Whisper not available, transcription will be limited")
            self.faster_whisper_model = None
        except Exception as e:
            logger.error(f"Error initializing Faster-Whisper: {e}")
            self.faster_whisper_model = None
    
    async def _initialize_silero_vad(self):
        """Initialize Silero VAD for voice activity detection"""
        try:
            import torch
            
            # Load Silero VAD model
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            
            self.silero_vad_model = model
            self.vad_utils = utils
            
            logger.info("Silero VAD model initialized")
            
        except Exception as e:
            logger.warning(f"Error initializing Silero VAD: {e}")
            self.silero_vad_model = None
    
    async def _initialize_coqui_tts(self):
        """Initialize Coqui TTS for offline synthesis"""
        try:
            from TTS.api import TTS
            
            # Initialize with a multilingual model
            model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
            self.coqui_tts_model = TTS(model_name)
            
            logger.info("Coqui TTS model initialized")
            
        except ImportError:
            logger.warning("Coqui TTS not available, offline synthesis will be limited")
            self.coqui_tts_model = None
        except Exception as e:
            logger.error(f"Error initializing Coqui TTS: {e}")
            self.coqui_tts_model = None
    
    async def transcribe_audio(
        self,
        audio_data: bytes,
        language: str = "en",
        audio_format: str = "audio/wav"
    ) -> Dict[str, Any]:
        """Transcribe audio to text using Faster-Whisper"""
        try:
            if not self.faster_whisper_model:
                raise ValueError("Faster-Whisper model not initialized")
            
            start_time = datetime.now()
            
            # Preprocess audio
            processed_audio = await self._preprocess_audio(audio_data, audio_format)
            
            # Save to temporary file for Faster-Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(processed_audio)
                temp_file_path = temp_file.name
            
            try:
                # Transcribe with Faster-Whisper
                segments, info = self.faster_whisper_model.transcribe(
                    temp_file_path,
                    language=language,
                    beam_size=5,
                    best_of=5,
                    temperature=0.0,
                    condition_on_previous_text=False,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                
                # Extract transcription and segments
                transcription = ""
                segment_list = []
                
                for segment in segments:
                    transcription += segment.text + " "
                    segment_list.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text.strip(),
                        "confidence": getattr(segment, 'confidence', 0.0)
                    })
                
                processing_time = (datetime.now() - start_time).total_seconds()
                
                # Get audio duration
                duration = await self._get_audio_duration(processed_audio)
                
                return {
                    "text": transcription.strip(),
                    "language": info.language,
                    "confidence": info.language_probability,
                    "duration": duration,
                    "segments": segment_list,
                    "processing_time": processing_time
                }
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise
    
    async def synthesize_elevenlabs(
        self,
        text: str,
        voice_id: str,
        voice_settings: Dict[str, Any]
    ) -> bytes:
        """Synthesize speech using ElevenLabs API"""
        try:
            if not self.elevenlabs_api_key:
                raise ValueError("ElevenLabs API key not configured")
            
            url = f"{self.elevenlabs_base_url}/text-to-speech/{voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            # Default voice settings
            default_settings = {
                "stability": 0.5,
                "similarity_boost": 0.8,
                "style": 0.0,
                "use_speaker_boost": True
            }
            
            # Merge with provided settings
            final_settings = {**default_settings, **voice_settings}
            
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": final_settings
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                return response.content
                
        except httpx.HTTPStatusError as e:
            logger.error(f"ElevenLabs API error: {e.response.text if hasattr(e, 'response') else str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error synthesizing with ElevenLabs: {e}")
            raise
    
    async def synthesize_coqui(
        self,
        text: str,
        voice_id: str = "default",
        language: str = "en"
    ) -> bytes:
        """Synthesize speech using Coqui TTS (offline)"""
        try:
            if not self.coqui_tts_model:
                raise ValueError("Coqui TTS model not initialized")
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file_path = temp_file.name
            
            try:
                # Synthesize to file
                self.coqui_tts_model.tts_to_file(
                    text=text,
                    file_path=temp_file_path,
                    language=language
                )
                
                # Read the generated audio file
                with open(temp_file_path, 'rb') as audio_file:
                    audio_data = audio_file.read()
                
                # Convert to MP3 for consistency
                audio_segment = AudioSegment.from_wav(temp_file_path)
                
                with tempfile.NamedTemporaryFile() as mp3_temp:
                    audio_segment.export(mp3_temp.name, format="mp3", bitrate="128k")
                    mp3_temp.seek(0)
                    mp3_data = mp3_temp.read()
                
                return mp3_data
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"Error synthesizing with Coqui TTS: {e}")
            raise
    
    async def process_audio_stream(
        self,
        audio_chunk: bytes,
        session_id: str,
        is_final: bool = False,
        language: str = "en",
        user_id: str = None
    ) -> Dict[str, Any]:
        """Process streaming audio with VAD"""
        try:
            # Get session data
            session_key = f"voice_session:{session_id}:{user_id}"
            session_data = await redis_client.get(session_key) or {}
            
            # Initialize session if new
            if not session_data:
                session_data = {
                    "audio_buffer": b"",
                    "partial_transcript": "",
                    "speech_detected": False,
                    "last_activity": datetime.utcnow().isoformat(),
                    "total_duration": 0.0
                }
            
            # Add chunk to buffer
            if isinstance(session_data.get("audio_buffer"), str):
                # Convert base64 string back to bytes if stored as string
                existing_buffer = base64.b64decode(session_data["audio_buffer"])
            else:
                existing_buffer = session_data.get("audio_buffer", b"")
            
            combined_audio = existing_buffer + audio_chunk
            
            # Perform VAD on the chunk
            has_speech = await self._detect_voice_activity(audio_chunk)
            
            result = {
                "has_speech": has_speech,
                "partial_text": "",
                "final_text": "",
                "confidence": 0.0,
                "processing_time": 0.0
            }
            
            # Update session state
            session_data["speech_detected"] = has_speech or session_data.get("speech_detected", False)
            session_data["last_activity"] = datetime.utcnow().isoformat()
            
            # Process transcription if speech detected or final
            if has_speech or is_final:
                if len(combined_audio) > 1024:  # Minimum audio size
                    try:
                        # Transcribe the accumulated audio
                        transcription_result = await self.transcribe_audio(
                            audio_data=combined_audio,
                            language=language
                        )
                        
                        if is_final:
                            result["final_text"] = transcription_result["text"]
                            session_data["partial_transcript"] = ""
                        else:
                            result["partial_text"] = transcription_result["text"]
                            session_data["partial_transcript"] = transcription_result["text"]
                        
                        result["confidence"] = transcription_result.get("confidence", 0.0)
                        result["processing_time"] = transcription_result.get("processing_time", 0.0)
                        
                    except Exception as e:
                        logger.warning(f"Error transcribing audio stream: {e}")
                        result["partial_text"] = session_data.get("partial_transcript", "")
            
            # Update buffer (keep manageable size)
            if is_final or len(combined_audio) > 1024 * 1024:  # 1MB max buffer
                session_data["audio_buffer"] = base64.b64encode(audio_chunk).decode()
            else:
                session_data["audio_buffer"] = base64.b64encode(combined_audio).decode()
            
            # Store session data
            await redis_client.set(session_key, session_data, expire=3600)  # 1 hour
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing audio stream: {e}")
            return {
                "has_speech": False,
                "partial_text": "",
                "final_text": "",
                "confidence": 0.0,
                "processing_time": 0.0
            }
    
    async def _detect_voice_activity(self, audio_data: bytes) -> bool:
        """Detect voice activity in audio chunk"""
        try:
            if not self.silero_vad_model:
                # Fallback to simple energy-based detection
                return await self._simple_energy_vad(audio_data)
            
            # Convert audio data to numpy array
            audio_array = await self._audio_bytes_to_array(audio_data)
            
            if len(audio_array) < 512:  # Too short for VAD
                return False
            
            # Resample to 16kHz for Silero VAD
            if len(audio_array) > 0:
                audio_16k = librosa.resample(
                    audio_array,
                    orig_sr=self.target_sample_rate,
                    target_sr=16000
                )
                
                # Run VAD
                import torch
                
                audio_tensor = torch.from_numpy(audio_16k).float()
                
                # Get VAD probability
                speech_prob = self.silero_vad_model(audio_tensor, 16000).item()
                
                return speech_prob > self.vad_threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Error in voice activity detection: {e}")
            return False
    
    async def _simple_energy_vad(self, audio_data: bytes) -> bool:
        """Simple energy-based voice activity detection"""
        try:
            # Convert to numpy array
            audio_array = await self._audio_bytes_to_array(audio_data)
            
            if len(audio_array) == 0:
                return False
            
            # Calculate RMS energy
            rms_energy = np.sqrt(np.mean(audio_array ** 2))
            
            # Simple threshold (this should be calibrated)
            energy_threshold = 0.01
            
            return rms_energy > energy_threshold
            
        except Exception as e:
            logger.error(f"Error in simple energy VAD: {e}")
            return False
    
    async def _preprocess_audio(self, audio_data: bytes, audio_format: str) -> bytes:
        """Preprocess audio data"""
        try:
            # Convert to AudioSegment
            if audio_format.startswith("audio/wav"):
                audio = AudioSegment.from_wav(io.BytesIO(audio_data))
            elif audio_format.startswith("audio/mp3"):
                audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            elif audio_format.startswith("audio/mp4") or audio_format.startswith("audio/m4a"):
                audio = AudioSegment.from_file(io.BytesIO(audio_data), format="mp4")
            else:
                # Try to auto-detect format
                audio = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Convert to mono
            if audio.channels > 1:
                audio = audio.set_channels(1)
            
            # Resample to target sample rate
            if audio.frame_rate != self.target_sample_rate:
                audio = audio.set_frame_rate(self.target_sample_rate)
            
            # Normalize volume
            audio = audio.normalize()
            
            # Apply noise reduction if enabled
            if self.noise_reduction_enabled:
                audio = await self._apply_noise_reduction(audio)
            
            # Export as WAV
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            
            return wav_buffer.read()
            
        except Exception as e:
            logger.error(f"Error preprocessing audio: {e}")
            return audio_data  # Return original if preprocessing fails
    
    async def _apply_noise_reduction(self, audio: AudioSegment) -> AudioSegment:
        """Apply noise reduction to audio"""
        try:
            # Convert to numpy array
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / np.iinfo(audio.array_type).max  # Normalize
            
            # Apply noise reduction
            reduced_noise = nr.reduce_noise(y=samples, sr=audio.frame_rate)
            
            # Convert back to audio segment
            reduced_noise_int = (reduced_noise * np.iinfo(audio.array_type).max).astype(audio.array_type)
            
            return AudioSegment(
                reduced_noise_int.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            
        except Exception as e:
            logger.error(f"Error applying noise reduction: {e}")
            return audio  # Return original if noise reduction fails
    
    async def _audio_bytes_to_array(self, audio_data: bytes) -> np.ndarray:
        """Convert audio bytes to numpy array"""
        try:
            # Try to detect format and convert
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Convert to mono and target sample rate
            if audio.channels > 1:
                audio = audio.set_channels(1)
            
            if audio.frame_rate != self.target_sample_rate:
                audio = audio.set_frame_rate(self.target_sample_rate)
            
            # Convert to numpy array
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / np.iinfo(audio.array_type).max  # Normalize to [-1, 1]
            
            return samples
            
        except Exception as e:
            logger.error(f"Error converting audio to array: {e}")
            return np.array([], dtype=np.float32)
    
    async def _get_audio_duration(self, audio_data: bytes) -> float:
        """Get audio duration in seconds"""
        try:
            audio = AudioSegment.from_wav(io.BytesIO(audio_data))
            return len(audio) / 1000.0  # Convert milliseconds to seconds
            
        except Exception as e:
            logger.error(f"Error getting audio duration: {e}")
            return 0.0
    
    async def get_elevenlabs_voices(self) -> List[Dict[str, Any]]:
        """Get available ElevenLabs voices"""
        try:
            if not self.elevenlabs_api_key:
                return []
            
            url = f"{self.elevenlabs_base_url}/voices"
            headers = {"xi-api-key": self.elevenlabs_api_key}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                return [
                    {
                        "voice_id": voice["voice_id"],
                        "name": voice["name"],
                        "category": voice.get("category", ""),
                        "description": voice.get("description", ""),
                        "use_case": voice.get("use_case", ""),
                        "accent": voice.get("accent", ""),
                        "age": voice.get("age", ""),
                        "gender": voice.get("gender", ""),
                        "preview_url": voice.get("preview_url", "")
                    }
                    for voice in data.get("voices", [])
                ]
                
        except Exception as e:
            logger.error(f"Error getting ElevenLabs voices: {e}")
            return []
    
    async def get_coqui_voices(self) -> List[Dict[str, Any]]:
        """Get available Coqui TTS voices"""
        try:
            if not self.coqui_tts_model:
                return []
            
            # Return available speakers/voices
            voices = [
                {
                    "voice_id": "default",
                    "name": "Default Voice",
                    "language": "en",
                    "gender": "neutral"
                }
            ]
            
            return voices
            
        except Exception as e:
            logger.error(f"Error getting Coqui voices: {e}")
            return []