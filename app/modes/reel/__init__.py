from flask import Blueprint

reel_bp = Blueprint('reel', __name__, template_folder='templates', static_folder='static', static_url_path='/reels/static')

from . import routes
