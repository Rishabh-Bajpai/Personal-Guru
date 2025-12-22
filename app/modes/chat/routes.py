from flask import render_template, request, session
from . import chat_bp
from app.core.storage import load_topic
from app.core.agents import ChatAgent
import os

chat_agent = ChatAgent()

@chat_bp.route('/<topic_name>/<int:step_index>', methods=['POST'])
def chat(topic_name, step_index):
    user_question = request.json.get('question')
    topic_data = load_topic(topic_name)

    if not user_question or not topic_data:
        return {"error": "Invalid request"}, 400

    current_step_data = topic_data['steps'][step_index]
    teaching_material = current_step_data.get('teaching_material', '')
    current_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
    answer, error = chat_agent.get_answer(user_question, teaching_material, current_background)

    if error:
        return {"error": answer}, 500

    return {"answer": answer}
