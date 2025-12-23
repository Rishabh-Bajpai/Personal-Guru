from flask import render_template, request, session, redirect, url_for, make_response
from . import chapter_bp
from app.core.storage import load_topic, save_topic
from app.core.agents import FeedbackAgent
from .agent import ChapterTeachingAgent, AssessorAgent
from app.core.utils import generate_audio
from markdown_it import MarkdownIt
from weasyprint import HTML
import datetime
import os
import urllib.parse

# Instantiate agents
teacher = ChapterTeachingAgent()
assessor = AssessorAgent()
feedback_agent = FeedbackAgent()
md = MarkdownIt()

@chapter_bp.route('/learn/<topic_name>/<int:step_index>')
def learn_topic(topic_name, step_index):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    plan_steps = topic_data.get('plan', [])
    
    # If topic has no plan (quiz/flashcard only), redirect
    if not plan_steps:
        # Checking logic from app.py
        if 'flashcards' in topic_data and topic_data['flashcards']:
            return redirect(url_for('flashcard.mode', topic_name=topic_name)) # Adjusted endpoint name
        elif 'quiz' in topic_data:
            return redirect(url_for('quiz.mode', topic_name=topic_name)) # Adjusted endpoint name
    
    if not 0 <= step_index < len(plan_steps):
        return "Invalid step index", 404

    current_step_data = topic_data['steps'][step_index]

    if 'teaching_material' not in current_step_data:
        incorrect_questions = session.get('incorrect_questions')
        current_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
        teaching_material, error = teacher.generate_teaching_material(plan_steps[step_index], plan_steps, current_background, incorrect_questions)
        if error:
            return f"<h1>Error Generating Teaching Material</h1><p>{teaching_material}</p>"
        current_step_data['teaching_material'] = teaching_material
        current_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
        question_data, error = assessor.generate_question(teaching_material, current_background)
        if not error:
            current_step_data['questions'] = question_data

        save_topic(topic_name, topic_data)
        session.pop('incorrect_questions', None)

    show_assessment = 'questions' in current_step_data and 'user_answers' not in current_step_data
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

    # Check if this is a flashcard topic or a chapter topic
    if topic_data.get('flashcards'):
        # Render flashcards as PDF
        # Template moved to app/modes/flashcard/templates/flashcard/export.html ?
        # Wait, app.py had 'flashcard_export_template.html'. I moved it to ...
        # logic for flashcard export is in flashcard route? No, app.py had it here.
        # But if we split, flashcard PDF export should arguably be in Flashcard Blueprint.
        # However, keeping it here for now if the endpoint is /export/...
        # But cleanest is to move flashcard export to flashcard_bp.
        # I will redirect or handle here. Since the route is /export/<topic>/pdf, it implies generic ownership.
        # But I'll assume Chapter BP handles "General Topic Export".
        
        # But render_template('flashcard/export.html') requires cross-bp template?
        # Flask looks in all template folders. So it works.
        html = render_template('flashcard/export.html', topic_name=topic_name, flashcards=topic_data.get('flashcards', []))
    else:
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
