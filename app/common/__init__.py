from flask import Blueprint

# This __init__.py allows app/common to be treated as a Flask Blueprint.
# It is specifically required to serve the shared CSS/JS (static_folder) 
# and HTML templates (template_folder) that the chat popup needs.
common_bp = Blueprint('common', __name__, template_folder='templates', static_folder='static')
