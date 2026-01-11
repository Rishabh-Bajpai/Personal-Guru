from flask import render_template, request, redirect, url_for
from . import chat_bp
from app.common.storage import load_topic, save_chat_history, save_topic
from app.common.agents import PlannerAgent
from app.common.utils import summarize_text
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

    chat_history = topic_data.get('chat_history') or [] if topic_data else []

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
    chat_history = topic_data.get('chat_history') or []

    system_message = f"Based on your feedback, I've updated the study plan. The new focus will be on: {', '.join(new_plan)}. Let's proceed with the new direction."
    chat_history.append({"role": "assistant", "content": system_message})
    save_chat_history(topic_name, chat_history)

    # Redirect back to the chat interface
    return redirect(url_for('chat.mode', topic_name=topic_name))


@chat_bp.route('/<topic_name>/send', methods=['POST'])
def send_message(topic_name):
    user_message = request.form.get('message')
    try:
        time_spent = int(request.form.get('time_spent', 0))
    except (ValueError, TypeError):
        time_spent = 0
    
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
    chat_history = (topic_data.get('chat_history') or []) if topic_data else []
    chat_history_summary = (topic_data.get('chat_history_summary') or []) if topic_data else []

    # Initialize summary if missing (for backward compatibility)
    if chat_history and not chat_history_summary:
        chat_history_summary = list(chat_history)

    # Add user message to both
    chat_history.append({"role": "user", "content": user_message.strip()})
    chat_history_summary.append({"role": "user", "content": user_message.strip()})

    # Construct context for LLM
    # We want last 2 interactions (4 messages) + current message from full history
    # And everything older from summary history.
    # Total recent messages = 4 (prev interactions) + 1 (current) = 5
    KEEP_FULL_COUNT = 5

    if len(chat_history) <= KEEP_FULL_COUNT:
        messages_for_llm = chat_history
    else:
        # Slicing:
        # Older = Summary[:-5]
        # Recent = Full[-5:]
        older_part = chat_history_summary[:-KEEP_FULL_COUNT]
        recent_part = chat_history[-KEEP_FULL_COUNT:]
        messages_for_llm = older_part + recent_part

    # Get answer from agent
    try:
        answer = chat_agent.get_answer(
            user_message, # passed for logic, but agent should use full history from msg
            messages_for_llm, # Passing constructed history
            context,
            user_background,
            plan)
        
        # Append full answer to full history
        chat_history.append({"role": "assistant", "content": answer})

        # Generate summary for the answer
        try:
            summary = summarize_text(answer)
            chat_history_summary.append({"role": "assistant", "content": summary})
        except Exception as e:
            # Fallback: just use full answer
            print(f"Failed to summarize answer: {e}")
            chat_history_summary.append({"role": "assistant", "content": answer})

    except Exception as error:
        # Add an error message to the chat instead of crashing
        error_msg = f"Sorry, I encountered an error: {error}"
        chat_history.append({"role": "assistant", "content": error_msg})
        chat_history_summary.append({"role": "assistant", "content": error_msg})

    save_chat_history(topic_name, chat_history, history_summary=chat_history_summary, time_spent=time_spent)

    return redirect(url_for('chat.mode', topic_name=topic_name))

@chat_bp.route('/<topic_name>/update_time', methods=['POST'])
def update_time(topic_name):
    try:
        time_spent = int(request.form.get('time_spent', 0))
    except (ValueError, TypeError):
        time_spent = 0
        
    if time_spent > 0:
        topic_data = load_topic(topic_name)
        if topic_data:
             chat_history = topic_data.get('chat_history') or []
             save_chat_history(topic_name, chat_history, time_spent=time_spent)
             
    return '', 204

@chat_bp.route('/<topic_name>/<int:step_index>', methods=['POST'])
def chat(topic_name, step_index):
    user_question = request.json.get('question')
    try:
        time_spent = int(request.json.get('time_spent', 0))
    except (ValueError, TypeError):
        time_spent = 0
    topic_data = load_topic(topic_name)

    if not user_question:
        return {"error": "Missing or empty question"}, 400

    if not topic_data:
        return {"error": "Topic not found"}, 400

    if step_index == 9999:
        # Chat Mode Popup Logic
        popup_history = topic_data.get('popup_chat_history') or []
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
        save_chat_history(topic_name, topic_data.get('chat_history', []), popup_history=popup_history)
        return {"answer": answer}

    if 'chapter_mode' not in topic_data:
        return {"error": "Topic has no steps defined"}, 400

    if step_index < 0 or step_index >= len(topic_data['chapter_mode']):
        return {"error": "Step index out of range"}, 400
    current_step_data = topic_data['chapter_mode'][step_index]
    teaching_material = current_step_data.get('teaching_material', '')

    # Load step-specific chat history
    step_history = current_step_data.get('popup_chat_history') or []
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
    current_step_data['popup_chat_history'] = step_history
    if time_spent:
         current_step_data['time_spent'] = (current_step_data.get('time_spent', 0) or 0) + int(time_spent)
    # We must save the whole topic to persist the step update
    save_topic(topic_name, topic_data)

    return {"answer": answer}
