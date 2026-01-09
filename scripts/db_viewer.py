import sys
import os
from flask import Flask, render_template_string, redirect
from sqlalchemy.orm import class_mapper
from dotenv import load_dotenv

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

from config import Config  # noqa: E402
from app.core.extensions import db  # noqa: E402
from app.core import models  # noqa: E402

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
    'ChapterMode': models.ChapterMode,
    'QuizMode': models.QuizMode,
    'FlashcardMode': models.FlashcardMode,
    'ChatMode': models.ChatMode,
    'User': models.User,
    'Installation': models.Installation,
    'TelemetryLog': models.TelemetryLog,
    'Feedback': models.Feedback,
    'LLMPerformance': models.LLMPerformance,
    'PlanRevision': models.PlanRevision,
    'Login': models.Login
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
      nav { margin-bottom: 20px; display: flex; align-items: center; gap: 15px; }
      nav a { text-decoration: none; color: #66b0ff; }
      nav a:hover { text-decoration: underline; }
      table { border-collapse: collapse; width: 100%; border: 1px solid #444; }
      th, td { border: 1px solid #444; padding: 8px; text-align: left; vertical-align: top; }
      th { background-color: #333; color: #fff; cursor: pointer; user-select: none; }
      th:hover { background-color: #444; }
      th.sorted-asc::after { content: " ▲"; color: #00C9FF; }
      th.sorted-desc::after { content: " ▼"; color: #00C9FF; }
      
      tr:nth-child(even) { background-color: #252525; }
      tr.selected { background-color: rgba(0, 201, 255, 0.2) !important; }
      
      pre { margin: 0; white-space: pre-wrap; font-size: 0.9em; color: #ccc; }
      
      .btn-danger {
          background-color: #d9534f; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 4px;
      }
      .btn-danger:hover { background-color: #c9302c; }
      
      .bulk-actions { margin-bottom: 15px; display: none; }
      .bulk-actions.visible { display: block; }
      
      .chat-message { margin-bottom: 5px; padding: 5px; border-radius: 4px; }
      .chat-role { font-weight: bold; font-size: 0.8em; margin-bottom: 2px; }
      .chat-role.user { color: #5cb85c; }
      .chat-role.assistant { color: #5bc0de; }
      .chat-role.system { color: #f0ad4e; }
      .chat-content { white-space: pre-wrap; }
    </style>
    <script>
    // helper for jinja to parsed json if needed, but jinja does it better server side
    </script>
  </head>
  <body>
    <h1>Database Viewer</h1>
    <nav>
        <a href="/db-viewer">Home</a>
        {% for name in models %}
            <a href="/db-viewer/{{ name }}" style="{% if name == current_model %}font-weight: bold; color: white; border-bottom: 2px solid #00C9FF;{% endif %}">{{ name }}</a>
        {% endfor %}
    </nav>
    
    {% if current_model %}
        <h2>{{ current_model }}</h2>
        
        <div class="bulk-actions" id="bulkActions">
            <form action="/db-viewer/{{ current_model }}/bulk_delete" method="post" onsubmit="return confirm('Delete selected items?');">
                <input type="hidden" name="ids[]" id="bulkDeleteInput">
                <button type="submit" class="btn-danger">Delete Selected (<span id="selectedCount">0</span>)</button>
            </form>
        </div>

        <div style="overflow-x: auto;">
            <table id="dataTable">
                <thead>
                    <tr>
                        <th style="width: 30px; text-align: center; cursor: default;" onclick="event.stopPropagation()">
                            <input type="checkbox" id="selectAll">
                        </th>
                        {% for header in headers %}
                            <th onclick="sortTable({{ loop.index }})">{{ header }}</th>
                        {% endfor %}
                        <th style="cursor: default;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in rows %}
                        <tr data-id="{{ row['_pk_value'] }}" onclick="toggleRow(event, this)">
                            <td style="text-align: center;" onclick="event.stopPropagation()">
                                <input type="checkbox" class="row-select" value="{{ row['_pk_value'] }}" onchange="updateBulkState()">
                            </td>
                            {% for col in columns %}
                                <td>
                                    {% if col == 'chat_history' and row[col] %}
                                        <div style="max-height: 300px; overflow-y: auto;">
                                            {% for msg in row[col] %}
                                                <div class="chat-message">
                                                    <div class="chat-role {{ msg.get('role', 'unknown') }}">{{ msg.get('role', 'unknown') }}</div>
                                                    <div class="chat-content">{{ msg.get('content', '') }}</div>
                                                </div>
                                            {% endfor %}
                                        </div>
                                    {% elif col in json_cols %}
                                        <div style="max-height: 200px; overflow-y: auto;">
                                            <pre>{{ row[col] | tojson(indent=2) }}</pre>
                                        </div>
                                    {% else %}
                                        {{ row[col] }}
                                    {% endif %}
                                </td>
                            {% endfor %}
                            <td onclick="event.stopPropagation()">
                                <form action="/db-viewer/{{ current_model }}/delete/{{ row['_pk_value'] }}" method="post" style="display:inline;" onsubmit="return confirm('Delete this item?');">
                                    <button type="submit" class="btn-danger">Delete</button>
                                </form>
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <script>
            let lastChecked = null;
            const rows = document.querySelectorAll('#dataTable tbody tr');
            const checkboxes = document.querySelectorAll('.row-select');
            const selectAll = document.getElementById('selectAll');
            
            // Row Click Handler (Ctrl/Shift Select)
            function toggleRow(e, row) {
                // Don't trigger if clicking inside button or link or checkbox container
                if (e.target.closest('button') || e.target.closest('a') || e.target.closest('input')) return;
                
                const checkbox = row.querySelector('.row-select');
                // Get current rows in current order (after sort)
                const currentRows = Array.from(document.querySelectorAll('#dataTable tbody tr'));
                
                // Handle Shift Click
                if (e.shiftKey && lastChecked) {
                    let start = currentRows.indexOf(row);
                    let end = currentRows.indexOf(lastChecked);
                    
                    const [lower, upper] = [Math.min(start, end), Math.max(start, end)];
                    
                    for (let i = lower; i <= upper; i++) {
                        const r = currentRows[i];
                        const cb = r.querySelector('.row-select');
                        cb.checked = lastChecked.querySelector('.row-select').checked;
                        toggleRowVisual(r, cb.checked);
                    }
                } else {
                    // Regular Click or Ctrl Click
                    // If Ctrl is NOT pressed, maybe we should clear others? 
                    // User asked for "multiple selections using Ctrl and Shift".
                    // Standard file manager behavior: Click = select one (clear others), Ctrl+Click = toggle one.
                    
                    if (!e.ctrlKey && !e.metaKey) {
                        // Clear all
                        checkboxes.forEach(cb => {
                            cb.checked = false;
                            toggleRowVisual(cb.closest('tr'), false);
                        });
                        checkbox.checked = true;
                    } else {
                        // Ctrl Click (Toggle)
                        checkbox.checked = !checkbox.checked;
                    }
                    toggleRowVisual(row, checkbox.checked);
                    lastChecked = row;
                }
                
                updateBulkState();
            }
            
            function toggleRowVisual(row, isSelected) {
                if (isSelected) row.classList.add('selected');
                else row.classList.remove('selected');
            }
            
            // Checkbox Change Handler (for direct clicks)
            checkboxes.forEach(cb => {
                cb.addEventListener('click', function(e) {
                     // Update visual
                     toggleRowVisual(this.closest('tr'), this.checked);
                     lastChecked = this.closest('tr');
                     updateBulkState();
                     e.stopPropagation(); // Prevent row click
                });
            });
            
            if (selectAll) {
                selectAll.addEventListener('change', function(e) {
                    checkboxes.forEach(cb => {
                        cb.checked = this.checked;
                        toggleRowVisual(cb.closest('tr'), this.checked);
                    });
                    updateBulkState();
                });
            }

            function updateBulkState() {
                const selected = Array.from(checkboxes).filter(cb => cb.checked);
                const count = selected.length;
                document.getElementById('selectedCount').innerText = count;
                
                const bulkActions = document.getElementById('bulkActions');
                if (count > 0) bulkActions.classList.add('visible');
                else bulkActions.classList.remove('visible');
                
                // Populate hidden input
                const ids = selected.map(cb => cb.value);
                const container = document.getElementById('bulkDeleteInput');
                // We need to append multiple inputs for form.getlist or use a simpler delimiter?
                // Flask getlist works with multiple inputs of same name.
                // Let's replace the single input logic.
                
                // Clear old inputs
                const form = container.form;
                // Remove existing hidden id inputs
                form.querySelectorAll('input[name="ids[]"]').forEach(el => {
                    if (el.type === 'hidden' && el !== container) el.remove();
                });
                
                // Add new ones
                ids.forEach(id => {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'ids[]';
                    input.value = id;
                    form.appendChild(input);
                });
            }
            
            // Sorting Logic
            function sortTable(n) {
                const table = document.getElementById("dataTable");
                let rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
                switching = true;
                dir = "asc"; 
                
                // Reset headers
                table.querySelectorAll('th').forEach(th => {
                   th.classList.remove('sorted-asc', 'sorted-desc'); 
                });
                
                while (switching) {
                    switching = false;
                    rows = table.rows;
                    for (i = 1; i < (rows.length - 1); i++) {
                        shouldSwitch = false;
                        x = rows[i].getElementsByTagName("TD")[n];
                        y = rows[i + 1].getElementsByTagName("TD")[n];
                        
                        let xVal = x.textContent.toLowerCase();
                        let yVal = y.textContent.toLowerCase();
                        
                        // Try numeric
                        if (!isNaN(parseFloat(xVal)) && isFinite(xVal)) {
                            xVal = parseFloat(xVal);
                            yVal = parseFloat(yVal);
                        }
                        
                        if (dir == "asc") {
                            if (xVal > yVal) { shouldSwitch = true; break; }
                        } else if (dir == "desc") {
                            if (xVal < yVal) { shouldSwitch = true; break; }
                        }
                    }
                    if (shouldSwitch) {
                        rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                        switching = true;
                        switchcount ++;      
                    } else {
                        if (switchcount == 0 && dir == "asc") {
                            dir = "desc";
                            switching = true;
                        }
                    }
                }
                
                const th = table.querySelectorAll('th')[n];
                th.classList.add(dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
            }
        </script>
    {% else %}
        <p>Select a table to view data.</p>
    {% endif %}
  </body>
</html>
"""

@app.route('/db-viewer/<model_name>/delete/<pk_value>', methods=['POST'])
def delete_item(model_name, pk_value):
    if model_name in MODELS:
        model = MODELS[model_name]
        mapper = class_mapper(model)
        pk_keys = [key.name for key in mapper.primary_key]
        if pk_keys:
            pk_name = pk_keys[0] # Assume single PK
            # Handle type conversion if necessary (e.g., int vs string)
            # SQLAlchemy might handle this, but let's be safe.
            # User uses string, others use int.
            # We can try to query directly.
            
            # Construct filter kwargs
            filter_args = {pk_name: pk_value}
            item = model.query.filter_by(**filter_args).first()
            if item:
                try:
                    db.session.delete(item)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    return f"Error deleting: {e}", 500
                    
        return redirect(f'/db-viewer/{model_name}')
    return "Model not found", 404

@app.route('/db-viewer/<model_name>/bulk_delete', methods=['POST'])
def bulk_delete_items(model_name):
    if model_name in MODELS:
        from flask import request
        model = MODELS[model_name]
        mapper = class_mapper(model)
        pk_keys = [key.name for key in mapper.primary_key]
        
        if not pk_keys:
             return "No PK found", 400
             
        pk_name = pk_keys[0]
        ids = request.form.getlist('ids[]')
        # Filter out empty strings that might come from template inputs
        ids = [x for x in ids if x.strip()]
        
        if ids:
            try:
                # Filter by list of IDs
                # We assume PK is the first key
                # filter_args = {pk_name: ids} # Unused
                # Using in_ for bulk delete
                # model.query.filter(getattr(model, pk_name).in_(ids)).delete(synchronize_session=False) ## This is faster
                # But let's stick to safe iteration for now to reuse logic or if cascade needed (though delete usually cascades)
                
                # Fetch and delete to handle potential complex relationships if needed (though batch is better)
                # Let's use batch delete
                model.query.filter(getattr(model, pk_name).in_(ids)).delete(synchronize_session=False)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                return f"Error deleting: {e}", 500
        
        return redirect(f'/db-viewer/{model_name}')
    return "Model not found", 404

@app.route('/db-viewer')
@app.route('/db-viewer/<model_name>')
def db_viewer(model_name=None):
    
    if model_name and model_name in MODELS:
        model = MODELS[model_name]
        mapper = class_mapper(model)
        columns = [c.name for c in mapper.columns]
        pk_keys = [key.name for key in mapper.primary_key]
        pk_name = pk_keys[0] if pk_keys else 'id'
        
        # Identify JSON columns for formatting
        json_cols = []
        for c in mapper.columns:
            if 'JSON' in str(c.type):
                json_cols.append(c.name)

        items = model.query.all()
        rows = []
        for item in items:
            row = {}
            for col in columns:
                val = getattr(item, col)
                row[col] = val
            # Add PK specifically for actions
            row['_pk_value'] = getattr(item, pk_name)
            rows.append(row)
            
        # Custom aliases for headers
        headers = []
        for c in columns:
            if c == 'time_spent':
                headers.append('time_spent (seconds)')
            else:
                headers.append(c)

        return render_template_string(VIEWER_HTML, 
                                      models=MODELS.keys(), 
                                      current_model=model_name, 
                                      columns=columns,  # Use original keys for data lookup
                                      headers=headers,  # Use aliases for display
                                      rows=rows,
                                      json_cols=json_cols)
    
    return render_template_string(VIEWER_HTML, models=MODELS.keys(), current_model=None)

# Redirect root to viewer for convenience in this standalone mode
@app.route('/')
def index():
    return render_template_string(VIEWER_HTML, models=MODELS.keys(), current_model=None)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database tables created/verified.")
    print("Starting DB Viewer on http://localhost:5012/")
    app.run(host='0.0.0.0', port=5012, debug=True)
