import os
import urllib.parse
import requests

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
