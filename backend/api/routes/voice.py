from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import io
import uuid

from middleware.auth import get_current_active_user
from models.database import User
from models.schemas import VoiceTranscriptionResponse, VoiceSynthesisRequest

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form("en"),
    agent_id: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """Transcribe audio to text using Faster-Whisper"""
    try:
        # Validate audio file
        if not audio_file.content_type or not audio_file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid audio file format"
            )
        
        # Read audio data
        audio_data = await audio_file.read()
        
        if len(audio_data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty audio file"
            )
        
        # Transcribe using voice service
        transcription_result = await transcribe_with_faster_whisper(
            audio_data=audio_data,
            language=language,
            audio_format=audio_file.content_type
        )
        
        # Store transcription in memory if agent specified
        if agent_id and session_id:
            try:
                from main import app
                orchestrator = app.state.orchestrator
                
                if agent_id in orchestrator.agents:
                    agent = orchestrator.agents[agent_id]
                    await agent.store_memory(
                        content=f"Voice input transcribed: {transcription_result['text']}",
                        content_type="voice_transcription",
                        tags=["voice", "transcription", "input"]
                    )
            except Exception as e:
                logger.warning(f"Failed to store transcription in agent memory: {e}")
        
        return VoiceTranscriptionResponse(
            text=transcription_result["text"],
            language=transcription_result.get("language", language),
            confidence=transcription_result.get("confidence", 0.0),
            duration=transcription_result.get("duration", 0.0),
            segments=transcription_result.get("segments", []),
            processing_time=transcription_result.get("processing_time", 0.0),
            audio_file_size=len(audio_data),
            transcribed_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transcribe audio: {str(e)}"
        )

@router.post("/synthesize")
async def synthesize_speech(
    synthesis_data: VoiceSynthesisRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Synthesize speech from text using ElevenLabs or Coqui TTS"""
    try:
        # Validate input
        if not synthesis_data.text or not synthesis_data.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text is required for synthesis"
            )
        
        # Clean text for speech synthesis (remove code, special characters)
        clean_text = clean_text_for_speech(synthesis_data.text)
        
        if not clean_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No synthesizable text found after cleaning"
            )
        
        # Choose synthesis method based on mode
        if synthesis_data.mode == "online":
            audio_data = await synthesize_with_elevenlabs(
                text=clean_text,
                voice_id=synthesis_data.voice_id,
                voice_settings=synthesis_data.voice_settings or {}
            )
        else:
            audio_data = await synthesize_with_coqui_tts(
                text=clean_text,
                voice_id=synthesis_data.voice_id or "default",
                language=synthesis_data.language or "en"
            )
        
        # Store synthesis in memory if agent specified
        if synthesis_data.agent_id:
            try:
                from main import app
                orchestrator = app.state.orchestrator
                
                if synthesis_data.agent_id in orchestrator.agents:
                    agent = orchestrator.agents[synthesis_data.agent_id]
                    await agent.store_memory(
                        content=f"Text synthesized to speech: {clean_text[:100]}...",
                        content_type="voice_synthesis",
                        tags=["voice", "synthesis", "output"]
                    )
            except Exception as e:
                logger.warning(f"Failed to store synthesis in agent memory: {e}")
        
        # Return audio stream
        def generate_audio():
            yield audio_data
        
        return StreamingResponse(
            generate_audio(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=synthesis_{uuid.uuid4().hex[:8]}.mp3",
                "Content-Length": str(len(audio_data))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error synthesizing speech: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synthesize speech: {str(e)}"
        )

@router.post("/process-stream")
async def process_voice_stream(
    audio_chunk: UploadFile = File(...),
    session_id: str = Form(...),
    is_final: bool = Form(False),
    language: Optional[str] = Form("en"),
    current_user: User = Depends(get_current_active_user)
):
    """Process streaming voice input with VAD and real-time transcription"""
    try:
        # Read audio chunk
        chunk_data = await audio_chunk.read()
        
        # Process through VAD and streaming transcription
        result = await process_streaming_audio(
            audio_chunk=chunk_data,
            session_id=session_id,
            is_final=is_final,
            language=language,
            user_id=str(current_user.id)
        )
        
        return {
            "session_id": session_id,
            "has_speech": result.get("has_speech", False),
            "partial_text": result.get("partial_text", ""),
            "final_text": result.get("final_text", "") if is_final else "",
            "confidence": result.get("confidence", 0.0),
            "is_final": is_final,
            "processing_time": result.get("processing_time", 0.0),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing voice stream: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process voice stream: {str(e)}"
        )

@router.get("/voices/available")
async def get_available_voices(
    mode: str = "online",
    current_user: User = Depends(get_current_active_user)
):
    """Get list of available voices for synthesis"""
    try:
        if mode == "online":
            voices = await get_elevenlabs_voices()
        else:
            voices = await get_coqui_voices()
        
        return {
            "mode": mode,
            "voices": voices,
            "total_count": len(voices),
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving available voices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve available voices: {str(e)}"
        )

@router.get("/agent-voices")
async def get_agent_voice_mapping(
    current_user: User = Depends(get_current_active_user)
):
    """Get voice assignments for each agent"""
    try:
        from main import app
        
        orchestrator = app.state.orchestrator
        agent_configs = orchestrator.get_agent_configs()
        
        voice_mapping = {}
        for agent_id, config in agent_configs.items():
            voice_mapping[agent_id] = {
                "agent_name": config.get("name", agent_id),
                "voice_id": config.get("voice_id"),
                "voice_settings": config.get("voice_settings", {}),
                "description": config.get("description", "")
            }
        
        return {
            "agent_voices": voice_mapping,
            "total_agents": len(voice_mapping),
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving agent voice mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agent voice mapping: {str(e)}"
        )

@router.post("/test-voice")
async def test_voice_synthesis(
    voice_id: str,
    mode: str = "online",
    text: Optional[str] = "Hello, this is a voice test.",
    current_user: User = Depends(get_current_active_user)
):
    """Test voice synthesis with a sample text"""
    try:
        # Use provided text or default test text
        test_text = text or "Hello, this is a voice synthesis test. How does this voice sound?"
        
        # Synthesize test audio
        if mode == "online":
            audio_data = await synthesize_with_elevenlabs(
                text=test_text,
                voice_id=voice_id,
                voice_settings={}
            )
        else:
            audio_data = await synthesize_with_coqui_tts(
                text=test_text,
                voice_id=voice_id,
                language="en"
            )
        
        # Return audio stream
        def generate_audio():
            yield audio_data
        
        return StreamingResponse(
            generate_audio(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=voice_test_{voice_id}.mp3",
                "Content-Length": str(len(audio_data))
            }
        )
        
    except Exception as e:
        logger.error(f"Error testing voice synthesis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test voice synthesis: {str(e)}"
        )

@router.post("/interrupt")
async def interrupt_voice_playback(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Interrupt ongoing voice playback (barge-in)"""
    try:
        # Stop current voice synthesis/playback for the session
        result = await handle_voice_interrupt(session_id, str(current_user.id))
        
        return {
            "message": "Voice playback interrupted",
            "session_id": session_id,
            "interrupted": result.get("interrupted", False),
            "interrupted_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error interrupting voice playback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to interrupt voice playback: {str(e)}"
        )

@router.get("/session/{session_id}/status")
async def get_voice_session_status(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get current voice session status"""
    try:
        from core.redis_client import redis_client
        
        # Get session status from Redis
        session_key = f"voice_session:{session_id}:{current_user.id}"
        session_data = await redis_client.get(session_key)
        
        if not session_data:
            return {
                "session_id": session_id,
                "active": False,
                "status": "not_found"
            }
        
        return {
            "session_id": session_id,
            "active": session_data.get("active", False),
            "status": session_data.get("status", "unknown"),
            "started_at": session_data.get("started_at"),
            "last_activity": session_data.get("last_activity"),
            "current_mode": session_data.get("current_mode", "listening"),
            "partial_transcript": session_data.get("partial_transcript", "")
        }
        
    except Exception as e:
        logger.error(f"Error getting voice session status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get voice session status: {str(e)}"
        )

# Helper functions

async def transcribe_with_faster_whisper(
    audio_data: bytes,
    language: str,
    audio_format: str
) -> Dict[str, Any]:
    """Transcribe audio using Faster-Whisper"""
    try:
        from services.voice_service import VoiceService
        
        voice_service = VoiceService()
        result = await voice_service.transcribe_audio(
            audio_data=audio_data,
            language=language,
            audio_format=audio_format
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Faster-Whisper transcription failed: {e}")
        raise

async def synthesize_with_elevenlabs(
    text: str,
    voice_id: str,
    voice_settings: Dict[str, Any]
) -> bytes:
    """Synthesize speech using ElevenLabs API"""
    try:
        from services.voice_service import VoiceService
        
        voice_service = VoiceService()
        audio_data = await voice_service.synthesize_elevenlabs(
            text=text,
            voice_id=voice_id,
            voice_settings=voice_settings
        )
        
        return audio_data
        
    except Exception as e:
        logger.error(f"ElevenLabs synthesis failed: {e}")
        raise

async def synthesize_with_coqui_tts(
    text: str,
    voice_id: str,
    language: str
) -> bytes:
    """Synthesize speech using Coqui TTS"""
    try:
        from services.voice_service import VoiceService
        
        voice_service = VoiceService()
        audio_data = await voice_service.synthesize_coqui(
            text=text,
            voice_id=voice_id,
            language=language
        )
        
        return audio_data
        
    except Exception as e:
        logger.error(f"Coqui TTS synthesis failed: {e}")
        raise

def clean_text_for_speech(text: str) -> str:
    """Clean text for speech synthesis"""
    import re
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    
    # Remove special markdown syntax
    text = re.sub(r'[*_~`#]', '', text)
    
    # Remove excessive punctuation
    text = re.sub(r'[.]{2,}', '.', text)
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

async def process_streaming_audio(
    audio_chunk: bytes,
    session_id: str,
    is_final: bool,
    language: str,
    user_id: str
) -> Dict[str, Any]:
    """Process streaming audio with VAD"""
    try:
        from services.voice_service import VoiceService
        
        voice_service = VoiceService()
        result = await voice_service.process_audio_stream(
            audio_chunk=audio_chunk,
            session_id=session_id,
            is_final=is_final,
            language=language,
            user_id=user_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Streaming audio processing failed: {e}")
        raise

async def get_elevenlabs_voices() -> List[Dict[str, Any]]:
    """Get available ElevenLabs voices"""
    try:
        from services.voice_service import VoiceService
        
        voice_service = VoiceService()
        voices = await voice_service.get_elevenlabs_voices()
        
        return voices
        
    except Exception as e:
        logger.error(f"Failed to get ElevenLabs voices: {e}")
        return []

async def get_coqui_voices() -> List[Dict[str, Any]]:
    """Get available Coqui TTS voices"""
    try:
        from services.voice_service import VoiceService
        
        voice_service = VoiceService()
        voices = await voice_service.get_coqui_voices()
        
        return voices
        
    except Exception as e:
        logger.error(f"Failed to get Coqui voices: {e}")
        return []

async def handle_voice_interrupt(session_id: str, user_id: str) -> Dict[str, Any]:
    """Handle voice playback interruption"""
    try:
        from core.redis_client import redis_client
        
        # Update session status to interrupted
        session_key = f"voice_session:{session_id}:{user_id}"
        session_data = await redis_client.get(session_key) or {}
        
        session_data.update({
            "status": "interrupted",
            "interrupted_at": datetime.utcnow().isoformat(),
            "current_mode": "listening"
        })
        
        await redis_client.set(session_key, session_data, expire=3600)  # 1 hour
        
        # Notify WebSocket clients about the interruption
        from utils.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager()
        
        await websocket_manager.send_to_user(user_id, {
            "type": "voice_interrupted",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {"interrupted": True}
        
    except Exception as e:
        logger.error(f"Voice interrupt handling failed: {e}")
        return {"interrupted": False}