import sys
import os
from flask import Flask, render_template_string
from sqlalchemy.orm import class_mapper
from dotenv import load_dotenv

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

from config import Config
from app.common.extensions import db
from app.common import models

# --- Standalone App Setup ---
def create_viewer_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize only the DB extension
    db.init_app(app)
    
    return app

app = create_viewer_app()

MODELS = {
    'Topic': models.Topic,
    'StudyStep': models.StudyStep,
    'Quiz': models.Quiz,
    'Flashcard': models.Flashcard,
    'User': models.User
}

VIEWER_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DB Viewer</title>
    <style>
      body { font-family: sans-serif; padding: 20px; background-color: #1a1a1a; color: #e0e0e0; }
      nav { margin-bottom: 20px; }
      nav a { margin-right: 10px; text-decoration: none; color: #66b0ff; }
      nav a:hover { text-decoration: underline; }
      table { border-collapse: collapse; width: 100%; border: 1px solid #444; }
      th, td { border: 1px solid #444; padding: 8px; text-align: left; vertical-align: top; }
      th { background-color: #333; color: #fff; }
      tr:nth-child(even) { background-color: #252525; }
      pre { margin: 0; white-space: pre-wrap; font-size: 0.9em; color: #ccc; }
    </style>
  </head>
  <body>
    <h1>Database Viewer</h1>
    <nav>
        <a href="/db-viewer">Home</a>
        {% for name in models %}
            <a href="/db-viewer/{{ name }}">{{ name }}</a>
        {% endfor %}
    </nav>
    
    {% if current_model %}
        <h2>{{ current_model }}</h2>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        {% for col in columns %}
                            <th>{{ col }}</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for row in rows %}
                        <tr>
                            {% for col in columns %}
                                <td>
                                    {% if col in json_cols %}
                                        <pre>{{ row[col] | tojson(indent=2) }}</pre>
                                    {% else %}
                                        {{ row[col] }}
                                    {% endif %}
                                </td>
                            {% endfor %}
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    {% else %}
        <p>Select a table to view data.</p>
    {% endif %}
  </body>
</html>
"""

@app.route('/db-viewer')
@app.route('/db-viewer/<model_name>')
def db_viewer(model_name=None):
    if model_name and model_name in MODELS:
        model = MODELS[model_name]
        mapper = class_mapper(model)
        columns = [c.name for c in mapper.columns]
        
        # Identify JSON columns for formatting
        json_cols = []
        for c in mapper.columns:
            # Check if type is JSON or JSONB
            # Casting type to string is a robust way to check for SQL types in SQLAlchemy
            if 'JSON' in str(c.type):
                json_cols.append(c.name)

        items = model.query.all()
        rows = []
        for item in items:
            row = {}
            for col in columns:
                val = getattr(item, col)
                row[col] = val
            rows.append(row)
            
        return render_template_string(VIEWER_HTML, 
                                      models=MODELS.keys(), 
                                      current_model=model_name, 
                                      columns=columns, 
                                      rows=rows,
                                      json_cols=json_cols)
    
    return render_template_string(VIEWER_HTML, models=MODELS.keys(), current_model=None)

# Redirect root to viewer for convenience in this standalone mode
@app.route('/')
def index():
    return render_template_string(VIEWER_HTML, models=MODELS.keys(), current_model=None)

if __name__ == '__main__':
    print("Starting DB Viewer on http://localhost:5012/")
    app.run(host='0.0.0.0', port=5012, debug=True)
