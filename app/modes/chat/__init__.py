from flask import Blueprint

chat_bp = Blueprint(
    'chat',
    __name__,
    template_folder='templates',
    static_folder='static')

from . import routes  # noqa: E402, F401
