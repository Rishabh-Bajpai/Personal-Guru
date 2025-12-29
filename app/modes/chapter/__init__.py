from flask import Blueprint

chapter_bp = Blueprint('chapter', __name__, template_folder='templates', static_folder='static')

from . import routes  # noqa: E402, F401
