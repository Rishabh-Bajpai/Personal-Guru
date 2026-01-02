from flask import Flask, render_template, request, redirect, url_for
import os

def create_setup_app():
    app = Flask(__name__, template_folder='templates') # Checks strictly inside app/templates/ if run from app? No, relative to file.
    # Actually, if this file is in app/setup_app.py, template_folder='templates' looks in app/templates. Correct.
    
    @app.route('/', methods=['GET', 'POST'])
    def setup():
        if request.method == 'POST':
            # Gather form data
            db_url = request.form.get('database_url')
            llm_endpoint = request.form.get('llm_endpoint')
            llm_model = request.form.get('llm_model')
            llm_key = request.form.get('llm_key', '')
            
            # Simple validation
            if not db_url or not llm_endpoint or not llm_model:
                return "Missing required fields", 400
            
            # Write to .env
            env_content = f"""DATABASE_URL={db_url}
LLM_ENDPOINT={llm_endpoint}
LLM_MODEL_NAME={llm_model}
LLM_API_KEY={llm_key}
LLM_NUM_CTX=18000
PORT=5011
"""
            with open('.env', 'w') as f:
                f.write(env_content)
                
            return "Setup Complete! Please restart the application."
        
        return render_template('setup.html')
        
    return app
