from flask import Blueprint

flashcard_bp = Blueprint(
    'flashcard',
    __name__,
    template_folder='templates',
    static_folder='static')

from . import routes  # noqa: E402, F401
