"""
Audio Service - TTS and STT abstraction layer.

This module provides a unified interface for audio services (TTS/STT) that can be
backed by either Docker/OpenAI or local models (Kokoro/faster-whisper).

Services are initialized once at app startup based on environment configuration.
"""
import os
import sys
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Union

logger = logging.getLogger(__name__)


# =============================================================================
# ABSTRACT INTERFACES
# =============================================================================

class TTSService(ABC):
    """Abstract interface for Text-to-Speech services."""

    @abstractmethod
    def generate(self, text: str, voice: Optional[str] = None) -> Tuple[Union[bytes, any], Optional[int]]:
        """
        Generate audio from text.

        Args:
            text: Text to convert to speech
            voice: Optional voice ID to use

        Returns:
            Tuple of (audio_data, sample_rate)
            - Docker/OpenAI: (bytes, None)
            - Local/Kokoro: (numpy array, sample_rate)
        """
        pass


class STTService(ABC):
    """Abstract interface for Speech-to-Text services."""

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file

        Returns:
            Transcribed text
        """
        pass


# =============================================================================
# OPENAI/DOCKER IMPLEMENTATIONS
# =============================================================================

class OpenAITTS(TTSService):
    """TTS using OpenAI-compatible API (Docker or remote)."""

    def __init__(self, base_url: str, api_key: str, model: str, default_voice: str):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.default_voice = default_voice
        logger.info(f"OpenAI TTS initialized: {base_url}")

    def generate(self, text: str, voice: Optional[str] = None) -> Tuple[bytes, None]:
        """
        Generate audio using OpenAI-compatible API.

        Args:
            text: Text content to synthesize.
            voice: Optional voice ID override.

        Returns:
            Tuple: (audio_bytes, None) - Compatible with downstream logic.
        """
        voice = voice or self.default_voice
        response = self.client.audio.speech.create(
            model=self.model,
            voice=voice,
            input=text
        )
        return response.content, None


class OpenAISTT(STTService):
    """STT using OpenAI-compatible API (Docker or remote)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        logger.info(f"OpenAI STT initialized: {base_url}")

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file using OpenAI API.

        Args:
            audio_path: Absolute path to the audio file.

        Returns:
            str: Transcribed text.
        """
        with open(audio_path, "rb") as f:
            result = self.client.audio.transcriptions.create(
                model=self.model,
                file=f
            )
        return result.text


# =============================================================================
# LOCAL IMPLEMENTATIONS
# =============================================================================

# KokoroTTS removed as per configuration change





class WhisperSTT(STTService):
    """STT using local faster-whisper model."""

    def __init__(self, model_size: str = "medium"):
        from faster_whisper import WhisperModel

        device = "cpu"
        compute_type = "int8"

        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
        except ImportError:
            pass # Use defaults (cpu/int8)

        # Determine base directory for model storage
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            # Assumes running from project root or similar structure
            # If running via 'python run.py', getcwd() is usually root.
            # But let's be safe and use file relative path logic if getcwd isn't reliable?
            # Actually, standard practice for this app seems to be relying on GetCwd for dev, or relative paths.
            # Let's use the same logic as entry_point if possible, or just os.getcwd() if we trust it.
            # safer:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        model_dir = os.path.join(base_dir, 'data', 'models', 'whisper')
        os.makedirs(model_dir, exist_ok=True)

        logger.info(f"Loading faster-whisper {model_size} on {device}...")
        logger.info(f"Model path: {model_dir}")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type, download_root=model_dir)
        logger.info("Whisper STT initialized successfully")

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio using local Whisper model.

        Args:
            audio_path: Path to the audio file.

        Returns:
            str: Transcribed text.
        """
        segments, _ = self.model.transcribe(audio_path, beam_size=5)
        return "".join([segment.text for segment in segments]).strip()


# =============================================================================
# SERVICE MANAGEMENT
# =============================================================================

# Global singleton instances
_tts_service: Optional[TTSService] = None
_stt_service: Optional[STTService] = None


def init_audio_services():
    """
    Initialize audio services based on environment configuration.
    Called once at app startup.

    Only initializes local models (Kokoro/Whisper) when explicitly using local mode.
    Docker/OpenAI mode uses lightweight API clients.
    """
    global _tts_service, _stt_service

    tts_provider = os.getenv("TTS_PROVIDER", "externalapi").lower()
    stt_provider = os.getenv("STT_PROVIDER", "externalapi").lower()

    logger.info(f"Initializing audio services: TTS={tts_provider}, STT={stt_provider}")

    # Initialize TTS
    # Initialize TTS
    if tts_provider == "native":
        logger.warning("Native TTS (Kokoro) has been removed. Falling back to externalapi.")
        tts_provider = "externalapi"

    if tts_provider == "externalapi":
        # API mode (OpenAI compatible) - docker or external api
        _tts_service = OpenAITTS(
            base_url=os.getenv("TTS_BASE_URL", "http://localhost:8969/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "not-required"),
            model=os.getenv("TTS_MODEL", "tts-1"),
            default_voice=os.getenv("TTS_VOICE_DEFAULT", "af_bella")
        )

    # Initialize STT
    if stt_provider == "native":
        try:

            logger.info("Loading Native Whisper STT model (in-process)...")
            _stt_service = WhisperSTT(model_size="medium")
        except ImportError as e:
            logger.error(f"faster-whisper not installed: {e}")
            logger.warning("Install with: pip install faster-whisper")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Whisper STT: {e}")
            import traceback
            traceback.print_exc()
            raise
    elif stt_provider == "externalapi":
        # API mode (OpenAI compatible) - docker or external api
        _stt_service = OpenAISTT(
            base_url=os.getenv("STT_BASE_URL", "http://localhost:8969/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "not-required"),
            model=os.getenv("STT_MODEL", "whisper-1")
        )


def get_tts() -> TTSService:
    """Get the initialized TTS service. Auto-initializes if needed."""
    global _tts_service
    if _tts_service is None:
        logger.info("TTS service not initialized. Auto-initializing...")
        init_audio_services()

    if _tts_service is None:
        raise RuntimeError("TTS service failed to initialize.")
    return _tts_service


def get_stt() -> STTService:
    """Get the initialized STT service. Auto-initializes if needed."""
    global _stt_service
    if _stt_service is None:
        logger.info("STT service not initialized. Auto-initializing...")
        init_audio_services()

    if _stt_service is None:
        raise RuntimeError("STT service failed to initialize.")
    return _stt_service
