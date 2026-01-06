from flask import Flask, render_template, request
import os

def create_setup_app():
    app = Flask(__name__, template_folder='core/templates')
    
    # Load defaults
    defaults = {}
    
    # Try loading from .env first, then .env.example
    env_path = '.env' if os.path.exists('.env') else '.env.example'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    defaults[key] = value

    @app.route('/', methods=['GET', 'POST'])
    def setup():
        if request.method == 'POST':
            # Gather form data
            config = {
                'DATABASE_URL': request.form.get('database_url'),
                'PORT': request.form.get('port', '5011'),
                'LLM_BASE_URL': request.form.get('LLM_BASE_URL'),
                'LLM_MODEL_NAME': request.form.get('llm_model'),
                'LLM_API_KEY': request.form.get('llm_key', ''),
                'LLM_NUM_CTX': request.form.get('llm_ctx', '18000'),
                'TTS_BASE_URL': request.form.get('tts_url', ''),
                'OPENAI_API_KEY': request.form.get('openai_key', ''),
                'YOUTUBE_API_KEY': request.form.get('youtube_key', '')
            }
            
            # Simple validation
            if not config['DATABASE_URL'] or not config['LLM_BASE_URL']:
                return "Missing required fields", 400
            
            # Write to .env
            with open('.env', 'w') as f:
                for key, value in config.items():
                    f.write(f"{key}={value}\n")
                
            return "Setup Complete! Please restart the application."
        
        return render_template('setup.html', defaults=defaults)
        
    return app
