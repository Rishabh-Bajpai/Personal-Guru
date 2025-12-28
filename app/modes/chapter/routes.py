from flask import render_template, request, session, redirect, url_for, make_response
from . import chapter_bp
from app.core.storage import load_topic, save_topic
from app.core.agents import FeedbackAgent, PlannerAgent
from .agent import ChapterTeachingAgent, AssessorAgent
from app.core.utils import generate_audio
from markdown_it import MarkdownIt
from weasyprint import HTML
import datetime
from app.core.agents import CodeExecutionAgent
from app.core.sandbox import Sandbox

# Instantiate agents
teacher = ChapterTeachingAgent()
planner = PlannerAgent()
assessor = AssessorAgent()
feedback_agent = FeedbackAgent()
md = MarkdownIt()

@chapter_bp.route('/<topic_name>')
def mode(topic_name):
    topic_data = load_topic(topic_name)
    
    # Initialize Persistent Sandbox
    sandbox_id = session.get('sandbox_id')
    # If exists, reuse. If None, create new.
    sandbox = Sandbox(sandbox_id=sandbox_id)
    session['sandbox_id'] = sandbox.id
    
    # If topic exists and has a plan, go directly to learning
    # If topic exists and has a plan, go directly to learning
    if topic_data and topic_data.get('plan'):
        # Resume logic: find the last step with content
        steps = topic_data.get('steps', [])
        resume_step_index = 0
        for i, step in enumerate(steps):
             # Check if step has content (teaching_material or questions)
             has_content = bool(step.get('teaching_material') or step.get('questions'))
             if has_content:
                 resume_step_index = i
        
        return redirect(url_for('chapter.learn_topic', topic_name=topic_name, step_index=resume_step_index))
    
    # No plan exists - generate one automatically
    from app.core.utils import get_user_context
    user_background = get_user_context()
    plan_steps, error = planner.generate_study_plan(topic_name, user_background)
    
    if error:
        return f"<h1>Error Generating Plan</h1><p>{plan_steps}</p>"
    
    # Save the new plan
    topic_data = topic_data or {"name": topic_name}
    topic_data['plan'] = plan_steps
    topic_data['steps'] = [{} for _ in plan_steps]
    save_topic(topic_name, topic_data)
    
    # Go directly to learning
    return redirect(url_for('chapter.learn_topic', topic_name=topic_name, step_index=0))

@chapter_bp.route('/generate', methods=['POST'])
def generate_plan():
    data = request.get_json()
    topic_name = data.get('topic')
    if not topic_name:
        return {"error": "Topic name required"}, 400
        
    from app.core.utils import get_user_context
    user_background = get_user_context()
    plan_steps, error = planner.generate_study_plan(topic_name, user_background)
    
    if error:
        return {"error": plan_steps}, 500
        
    topic_data = load_topic(topic_name) or {"name": topic_name}
    topic_data['plan'] = plan_steps
    # Initialize steps structure
    topic_data['steps'] = [{} for _ in plan_steps]
    
    save_topic(topic_name, topic_data)
    
    return {"status": "success", "plan": plan_steps}

@chapter_bp.route('/<topic_name>/update_plan', methods=['POST'])
def update_plan(topic_name):
    comment = request.form.get('comment')
    current_step_index = request.form.get('current_step_index', 0)
    
    if not comment or not comment.strip():
         return redirect(url_for('chapter.learn_topic', topic_name=topic_name, step_index=current_step_index))

    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    current_plan = topic_data.get('plan', [])
    from app.core.utils import get_user_context
    user_background = get_user_context()

    # Use the unified PlannerAgent
    new_plan, error = planner.update_study_plan(topic_name, user_background, current_plan, comment)

    if not error:
        # Smart Update: Preserve content for unchanged steps
        from app.core.utils import reconcile_plan_steps

        # Smart Update using helper
        topic_data['plan'] = new_plan
        topic_data['steps'] = reconcile_plan_steps(
            topic_data.get('steps', []),
            current_plan, # Original plan strings! We need them.
            new_plan
        )
        # Wait, reconcile_plan_steps signature: (current_steps, current_plan, new_plan)
        # I have current_plan already (line 94).
        
        save_topic(topic_name, topic_data)

    return redirect(url_for('chapter.learn_topic', topic_name=topic_name, step_index=0))

@chapter_bp.route('/learn/<topic_name>/<int:step_index>')
def learn_topic(topic_name, step_index):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    plan_steps = topic_data.get('plan', [])
    
    # If topic has no plan (quiz/flashcard only), redirect
    # Not needed after issue #28 is fixed, but keeping the commented logic for now
    # if not plan_steps:
    #     # Checking logic from app.py
    #     if 'flashcards' in topic_data and topic_data['flashcards']:
    #         return redirect(url_for('flashcard.mode', topic_name=topic_name)) # Adjusted endpoint name
    #     elif 'quiz' in topic_data:
    #         return redirect(url_for('quiz.mode', topic_name=topic_name)) # Adjusted endpoint name
    
    if not 0 <= step_index < len(plan_steps):
        return "Invalid step index", 404

    current_step_data = topic_data['steps'][step_index]

    if not current_step_data.get('teaching_material'):
        incorrect_questions = session.get('incorrect_questions')
        from app.core.utils import get_user_context
        current_background = get_user_context()
        teaching_material, error = teacher.generate_teaching_material(plan_steps[step_index], plan_steps, current_background, incorrect_questions)
        if error:
            return f"<h1>Error Generating Teaching Material</h1><p>{teaching_material}</p>"
        current_step_data['teaching_material'] = teaching_material
        from app.core.utils import get_user_context
        current_background = get_user_context()
        question_data, error = assessor.generate_question(teaching_material, current_background)
        if not error:
            current_step_data['questions'] = question_data

        save_topic(topic_name, topic_data)
        session.pop('incorrect_questions', None)

    show_assessment = current_step_data.get('questions') and not current_step_data.get('user_answers')
    return render_template('chapter/learn_step.html',
                           topic=topic_data,
                           step_index=step_index,
                           total_steps=len(plan_steps),
                           step_title=plan_steps[step_index],
                           step_content=current_step_data.get('teaching_material', ''),
                           question_data=current_step_data.get('questions', None),
                           show_assessment=show_assessment)

@chapter_bp.route('/assess/<topic_name>/<int:step_index>', methods=['POST'])
def assess_step(topic_name, step_index):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    current_step_data = topic_data['steps'][step_index]
    questions = current_step_data.get('questions', {}).get('questions', [])
    user_answers = [request.form.get(f'option_{i}') for i in range(len(questions))]

    num_correct = 0
    feedback_results = []
    incorrect_questions = []

    for i, question in enumerate(questions):
        user_answer = user_answers[i]

        if user_answer: # Only score answered questions
            feedback_data, _ = feedback_agent.evaluate_answer(question.get('correct_answer'), user_answer)
            if feedback_data['is_correct']:
                num_correct += 1
            else:
                incorrect_questions.append(question)
            feedback_results.append(feedback_data)

    current_step_data['user_answers'] = user_answers
    current_step_data['feedback'] = feedback_results

    answered_questions_count = len([ua for ua in user_answers if ua])
    score = (num_correct / answered_questions_count * 100) if answered_questions_count > 0 else 0
    current_step_data['score'] = score

    if score < 50 and incorrect_questions:
        session['incorrect_questions'] = incorrect_questions

    save_topic(topic_name, topic_data)

    if step_index == len(topic_data['plan']) - 1:
        return redirect(url_for('chapter.complete_topic', topic_name=topic_name))

    return render_template('chapter/feedback.html',
                           feedback_results=feedback_results,
                           score=score,
                           topic=topic_data,
                           step_index=step_index,
                           next_step_index=step_index + 1,
                           total_steps=len(topic_data['plan']))

@chapter_bp.route('/reset_quiz/<topic_name>/<int:step_index>', methods=['POST'])
def reset_quiz(topic_name, step_index):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404
    
    if 0 <= step_index < len(topic_data['steps']):
        current_step_data = topic_data['steps'][step_index]
        if 'user_answers' in current_step_data:
            del current_step_data['user_answers']
        if 'feedback' in current_step_data:
            del current_step_data['feedback']
        if 'score' in current_step_data:
            del current_step_data['score']
        save_topic(topic_name, topic_data)
        
    return redirect(url_for('chapter.learn_topic', topic_name=topic_name, step_index=step_index))

@chapter_bp.route('/generate-audio/<int:step_index>', methods=['POST'])
def generate_audio_route(step_index):
    teaching_material = request.json.get('text')
    if not teaching_material:
        return {"error": "No text provided"}, 400

    audio_filename, error = generate_audio(teaching_material, step_index)
    if error:
        print(f"DEBUG: Audio Generation Error for step {step_index}: {error}")
        return {"error": str(error)}, 500

    # Assuming audio is saved to app/static
    audio_url = url_for('static', filename=audio_filename)
    return {"audio_url": audio_url}

@chapter_bp.route('/complete/<topic_name>')
def complete_topic(topic_name):
    topic_data, average_score = _get_topic_data_and_score(topic_name)
    if not topic_data:
        return "Topic not found", 404
    # Template was moved to app/templates/complete.html (global?)
    # Request said complete.html is GLOBAL TEMPLATE. So generic render_template 'complete.html'
    return render_template('complete.html', topic_name=topic_name, average_score=average_score)

@chapter_bp.route('/export/<topic_name>')
def export_topic(topic_name):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    markdown_content = f"# {topic_name}\n\n"
    for i, step_data in enumerate(topic_data['steps']):
        markdown_content += f"## {topic_data['plan'][i]}\n\n"
        markdown_content += step_data.get('teaching_material', '') + "\n\n"

    response = make_response(markdown_content)
    response.headers["Content-Disposition"] = f"attachment; filename={topic_name}.md"
    response.headers["Content-Type"] = "text/markdown"
    return response

@chapter_bp.route('/export/<topic_name>/pdf')
def export_topic_pdf(topic_name):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    # Prioritize Chapter/Quiz export if plan exists
    if topic_data.get('plan'):
        # Render chapter/quiz as PDF
        average_score = 0
        topic_data, average_score = _get_topic_data_and_score(topic_name) # Reuse helper
        html = render_template('chapter/pdf_export.html', topic=topic_data, average_score=average_score)
        
    # Fallback to Flashcards if no plan but flashcards exist
    elif topic_data.get('flashcards'):
        html = render_template('flashcard/export.html', topic_name=topic_name, flashcards=topic_data.get('flashcards', []))
    else:
        return "No content to export", 404
        # Render chapter/quiz as PDF
        average_score = 0
        topic_data, average_score = _get_topic_data_and_score(topic_name) # Reuse helper
        
        html = render_template('chapter/pdf_export.html', topic=topic_data, average_score=average_score)
    
    pdf = HTML(string=html).write_pdf(
        document_metadata={
            'title': topic_name,
            'created': datetime.date.today().isoformat()
        }
    )

    response = make_response(pdf)
    response.headers["Content-Disposition"] = f"attachment; filename={topic_name}.pdf"
    response.headers["Content-Type"] = "application/pdf"
    return response


code_agent = CodeExecutionAgent()

@chapter_bp.route('/execute_code', methods=['POST'])
def execute_code():
    data = request.json
    code = data.get('code')
    
    if not code:
        return {"error": "No code provided"}, 400

    # 1. Enhance code
    enhanced_data = code_agent.enhance_code(code)
    enhanced_code = enhanced_data.get('code')
    dependencies = enhanced_data.get('dependencies', [])
    
    # 2. Run in Sandbox
    sandbox_id = session.get('sandbox_id')
    sandbox = Sandbox(sandbox_id=sandbox_id)
    
    # Ensure ID is in session (if it was lost or new)
    if not sandbox_id:
         session['sandbox_id'] = sandbox.id
         
    try:
        # Install deps (basic caching could be used here in future)
        if dependencies:
            sandbox.install_deps(dependencies)
            
        result = sandbox.run_code(enhanced_code)
        
        return {
            "output": result.get('output'),
            "error": result.get('error'),
            "images": result.get('images', []), # List of base64 strings
            "enhanced_code": enhanced_code
        }
    finally:
        # Do persistent cleanup later
        pass

def _get_topic_data_and_score(topic_name):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return None, 0

    total_score = 0
    answered_questions = 0
    for step in topic_data['steps']:
        if 'teaching_material' in step:
            step['teaching_material'] = md.render(step['teaching_material'])
        if 'score' in step and step.get('user_answers'):
            total_score += step['score']
            answered_questions += 1

    average_score = (total_score / answered_questions) if answered_questions > 0 else 0
    return topic_data, average_score
