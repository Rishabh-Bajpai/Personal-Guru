from flask import render_template, request, redirect, url_for
from . import chat_bp
from app.common.storage import load_topic, save_chat_history, save_topic
from app.common.agents import PlannerAgent
from app.modes.chat.agent import ChatModeMainChatAgent, ChatModeChatPopupAgent
from app.modes.chapter.agent import ChapterModeChatAgent

chat_agent = ChatModeMainChatAgent()
chapter_agent = ChapterModeChatAgent()
popup_agent = ChatModeChatPopupAgent()


@chat_bp.route('/<topic_name>')
def mode(topic_name):
    # Try to load from DB first
    topic_data = load_topic(topic_name)
    if not topic_data:
        topic_data = {"name": topic_name}
        save_topic(topic_name, topic_data)
        topic_data = load_topic(topic_name)

    chat_history = topic_data.get('chat_history', []) if topic_data else []

    if not chat_history:
        # Generate welcome message if chat is new
        from app.common.utils import get_user_context
        user_background = get_user_context()

        # 1. Generate Plan if missing
        if not topic_data or not topic_data.get('plan'):
            planner = PlannerAgent()
            try:
                plan_steps = planner.generate_study_plan(
                    topic_name, user_background)
            except Exception:
                # Error will be caught by global handler
                raise

            # Save plan
            if not topic_data:
                topic_data = {"name": topic_name}
            topic_data['plan'] = plan_steps
            # Initialize empty steps list to match plan length (required by
            # storage logic)
            topic_data['steps'] = [{} for _ in plan_steps]
            save_topic(topic_name, topic_data)
            # Reload to ensure consistency
            topic_data = load_topic(topic_name)

        plan = topic_data.get('plan', []) if topic_data else []
        try:
            welcome_message = chat_agent.get_welcome_message(
                topic_name, user_background, plan)
        except Exception as error:
            # Handle error appropriately using a proper error template
            return render_template('error.html', error=str(error))

        chat_history.append({"role": "assistant", "content": welcome_message})

        # Save to DB immediately so the topic is created and persisted
        save_chat_history(topic_name, chat_history)

    # Always load plan to pass to the template
    topic_data = load_topic(topic_name)
    plan = topic_data.get('plan', []) if topic_data else []

    return render_template(
        'chat/mode.html',
        topic_name=topic_name,
        chat_history=chat_history,
        plan=plan)


@chat_bp.route('/<topic_name>/update_plan', methods=['POST'])
def update_plan(topic_name):
    comment = request.form.get('comment')
    if not comment or not comment.strip():
        return redirect(url_for('chat.mode', topic_name=topic_name))

    topic_data = load_topic(topic_name)
    if not topic_data:
        # Handle case where topic doesn't exist
        return redirect(url_for('chat.mode', topic_name=topic_name))

    current_plan = topic_data.get('plan', [])
    from app.common.utils import get_user_context
    user_background = get_user_context()

    planner = PlannerAgent()
    # Call agent to get a new plan
    try:
        new_plan = planner.update_study_plan(
            topic_name, user_background, current_plan, comment)
    except Exception:
        # Error will be caught by global handler
        raise

    from app.common.utils import reconcile_plan_steps

    # Save the new plan
    topic_data['plan'] = new_plan

    # Sync steps with new plan
    current_steps = topic_data.get('steps', [])
    # Note: Chat mode might not have loaded 'steps' if it wasn't accessed via load_topic deeply?
    # load_topic DOES load steps.

    topic_data['steps'] = reconcile_plan_steps(
        current_steps, current_plan, new_plan)

    save_topic(topic_name, topic_data)

    # Add a system message to the chat
    # Reload history from DB to be safe
    topic_data = load_topic(topic_name)
    chat_history = topic_data.get('chat_history', [])

    system_message = f"Based on your feedback, I've updated the study plan. The new focus will be on: {', '.join(new_plan)}. Let's proceed with the new direction."
    chat_history.append({"role": "assistant", "content": system_message})
    save_chat_history(topic_name, chat_history)

    # Redirect back to the chat interface
    return redirect(url_for('chat.mode', topic_name=topic_name))


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

    from app.common.utils import get_user_context
    user_background = get_user_context()

    # Load history from DB
    chat_history = topic_data.get('chat_history', []) if topic_data else []
    chat_history.append({"role": "user", "content": user_message.strip()})

    # Get answer from agent
    try:
        answer = chat_agent.get_answer(
            user_message,
            chat_history,
            context,
            user_background,
            plan)
        chat_history.append({"role": "assistant", "content": answer})
    except Exception as error:
        # Add an error message to the chat instead of crashing
        chat_history.append(
            {"role": "assistant", "content": f"Sorry, I encountered an error: {error}"})

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

    if step_index == 9999:
        # Chat Mode Popup Logic
        popup_history = topic_data.get('popup_chat_history', [])
        popup_history.append({"role": "user", "content": user_question})

        from app.common.utils import get_user_context
        user_background = get_user_context()

        # Context for Chat Mode popup is general topic context
        context = topic_data.get('description', f'The topic is {topic_name}')
        plan = topic_data.get('plan', [])

        try:
            answer = popup_agent.get_answer(
                user_question,
                popup_history,
                context,
                user_background,
                plan
            )
        except Exception as error:
            return {"error": str(error)}, 500

        popup_history.append({"role": "assistant", "content": answer})
        topic_data['popup_chat_history'] = popup_history
        save_topic(topic_name, topic_data)
        return {"answer": answer}

    if 'steps' not in topic_data:
        return {"error": "Topic has no steps defined"}, 400

    if step_index < 0 or step_index >= len(topic_data['steps']):
        return {"error": "Step index out of range"}, 400
    current_step_data = topic_data['steps'][step_index]
    teaching_material = current_step_data.get('teaching_material', '')

    # Load step-specific chat history
    step_history = current_step_data.get('chat_history', [])
    step_history.append({"role": "user", "content": user_question})

    from app.common.utils import get_user_context
    current_background = get_user_context()

    # Pass the history to the agent.
    # Note: We pass 'plan=[]' effectively because chapter mode context is the
    # teaching material itself.
    try:
        answer = chapter_agent.get_answer(
            user_question,
            conversation_history=step_history,
            context=teaching_material,
            user_background=current_background,
            plan=[],
        )
    except Exception as error:
        return {"error": str(error)}, 500

    # Append assistant answer
    step_history.append({"role": "assistant", "content": answer})

    # Save back to topic data
    current_step_data['chat_history'] = step_history
    # We must save the whole topic to persist the step update
    save_topic(topic_name, topic_data)

    return {"answer": answer}
