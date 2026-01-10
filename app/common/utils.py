import os
import requests
import json
import re
import tempfile
import subprocess
import logging
from dotenv import load_dotenv
from openai import OpenAI
from app.core.exceptions import (
    MissingConfigError,
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    QuizValidationError,
    STTError
)

load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", 18000))
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")
TTS_BASE_URL = os.getenv("TTS_BASE_URL", "http://localhost:8969/v1")
STT_BASE_URL = os.getenv("STT_BASE_URL", "http://localhost:8969/v1")
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
        response.raise_for_status()

        response_json = response.json()
        content = response_json['choices'][0]['message']['content']

        logger.debug(f"LLM Response received: {len(content)} characters")

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
        raise LLMConnectionError(
            "Unable to connect to LLM service",
            endpoint=api_url,
            error_code="LLM012",
            debug_info={"original_error": str(e)}
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"LLM request failed: {e}")
        raise LLMConnectionError(
            f"LLM request failed: {str(e)}",
            endpoint=api_url,
            error_code="LLM013",
            debug_info={
                "status_code": getattr(
                    e.response,
                    'status_code',
                    None) if hasattr(
                    e,
                    'response') else None})
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
    Generates audio from text using the configured OpenAI-compatible TTS (Kokoro).
    Supports long text by chunking and merging.
    """
    static_dir = os.path.join(os.getcwd(), 'app', 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    # Clean up old audio
    for filename in os.listdir(static_dir):
        if filename.endswith('.wav') and f"step_{step_index}.wav" == filename:
            try:
                os.remove(os.path.join(static_dir, filename))
            except OSError:
                pass

    # 1. Chunk Text
    # Split by simple sentence delimiters to be safe
    # Kokoro has a limit around 500 tokens (approx 2000 chars maybe, but 510 phonemes is small)
    # Let's target ~300 chars to be safe.
    chunks = []

    # Helper to split text
    sentences = re.split(r'([.!?]+)', text)
    current_chunk = ""

    for i in range(0, len(sentences) - 1, 2):
        sentence = sentences[i] + sentences[i + 1]
        if len(current_chunk) + len(sentence) < 300:
            current_chunk += sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence

    # Add trailing sentence/text
    if len(sentences) % 2 == 1:
        current_chunk += sentences[-1]

    if current_chunk:
        chunks.append(current_chunk)

    if not chunks:
        chunks = [text]  # Fallback if split failed or empty

    # 2. Generate Segments
    temp_files = []
    output_filename = os.path.join(static_dir, f"step_{step_index}.wav")

    print(f"Connecting to TTS at: {TTS_BASE_URL} for {len(chunks)} chunks")

    try:
        tts_client = OpenAI(base_url=TTS_BASE_URL, api_key=OPENAI_API_KEY)
        voice = "af_bella"

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            print(
                f"DEBUG: Generating chunk {i+1}/{len(chunks)}, len: {len(chunk)}")
            response = tts_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=chunk
            )

            # Save segment to temp file
            fd, temp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            response.stream_to_file(temp_path)
            temp_files.append(temp_path)

        if not temp_files:
            return None, "Failed to generate any audio content"

        # 3. Merge Audio using ffmpeg
        list_file_fd, list_file_path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(list_file_fd, 'w') as f:
            for tf in temp_files:
                f.write(f"file '{tf}'\n")

        print("Merging audio files...")
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file_path,
            "-c", "copy",
            "-y",
            output_filename
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        os.remove(list_file_path)

        if result.returncode != 0:
            return None, f"ffmpeg merge failed: {result.stderr.decode()}"

        return f"step_{step_index}.wav", None

    except Exception as e:
        print(f"Error calling TTS: {e}")
        return None, f"Error calling TTS: {e}"
    finally:
        # Cleanup temp segments
        for tf in temp_files:
            if os.path.exists(tf):
                os.remove(tf)


def reconcile_plan_steps(current_steps, current_plan, new_plan):
    """
    Reconciles the list of dict-based steps with a new list of plan strings.
    Preserves content for steps that still exist (matching title/text),
    initializes new steps, and updates step_index.
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
            # Update step_index to match new position
            step_data['step_index'] = i
            new_steps.append(step_data)
        else:
            # New step, empty content with correct index
            new_steps.append({'step_index': i})

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
    Generates a full podcast audio file from a transcript using OpenAI-compatible TTS.
    """
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

    # 2. Setup TTS
    print(f"Connecting to TTS at: {TTS_BASE_URL}")
    try:
        tts_client = OpenAI(base_url=TTS_BASE_URL, api_key=OPENAI_API_KEY)
    except Exception as e:
        return False, f"Failed to initialize TTS client: {e}"

    # 3. Assign Voices
    unique_speakers = sorted(list(set(s for s, t in lines)))
    available_voices = [
        'af_bella',
        'am_michael',
        'am_puck',
        'af_nicole',
        'af_heart',
        'af_sarah',
        'am_adam']

    voice_map = {speaker: available_voices[i % len(
        available_voices)] for i, speaker in enumerate(unique_speakers)}

    # 4. Generate Audio Segments
    temp_files = []
    print("--- Synthesizing Audio Segments ---")

    try:
        for i, (speaker, text) in enumerate(lines):
            voice = voice_map.get(speaker, 'alloy')
            print(f"Generating: {speaker} ({voice}) -> '{text[:20]}...'")

            response = tts_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )

            # Save segment to temp file
            # Use .wav extension to ensure ffmpeg treats it correctly if
            # headers are weird, though usually .mp3 from OpenAI
            fd, temp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            response.stream_to_file(temp_path)
            temp_files.append(temp_path)

        if not temp_files:
            return False, "Failed to generate any audio content"

        # 5. Merge Audio using ffmpeg
        # ffmpeg -i "concat:file1.mp3|file2.mp3" -c copy output.mp3 (concatenation protocol)
        # OR using a list file for safer handling of many files

        list_file_fd, list_file_path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(list_file_fd, 'w') as f:
            for tf in temp_files:
                f.write(f"file '{tf}'\n")

        print("Merging audio files using ffmpeg...")
        # ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp3
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file_path,
            "-c", "copy",
            "-y",  # Overwrite output
            output_filename
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        # Clean up list file
        os.remove(list_file_path)

        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr.decode()}")
            return False, f"ffmpeg merge failed: {result.stderr.decode()}"

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
    Transcribes audio using an OpenAI-compatible STT service (e.g., speaches).
    """
    if not STT_BASE_URL:
        return None, "STT service not configured"

    try:
        print(f"Connecting to STT at: {STT_BASE_URL}")
        client = OpenAI(base_url=STT_BASE_URL, api_key=OPENAI_API_KEY)

        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="Systran/faster-whisper-medium.en",
                file=audio_file,
                response_format="text"
            )

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
