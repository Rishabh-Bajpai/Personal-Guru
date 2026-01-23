import os
import time
import requests
import json
import re
import tempfile
import subprocess
import logging
import platform
import psutil
from datetime import datetime
from dotenv import load_dotenv
from app.core.exceptions import (
    MissingConfigError,
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    QuizValidationError,
    STTError
)

load_dotenv(override=True)

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", 4096))
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")
TTS_BASE_URL = os.getenv("TTS_BASE_URL", "http://localhost:8969/v1")
TTS_MODEL = os.getenv("TTS_MODEL", "tts-1")
STT_BASE_URL = os.getenv("STT_BASE_URL", "http://localhost:8969/v1")
STT_MODEL = os.getenv("STT_MODEL", "Systran/faster-whisper-medium.en")
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "en")
TTS_VOICE_DEFAULT = os.getenv("TTS_VOICE_DEFAULT", "af_bella")
TTS_VOICE_PODCAST_HOST = os.getenv("TTS_VOICE_PODCAST_HOST", "af_bella")
TTS_VOICE_PODCAST_GUEST = os.getenv("TTS_VOICE_PODCAST_GUEST", "am_puck")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "not-required")


def call_llm(prompt_or_messages, is_json=False):
    """
    A helper function to call the LLM API using OpenAI-compatible protocol.
    Works with OpenAI, Ollama, LMStudio, VLLM, etc.
    Accepts specific 'messages' list for chat history or a simple string 'prompt'.

    Raises:
        MissingConfigError: If LLM environment variables are not set
        LLMConnectionError: If cannot connect to LLM service
        LLMResponseError: If LLM response is invalid
        LLMTimeoutError: If LLM request times out
    """
    logger = logging.getLogger(__name__)

    if not LLM_BASE_URL or not LLM_MODEL_NAME:
        raise MissingConfigError(
            "LLM configuration missing",
            missing_vars=[
                v for v in [
                    'LLM_BASE_URL',
                    'LLM_MODEL_NAME'] if not os.getenv(v)],
            error_code="CFG010")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }

    # Ensure the endpoint targets the chat completion path if not provided
    # Standard OpenAI base is like 'https://api.openai.com/v1'
    # Users might provide 'http://localhost:11434/v1' or just 'http://localhost:11434'
    # We will try to be smart or strictly follow a convention.
    # Convention: LLM_BASE_URL should be the base URL ending in /v1 (or similar root).
    # We append /chat/completions.

    # However, to be robust against trailing slashes:
    base_url = LLM_BASE_URL.rstrip('/')
    if not base_url.endswith('/v1'):
        # some users might just put the host.
        # For ollama: http://localhost:11434/v1/chat/completions is valid.
        # IF user put http://localhost:11434, we might need to append /v1 if it's missing?
        # Let's assume the user follows the instruction to provide base url.
        # But commonly for ollama, they might forget.
        if "11434" in base_url and "/v1" not in base_url:
            base_url += "/v1"

    api_url = f"{base_url}/chat/completions"

    try:
        start_time = time.time()
        print(f"Calling LLM: {api_url}")

        if isinstance(prompt_or_messages, list):
            messages = prompt_or_messages
        else:
            messages = [{"role": "user", "content": prompt_or_messages}]

        data = {
            "model": LLM_MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": LLM_NUM_CTX,
        }

        # Note: Ollama via OpenAI-compat supports 'json_object' in recent versions.
        # But standard prompt engineering is safer for broader compatibility
        # unless we know the provider supports response_format.
        if is_json:
            # We can try hinting via valid OpenAI param content or just rely on prompt.
            # Uncomment below if using a provider that strictly needs it for JSON
            # data["response_format"] = {"type": "json_object"}
            pass

        response = requests.post(
            api_url,
            headers=headers,
            json=data,
            timeout=300)

        # Check specifically for model not found (404 from Ollama often means this)
        if response.status_code == 404:
            try:
                err_body = response.json()
                if "model" in err_body.get('error', {}).get('message', '').lower():
                    logger.error(f"Model not found: {LLM_MODEL_NAME}")
                    raise LLMConnectionError(
                        f"Model '{LLM_MODEL_NAME}' not found. Please pull it first.",
                        endpoint=api_url,
                        error_code="LLM015",
                        debug_info={"model": LLM_MODEL_NAME}
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

        response.raise_for_status()

        response_json = response.json()
        content = response_json['choices'][0]['message']['content']

        # Calculate latency
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)

        # Extract token usage if available
        usage = response_json.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)

        logger.debug(f"LLM Response received: {len(content)} characters. Latency: {latency_ms}ms")

        # Database Logging Hook
        try:
            # Local imports to avoid circular dependency
            from app.core.extensions import db
            from app.core.models import AIModelPerformance
            from flask_login import current_user

            # Only log if user is authenticated and we are in a request context
            if current_user and current_user.is_authenticated:
                perf_log = AIModelPerformance(
                    user_id=current_user.userid,
                    model_type='LLM',
                    model_name=LLM_MODEL_NAME,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )
                db.session.add(perf_log)
                db.session.commit()
                logger.debug("Logged AI performance metrics to database.")

        except Exception as db_err:
            # We catch generic exception because this is non-critical logging
            # and we don't want to fail the LLM call if DB logging fails
            # (e.g. if outside of app context or db lock)
            logger.warning(f"Failed to log AI performance: {db_err}")

        if is_json:
            # The content is a string of JSON, so parse it
            # Sometimes LLMs wrap in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            try:
                # First, try to parse the entire content as JSON
                return json.loads(content)
            except json.JSONDecodeError:
                # If that fails, try to find a JSON object embedded in the text
                logger.warning(
                    "Failed to parse content directly, attempting to extract JSON object.")
                try:
                    # Regex to find a JSON object within the text.
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

                # Parsing failed
                raise LLMResponseError(
                    "Failed to parse JSON from LLM response",
                    error_code="LLM010",
                    debug_info={"content_preview": content[:200]}
                )

        return content

    except requests.exceptions.Timeout as e:
        logger.error(f"LLM request timed out: {e}")
        raise LLMTimeoutError(
            "Request to LLM timed out after 300 seconds",
            timeout=300,
            error_code="LLM011",
            debug_info={"endpoint": api_url}
        )
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to LLM: {e}")
        # Check if it was connection refused
        raise LLMConnectionError(
            "Unable to connect to LLM service",
            endpoint=api_url,
            error_code="LLM012",
            debug_info={"original_error": str(e)}
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"LLM request failed: {e}")

        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None

        raise LLMConnectionError(
            f"LLM request failed: {str(e)}",
            endpoint=api_url,
            error_code="LLM013",
            debug_info={"status_code": status_code}
        )
    except (KeyError, IndexError) as e:
        logger.error(f"Invalid LLM response structure: {e}")
        raise LLMResponseError(
            "LLM response has unexpected structure",
            error_code="LLM014",
            debug_info={"error": str(e)}
        )


def validate_quiz_structure(quiz_data):
    """
    Validates the structure of a quiz JSON object.

    Raises:
        QuizValidationError: If quiz structure is invalid
    """
    if not quiz_data or "questions" not in quiz_data or not isinstance(
            quiz_data["questions"], list) or not quiz_data["questions"]:
        raise QuizValidationError(
            "Invalid quiz format: missing or empty questions list",
            error_code="QUIZ001",
            debug_info={
                "has_data": bool(quiz_data),
                "has_questions_key": "questions" in quiz_data if quiz_data else False})

    for i, q in enumerate(quiz_data["questions"]):
        if not isinstance(q, dict):
            raise QuizValidationError(
                f"Question {i} is not a dictionary",
                error_code="QUIZ002",
                debug_info={"question_index": i, "type": type(q).__name__}
            )

        if not all(k in q for k in ["question", "options", "correct_answer"]):
            missing_keys = [
                k for k in [
                    "question",
                    "options",
                    "correct_answer"] if k not in q]
            raise QuizValidationError(
                f"Question {i} missing required keys: {missing_keys}",
                error_code="QUIZ003",
                debug_info={"question_index": i, "missing_keys": missing_keys}
            )

        if not isinstance(q["question"], str) or not q["question"].strip():
            raise QuizValidationError(
                f"Question {i} has empty text",
                error_code="QUIZ004",
                debug_info={"question_index": i}
            )

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise QuizValidationError(
                f"Question {i} must have exactly 4 options",
                error_code="QUIZ005",
                debug_info={
                    "question_index": i,
                    "options_count": len(
                        q["options"]) if isinstance(
                        q.get("options"),
                        list) else 0})

        if not all(isinstance(opt, str) and opt.strip()
                   for opt in q["options"]):
            raise QuizValidationError(
                f"Question {i} has one or more empty options",
                error_code="QUIZ006",
                debug_info={"question_index": i}
            )

        correct_answer = q.get("correct_answer", "")
        if not isinstance(
                correct_answer,
                str) or correct_answer.upper() not in [
                'A',
                'B',
                'C',
                'D']:
            raise QuizValidationError(
                f"Question {i} has invalid correct_answer: must be A, B, C, or D",
                error_code="QUIZ007",
                debug_info={
                    "question_index": i,
                    "correct_answer": correct_answer})


def generate_audio(text, step_index):
    """
    Generates audio from text using the configured TTS service.
    Supports both Docker/OpenAI and local Kokoro modes via audio_service.
    """
    from app.common.audio_service import get_tts
    import soundfile as sf

    start_time = time.time()
    static_dir = os.path.join(os.getcwd(), 'app', 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    output_filename = os.path.join(static_dir, f"step_{step_index}.wav")

    # Clean up old audio
    for filename in os.listdir(static_dir):
        if f"step_{step_index}" in filename:
            try:
                os.remove(os.path.join(static_dir, filename))
            except OSError:
                pass

    try:
        tts = get_tts()
        result, sample_rate = tts.generate(text)

        # Handle both formats: bytes (Docker/OpenAI) or samples (local/Kokoro)
        if isinstance(result, bytes):
            with open(output_filename, 'wb') as f:
                f.write(result)
        else:
            sf.write(output_filename, result, sample_rate)

        # --- Logging Hook for TTS ---
        try:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            from app.core.extensions import db
            from app.core.models import AIModelPerformance
            from flask_login import current_user

            if current_user and current_user.is_authenticated:
                perf_log = AIModelPerformance(
                    user_id=current_user.userid,
                    model_type='TTS',
                    model_name=TTS_MODEL,
                    latency_ms=latency_ms,
                    input_tokens=len(text),
                    output_tokens=0
                )
                db.session.add(perf_log)
                db.session.commit()
        except Exception as e:
            logging.warning(f"Failed to log TTS performance: {e}")

        return f"step_{step_index}.wav", None

    except Exception as e:
        print(f"Error calling TTS: {e}")
        return None, f"Error calling TTS: {e}"


def reconcile_plan_steps(current_steps, current_plan, new_plan):
    """
    Reconciles the list of dict-based steps with a new list of plan strings.

    Preserves existing step content (title, material, questions) when strict matches are found.
    - If a preserved step is missing its title (e.g. from a placeholder), it defaults to the plan text.
    - Initializes new steps for plan items that don't match existing content.
    - Updates 'step_index' for all steps to match the new plan order.

    Args:
        current_steps (list): List of existing step dictionaries.
        current_plan (list): List of existing plan strings (titles).
        new_plan (list): List of new plan strings.

    Returns:
        list: A new list of step dictionaries aligned with the new plan.
    """
    step_content_map = {}
    for i, plan_text in enumerate(current_plan):
        if i < len(current_steps):
            step_content_map[plan_text] = current_steps[i]

    new_steps = []
    for i, step_text in enumerate(new_plan):
        if step_text in step_content_map:
            # Preserve existing content
            step_data = step_content_map[step_text]

            # Ensure title is populated from plan if missing in data (e.g. placeholder)
            if not step_data.get('title'):
                step_data['title'] = step_text

            # Update step_index to match new position
            step_data['step_index'] = i
            new_steps.append(step_data)
        else:
            # New step, empty content with correct index
            new_steps.append({'step_index': i, 'title': step_text})

    return new_steps


def get_user_context():
    """
    Retrieves the user context string from the database for LLM usage.
    Falls back to environment variable if no user or empty profile.
    """
    from flask_login import current_user

    try:
        if current_user.is_authenticated and current_user.user_profile:
            context = current_user.user_profile.to_context_string()
            if context.strip():
                return context
    except Exception as e:
        print(f"Error fetching user context from current_user: {e}")
        pass

    return os.getenv("USER_BACKGROUND", "a beginner")


def generate_podcast_audio(transcript, output_filename):
    """
    Generates a full podcast audio file from a transcript using the configured TTS service.
    Supports both Docker/OpenAI and local Kokoro modes via audio_service.
    """
    from app.common.audio_service import get_tts
    import soundfile as sf
    import numpy as np

    start_time = time.time()

    # 1. Parse Transcript
    lines = []
    print("Parsing transcript...")
    for line in transcript.strip().split('\n'):
        if ':' in line:
            parts = line.split(':', 1)
            speaker = parts[0].strip()
            content = parts[1].strip()
            if content:
                lines.append((speaker, content))

    if not lines:
        return False, "No dialogue lines found in transcript"

    # 2. Get TTS Service
    try:
        tts = get_tts()
    except Exception as e:
        return False, f"Failed to get TTS service: {e}"

    # 3. Assign Voices
    unique_speakers = sorted(list(set(s for s, t in lines)))
    available_voices = [
        TTS_VOICE_PODCAST_HOST,
        TTS_VOICE_PODCAST_GUEST,
        'af_bella', 'af_sarah', 'af_nicole', 'af_sky',
        'am_adam', 'am_michael', 'am_puck',
        'bf_emma', 'bf_isabella',
        'bm_george', 'bm_lewis'
    ]
    available_voices = list(dict.fromkeys(available_voices))
    voice_map = {speaker: available_voices[i % len(available_voices)]
                 for i, speaker in enumerate(unique_speakers)}

    # 4. Generate Audio Segments
    temp_files = []
    all_samples = []
    sample_rate = None
    is_local_mode = False

    print("--- Synthesizing Audio Segments ---")

    try:
        for i, (speaker, text) in enumerate(lines):
            voice = voice_map.get(speaker, TTS_VOICE_DEFAULT)
            result, sr = tts.generate(text, voice=voice)
            print(f"DEBUG: TTS Result Type: {type(result)}")

            if isinstance(result, bytes):
                # Docker/OpenAI mode - save to temp file for ffmpeg merge
                fd, temp_path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
                with open(temp_path, 'wb') as f:
                    f.write(result)
                temp_files.append(temp_path)
            else:
                # Local mode - concatenate samples directly
                is_local_mode = True
                if sample_rate is None:
                    sample_rate = sr
                all_samples.append(result)

        if is_local_mode:
            # Local mode - concatenate samples and save directly
            if all_samples:
                combined = np.concatenate(all_samples)
                sf.write(output_filename, combined, sample_rate)
                print(f"Saved podcast audio to: {output_filename}")
            else:
                return False, "Failed to generate any audio content"
        else:
            # Docker/OpenAI mode - merge using ffmpeg
            if not temp_files:
                return False, "Failed to generate any audio content"

            list_file_fd, list_file_path = tempfile.mkstemp(suffix=".txt")
            with os.fdopen(list_file_fd, 'w') as f:
                for tf in temp_files:
                    f.write(f"file '{tf}'\n")

            print("Merging audio files using ffmpeg...")
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file_path,
                "-c", "copy",
                "-y",
                output_filename
            ]

            try:
                merge_result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if merge_result.returncode != 0:
                    print(f"ffmpeg error: {merge_result.stderr.decode()}")
                    raise OSError("ffmpeg failed")

            except (OSError, FileNotFoundError):
                print("ffmpeg not found or failed, falling back to direct concatenation...")
                # Fallback: Simple concatenation (works for MP3 often)
                with open(output_filename, 'wb') as outfile:
                    for tf in temp_files:
                        with open(tf, 'rb') as infile:
                            outfile.write(infile.read())

            # Clean up list file
            os.remove(list_file_path)

        # --- Logging Hook for Podcast TTS ---
        try:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            from app.core.extensions import db
            from app.core.models import AIModelPerformance
            from flask_login import current_user

            # Calculate approx input length from lines
            total_chars = sum(len(txt) for _, txt in lines)

            if current_user and current_user.is_authenticated:
                perf_log = AIModelPerformance(
                    user_id=current_user.userid,
                    model_type='TTS',
                    model_name=TTS_MODEL,
                    latency_ms=latency_ms,
                    input_tokens=total_chars,
                    output_tokens=0
                )
                db.session.add(perf_log)
                db.session.commit()
        except Exception as e:
            logging.warning(f"Failed to log Podcast TTS performance: {e}")

        return True, None

    except Exception as e:
        print(f"Error in podcast generation: {e}")
        return False, f"Error: {str(e)}"
    finally:
        # Cleanup temp audio files
        for tf in temp_files:
            if os.path.exists(tf):
                os.remove(tf)


def transcribe_audio(audio_file_path):
    """
    Transcribes audio using the configured STT service.
    Supports both Docker/OpenAI and local faster-whisper modes via audio_service.
    """
    from app.common.audio_service import get_stt

    start_time = time.time()

    if not os.path.exists(audio_file_path):
        raise STTError(f"Audio file not found: {audio_file_path}")

    try:
        stt = get_stt()
        transcript = stt.transcribe(audio_file_path)

        # --- Logging Hook for STT ---
        try:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            from app.core.extensions import db
            from app.core.models import AIModelPerformance
            from flask_login import current_user

            output_len = len(transcript) if transcript else 0

            if current_user and current_user.is_authenticated:
                perf_log = AIModelPerformance(
                    user_id=current_user.userid,
                    model_type='STT',
                    model_name=STT_MODEL,
                    latency_ms=latency_ms,
                    input_tokens=0,
                    output_tokens=output_len
                )
                db.session.add(perf_log)
                db.session.commit()
        except Exception as e:
            logging.warning(f"Failed to log STT performance: {e}")

        return transcript
    except Exception as e:
        print(f"Error calling STT: {e}")
        raise STTError(f"Error calling STT: {e}")


def summarize_text(text, max_lines=4):
    """
    Summarizes the given text into a dense, concise summary of 1-4 lines.
    """
    if not text or not text.strip():
        return ""

    prompt = f"""
You are an expert summarizer. Your task is to condense the following text into a very dense summary.
Requirements:
1. Minimum 1 line, maximum {max_lines} lines.
2. Maintain all essential core information and context.
3. Remove conversational filler, pleasantries, and redundancy.
4. Output ONLY the summary.

Text to summarize:
{text}
"""
    try:
        summary = call_llm(prompt)
        return summary.strip()
    except Exception as e:
        # Fallback if summarization fails: truncate or return original
        print(f"Summarization failed: {e}")
        # Return first 300 chars as backup
        return text[:300] + "..." if len(text) > 300 else text


def log_telemetry(event_type: str, triggers: dict, payload: dict, installation_id: str = None) -> None:
    """
    Logs a telemetry event to the database.
    Fails silently on errors to avoid disrupting the user experience.

    Args:
        event_type (str): The type of event (e.g., 'user_login', 'quiz_submitted').
        triggers (dict): What triggered the event (e.g., {'source': 'web_ui', 'action': 'click'}).
        payload (dict): The data payload for the event.
        installation_id (str, optional): The installation ID. If None, attempts to resolve from current_user or DB.
    """
    import uuid
    from flask import session
    from flask_login import current_user
    from app.core.extensions import db
    from app.core.models import TelemetryLog, Installation

    logger = logging.getLogger(__name__)

    try:
        # Resolve User ID (Nullable)
        user_id = None
        if current_user and current_user.is_authenticated:
            user_id = current_user.userid
            # If installation_id not provided, try to get from user
            if not installation_id:
                installation_id = current_user.installation_id

        # Resolve Installation ID (Non-Nullable)
        if not installation_id:
            # Try to find any installation record (assuming single-tenant / personal use)
            inst_record = Installation.query.first()
            if inst_record:
                installation_id = inst_record.installation_id

        # If we still don't have an installation_id, we cannot log (Constraint Violation)
        if not installation_id:
            logger.debug(f"Skipping telemetry {event_type}: No installation_id found.")
            return

        # Ensure session_id exists
        if 'telemetry_session_id' not in session:
            session['telemetry_session_id'] = str(uuid.uuid4())

        session_id = session['telemetry_session_id']

        log_entry = TelemetryLog(
            user_id=user_id,
            installation_id=installation_id,
            session_id=session_id,
            event_type=event_type,
            triggers=triggers,
            payload=payload
        )

        db.session.add(log_entry)
        db.session.commit()
        logger.debug(f"Telemetry logged: {event_type}")

    except Exception as e:
        # Log error but fail silently to avoid interrupting user flow
        logger.error(f"Failed to log telemetry: {e}")


def get_system_info():
    """
    Gather system information for Installation record.
    Returns a dict with cpu_cores, ram_gb, gpu_model, os_version, install_method.
    """
    info = {
        'cpu_cores': os.cpu_count(),
        'ram_gb': round(psutil.virtual_memory().total / (1024**3)),
        'os_version': platform.platform(),
        'install_method': 'local',  # Default
        'gpu_model': 'Unknown'
    }

    # Check for Docker
    if os.path.exists('/.dockerenv'):
        info['install_method'] = 'docker'

    # GPU Detection (cross-platform, multi-vendor)
    gpu_detected = False

    # Try NVIDIA (nvidia-smi)
    if not gpu_detected:
        try:
            result = subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                info['gpu_model'] = result.stdout.strip().split('\n')[0]
                gpu_detected = True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    # Try AMD (rocm-smi)
    if not gpu_detected:
        try:
            result = subprocess.run(['rocm-smi', '--showproductname'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                model_name = result.stdout.strip().split('\n')[0]
                info['gpu_model'] = f"AMD {model_name}"
                gpu_detected = True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    # Try Intel (Linux)
    if not gpu_detected and platform.system() == 'Linux':
        try:
            result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'VGA' in line or 'Display' in line or '3D' in line:
                        if 'Intel' in line:
                            info['gpu_model'] = line.split(':')[-1].strip()
                            gpu_detected = True
                            break
                        elif 'AMD' in line or 'ATI' in line:
                            info['gpu_model'] = line.split(':')[-1].strip()
                            gpu_detected = True
                            break
                        elif 'NVIDIA' in line:
                            info['gpu_model'] = line.split(':')[-1].strip()
                            gpu_detected = True
                            break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    # Try macOS (Apple Silicon / discrete GPU)
    if not gpu_detected and platform.system() == 'Darwin':
        try:
            result = subprocess.run(
                ['system_profiler', 'SPDisplaysDataType'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Chipset Model:' in line or 'Chip:' in line:
                        info['gpu_model'] = line.split(':')[-1].strip()
                        gpu_detected = True
                        break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    return info


# Cache for update check (simple in-memory cache)
_update_cache = {
    "last_checked": None,
    "data": None
}


def check_for_updates(current_version):
    """
    Checks GitHub for the latest release tag.
    Returns update info dict if a new version is available, else None.
    Default cache time: 1 hour.
    """
    global _update_cache

    # Check cache (1 hour expiry)
    now = datetime.now()
    if _update_cache["data"] and _update_cache["last_checked"]:
        if (now - _update_cache["last_checked"]).total_seconds() < 3600:
            return _compare_versions(current_version, _update_cache["data"])

    try:
        updated_cache_data = _fetch_github_release()
        if updated_cache_data:
            _update_cache["data"] = updated_cache_data
            _update_cache["last_checked"] = now
            return _compare_versions(current_version, updated_cache_data)
    except Exception as e:
        level = logging.INFO
        logging.getLogger(__name__).log(level, f"Failed to check for updates: {e}")

    return None


def _fetch_github_release():
    """Fetch the latest release from GitHub."""
    url = "https://api.github.com/repos/Rishabh-Bajpai/Personal-Guru/releases/latest"
    resp = requests.get(url, timeout=3)
    if resp.status_code == 200:
        data = resp.json()
        return {
            "tag_name": data.get("tag_name"),
            "html_url": data.get("html_url"),
            "published_at": data.get("published_at"),
            "name": data.get("name")
        }
    return None


def _compare_versions(current_ver, release_data):
    """Compare current version with latest release."""
    if not release_data:
        return None

    latest_ver = release_data["tag_name"].lstrip("v")
    curr_ver = current_ver.lstrip("v")

    # Simple semantic version comparison (assumes format 1.0.0)
    if latest_ver != curr_ver:
        return {
            "id": -1,
            "title": f"New Update Available: {release_data['tag_name']}",
            "message": f"A new version ({release_data['tag_name']}) is available on GitHub.",
            "notification_type": "info",
            "url": release_data["html_url"]
        }
    return None
