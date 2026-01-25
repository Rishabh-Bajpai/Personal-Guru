"""
Audio Service - TTS and STT abstraction layer.

This module provides a unified interface for audio services (TTS/STT) that can be
backed by either Docker/OpenAI or local models (Kokoro/faster-whisper).

Services are initialized once at app startup based on environment configuration.
"""
import os
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

class KokoroTTS(TTSService):
    """TTS using local Kokoro ONNX model."""

    def __init__(self, default_voice: str = "af_bella"):
        from kokoro_onnx import Kokoro
        from misaki import en, espeak

        logger.info("Loading Kokoro TTS model (downloading on first run)...")
        self.default_voice = default_voice

        # Define model paths (V1.0 Standard)
        model_dir = os.path.join(os.getcwd(), 'data', 'models')
        os.makedirs(model_dir, exist_ok=True)

        onnx_path = os.path.join(model_dir, "kokoro-v1.0.onnx")
        voices_path = os.path.join(model_dir, "voices-v1.0.bin")

        # GitHub Release URLs (v1.0)
        base_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
        onnx_url = f"{base_url}/kokoro-v1.0.onnx"
        voices_url = f"{base_url}/voices-v1.0.bin"

        # Download if missing
        if not os.path.exists(onnx_path):
            logger.info(f"Downloading model to {onnx_path}...")
            self._download_file(onnx_url, onnx_path)

        if not os.path.exists(voices_path):
            logger.info(f"Downloading voices to {voices_path}...")
            self._download_file(voices_url, voices_path)

        # Initialize G2P (Graph-to-Phoneme)
        # Suppress phonemizer warnings (usually harmless word count mismatches)
        logging.getLogger("phonemizer").setLevel(logging.ERROR)

        try:
            # Try with espeak fallback if available, else standard
            fallback = espeak.EspeakFallback(british=False)
            self.g2p = en.G2P(trf=False, british=False, fallback=fallback)
        except Exception:
            logger.info("eSpeak not available, using pure Misaki G2P")
            self.g2p = en.G2P(trf=False, british=False, fallback=None)

        try:
            self.kokoro = Kokoro(onnx_path, voices_path)
            logger.info("Kokoro TTS initialized successfully (V1.0)")
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro: {e}")
            raise

    def _download_file(self, url, path):
        """
        Helper to download a file from a URL to a local path.

        Args:
            url: Source URL.
            path: Destination file path.
        """
        import requests
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            raise

    def generate(self, text: str, voice: Optional[str] = None) -> Tuple[any, int]:
        """
        Generate audio using local Kokoro model.

        Args:
            text: Text to synthesize.
            voice: Voice ID to use (defaults to 'af_bella').

        Returns:
            Tuple: (audio_samples, sample_rate). Samples are numpy array.
        """
        voice = voice or self.default_voice
        # Convert text to phonemes first using Misaki
        phonemes, _ = self.g2p(text)
        # Generate audio from phonemes
        samples, sample_rate = self.kokoro.create(phonemes, voice=voice, speed=1.0, is_phonemes=True)
        return samples, sample_rate


class WhisperSTT(STTService):
    """STT using local faster-whisper model."""

    def __init__(self, model_size: str = "medium"):
        from faster_whisper import WhisperModel
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"

        logger.info(f"Loading faster-whisper {model_size} on {device}...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
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
    if tts_provider == "native":

        try:
            logger.info("Loading Native Kokoro TTS model (in-process)...")
            _tts_service = KokoroTTS(
                default_voice=os.getenv("TTS_VOICE_DEFAULT", "af_bella")
            )
        except ImportError as e:
            logger.error(f"Kokoro not installed: {e}")
            logger.warning("Install with: pip install kokoro-onnx")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro TTS: {e}")
            import traceback
            traceback.print_exc()
            raise
    elif tts_provider == "externalapi":
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
