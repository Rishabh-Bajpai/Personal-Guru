from flask import render_template, request, session, redirect, url_for
from . import chat_bp
from app.core.storage import load_topic
from .agent import ChatAgent
import os

chat_agent = ChatAgent()

@chat_bp.route('/<topic_name>')
def mode(topic_name):
    # Ensure a clean slate for a new chat session topic
    # Reset chat history when switching topics
    if session.get('chat_topic') != topic_name:
        session.pop('chat_history', None)
        session['chat_topic'] = topic_name
        session.modified = True  # Required for Flask to detect mutable object changes

    chat_history = session.get('chat_history', [])

    if not chat_history:
        # Generate welcome message if chat is new
        user_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
        welcome_message, error = chat_agent.get_welcome_message(topic_name, user_background)
        if error:
            # Handle error appropriately
            return f"<h1>Error</h1><p>Could not generate a welcome message: {welcome_message}</p>"

        chat_history.append({"role": "assistant", "content": welcome_message})
        session['chat_history'] = chat_history
        session.modified = True

    return render_template('chat/mode.html', topic_name=topic_name, chat_history=chat_history)

@chat_bp.route('/<topic_name>/send', methods=['POST'])
def send_message(topic_name):
    user_message = request.form.get('message')
    if not user_message:
        return redirect(url_for('chat.mode', topic_name=topic_name))

    topic_data = load_topic(topic_name)
    if topic_data:
        context = topic_data.get('description', f'The topic is {topic_name}')
    else:
        context = f'The topic is {topic_name}. No additional details are available yet.'
    
    user_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))

    chat_history = session.get('chat_history', [])
    chat_history.append({"role": "user", "content": user_message})

    # Get answer from agent
    answer, error = chat_agent.get_answer(user_message, chat_history, context, user_background)

    if error:
        # Add an error message to the chat instead of crashing
        chat_history.append({"role": "assistant", "content": f"Sorry, I encountered an error: {answer}"})
    else:
        chat_history.append({"role": "assistant", "content": answer})

    session['chat_history'] = chat_history
    session.modified = True  # Ensure Flask saves the updated list

    return redirect(url_for('chat.mode', topic_name=topic_name))

@chat_bp.route('/<topic_name>/<int:step_index>', methods=['POST'])
def chat(topic_name, step_index):
    user_question = request.json.get('question')
    topic_data = load_topic(topic_name)

    if not user_question or not topic_data or 'steps' not in topic_data or step_index >= len(topic_data['steps']):
        return {"error": "Invalid request or topic data missing"}, 400

    current_step_data = topic_data['steps'][step_index]
    teaching_material = current_step_data.get('teaching_material', '')
    current_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
    # Pass an empty conversation history for the chapter mode chat
    answer, error = chat_agent.get_answer(user_question, [], teaching_material, current_background)

    if error:
        return {"error": answer}, 500

    return {"answer": answer}
