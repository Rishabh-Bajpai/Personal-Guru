import os
import urllib.parse
import requests
import json
import re
from dotenv import load_dotenv

load_dotenv()

LLM_ENDPOINT = os.getenv("LLM_ENDPOINT")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", 4096))
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")

def call_llm(prompt, is_json=False):
    """
    A helper function to call the LLM API using OpenAI-compatible protocol.
    Works with OpenAI, Ollama, LMStudio, VLLM, etc.
    """
    if not LLM_ENDPOINT or not LLM_MODEL_NAME:
        return "Error: LLM environment variables not set.", "Config Error"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }

    # Ensure the endpoint targets the chat completion path if not provided
    # Standard OpenAI base is like 'https://api.openai.com/v1'
    # Users might provide 'http://localhost:11434/v1' or just 'http://localhost:11434'
    # We will try to be smart or strictly follow a convention. 
    # Convention: LLM_ENDPOINT should be the base URL ending in /v1 (or similar root).
    # We append /chat/completions.
    
    # However, to be robust against trailing slashes:
    base_url = LLM_ENDPOINT.rstrip('/')
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
        
        messages = [{"role": "user", "content": prompt}]
        
        data = {
            "model": LLM_MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
        }
        
        # Note: Ollama via OpenAI-compat supports 'json_object' in recent versions.
        # But standard prompt engineering is safer for broader compatibility unless we know the provider supports response_format.
        if is_json:
            # We can try hinting via valid OpenAI param content or just rely on prompt.
            # Uncomment below if using a provider that strictly needs it for JSON
            # data["response_format"] = {"type": "json_object"} 
            pass

        response = requests.post(api_url, headers=headers, json=data, timeout=300)
        response.raise_for_status()
        
        response_json = response.json()
        content = response_json['choices'][0]['message']['content']

        print(f"LLM Response: {content}")

        if is_json:
            # The content is a string of JSON, so parse it
            # Sometimes LLMs wrap in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            try:
                # First, try to parse the entire content as JSON
                return json.loads(content), None
            except json.JSONDecodeError:
                # If that fails, try to find a JSON object embedded in the text
                print("Failed to parse content directly, attempting to extract JSON object.")
                try:
                    # Regex to find a JSON object within the text.
                    # We match from the first { to the last }
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        return json.loads(json_str), None
                except json.JSONDecodeError:
                    pass
                
                # Parsing failed
                return f"Error parsing JSON from LLM response: {content[:100]}...", json.JSONDecodeError("Failed to parse", content, 0)

        return content, None

    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Error calling LLM or parsing JSON: {e}")
        return f"Error communicating with LLM: {e}", e


def generate_audio(text, step_index, tts_engine="coqui"):
    """
    Generates audio from text using the specified TTS engine.
    """
    # Clean up old audio files - path needs to be relative to app/static or we pass full path
    # 'static' in Flask refers to the static folder.
    # Note: In new structure, static files might be in app/static or app/modes/chapter/static.
    # Audio seems ephemeral. Let's store in app/static for simplicity or temp.
    
    # We need to know where 'static' is.
    # Assuming app/static based on new structure.
    
    static_dir = os.path.join(os.getcwd(), 'app', 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    # Clean up old audio (basic implementation from app.py)
    for filename in os.listdir(static_dir):
        if filename.endswith('.wav'):
             try:
                os.remove(os.path.join(static_dir, filename))
             except OSError:
                 pass

    output_filename = os.path.join(static_dir, f"step_{step_index}.wav")
    server_url = os.getenv("TTS_URL")
    if not server_url:
        return None, "Coqui TTS URL not set."

    encoded_text = urllib.parse.quote(text)
    speaker_id = "p278"
    url = f"{server_url}?text={encoded_text}&speaker_id={speaker_id}"

    try:
        print(f"DEBUG: Calling TTS for step {step_index}, text length: {len(text)}, url: {server_url}")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(output_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return f"step_{step_index}.wav", None # Return relative filename for url_for
    except requests.exceptions.RequestException as e:
        return None, f"Error calling Coqui TTS: {e}"
