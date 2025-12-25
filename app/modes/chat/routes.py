from flask import render_template, request, session, redirect, url_for
from . import chat_bp
from app.core.storage import load_topic, save_chat_history, save_topic
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

    # Try to load from DB first
    topic_data = load_topic(topic_name)
    if topic_data and topic_data.get('chat_history'):
        chat_history = topic_data['chat_history']
        session['chat_history'] = chat_history
    else:
        chat_history = session.get('chat_history', [])

    if not chat_history:
        # Generate welcome message if chat is new
        user_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
        
        # 1. Generate Plan if missing
        if not topic_data or not topic_data.get('plan'):
             from app.modes.chapter.agent import PlannerAgent
             planner = PlannerAgent()
             plan_steps, error = planner.generate_study_plan(topic_name, user_background)
             if not error:
                 # Save plan
                 if not topic_data: topic_data = {"name": topic_name}
                 topic_data['plan'] = plan_steps
                 # Initialize empty steps list to match plan length (required by storage logic)
                 topic_data['steps'] = [{} for _ in plan_steps]
                 save_topic(topic_name, topic_data)
                 # Reload to ensure consistency
                 topic_data = load_topic(topic_name)

        plan = topic_data.get('plan', []) if topic_data else []
        welcome_message, error = chat_agent.get_welcome_message(topic_name, user_background, plan)
        if error:
            # Handle error appropriately
            return f"<h1>Error</h1><p>Could not generate a welcome message: {welcome_message}</p>"

        chat_history.append({"role": "assistant", "content": welcome_message})
        session['chat_history'] = chat_history
        session.modified = True
        
        # Save to DB immediately so the topic is created and persisted
        save_chat_history(topic_name, chat_history)

    return render_template('chat/mode.html', topic_name=topic_name, chat_history=chat_history)

@chat_bp.route('/<topic_name>/send', methods=['POST'])
def send_message(topic_name):
    user_message = request.form.get('message')
    
    # Prevent empty or whitespace-only messages from being processed
    if not user_message or not user_message.strip():
        return redirect(url_for('chat.mode', topic_name=topic_name))

    topic_data = load_topic(topic_name)
    if topic_data:
        context = topic_data.get('description', f'The topic is {topic_name}')
        plan = topic_data.get('plan', [])
    else:
        context = f'The topic is {topic_name}. No additional details are available yet.'
        plan = []
    
    user_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))

    chat_history = session.get('chat_history', [])
    chat_history.append({"role": "user", "content": user_message})

    # Get answer from agent
    answer, error = chat_agent.get_answer(user_message, chat_history, context, user_background, plan)

    if error:
        # Add an error message to the chat instead of crashing
        chat_history.append({"role": "assistant", "content": f"Sorry, I encountered an error: {answer}"})
    else:
        chat_history.append({"role": "assistant", "content": answer})

    session['chat_history'] = chat_history
    session.modified = True  # Ensure Flask saves the updated list
    
    # Save to DB
    save_chat_history(topic_name, chat_history)

    return redirect(url_for('chat.mode', topic_name=topic_name))

@chat_bp.route('/<topic_name>/<int:step_index>', methods=['POST'])
def chat(topic_name, step_index):
    user_question = request.json.get('question')
    topic_data = load_topic(topic_name)

    if not user_question:
        return {"error": "Missing or empty question"}, 400

    if not topic_data:
        return {"error": "Topic not found"}, 400

    if 'steps' not in topic_data:
        return {"error": "Topic has no steps defined"}, 400

    if step_index < 0 or step_index >= len(topic_data['steps']):
        return {"error": "Step index out of range"}, 400
    current_step_data = topic_data['steps'][step_index]
    teaching_material = current_step_data.get('teaching_material', '')
    current_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
    # Pass an empty conversation history for the chapter mode chat
    answer, error = chat_agent.get_answer(user_question, [], teaching_material, current_background)

    if error:
        return {"error": answer}, 500

    return {"answer": answer}
