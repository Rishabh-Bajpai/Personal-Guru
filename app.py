import os
import urllib.parse
import uuid
from flask import Flask, render_template, request, url_for, session, redirect, make_response
from dotenv import load_dotenv, set_key, find_dotenv
import requests
from weasyprint import HTML
import datetime
from markdown_it import MarkdownIt

# Import the agents
from src.agents import PlannerAgent, AssessorAgent, FeedbackAgent, ChatAgent, TopicTeachingAgent, QuizAgent
from src.storage import save_topic, load_topic, get_all_topics, delete_topic

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Instantiate the agents
planner = PlannerAgent()
assessor = AssessorAgent()
feedback_agent = FeedbackAgent()
chat_agent = ChatAgent()
teacher = TopicTeachingAgent()
quiz_agent = QuizAgent()
md = MarkdownIt()

# Ensure the static directory exists
if not os.path.exists('static'):
    os.makedirs('static')

# The generate_audio and transcribe_audio functions can remain in app.py
# as they are more like utility functions than agents.
def generate_audio(text, step_index, tts_engine="coqui"):
    """
    Generates audio from text using the specified TTS engine.
    """
    # Clean up old audio files
    for filename in os.listdir('static'):
        if filename.endswith('.wav'):
            os.remove(os.path.join('static', filename))

    output_filename = os.path.join("static", f"step_{step_index}.wav")
    server_url = os.getenv("TTS_URL")
    if not server_url:
        return None, "Coqui TTS URL not set."

    encoded_text = urllib.parse.quote(text)
    speaker_id = "p278"
    url = f"{server_url}?text={encoded_text}&speaker_id={speaker_id}"

    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(output_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return output_filename, None
    except requests.exceptions.RequestException as e:
        return None, f"Error calling Coqui TTS: {e}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        topic_name = request.form.get('topic', '').strip()
        mode = request.form.get('mode', 'chapter')

        if not topic_name:
            topics = get_all_topics()
            topics_data = []
            for topic in topics:
                data = load_topic(topic)
                if data:
                    has_plan = bool(data.get('plan'))
                    topics_data.append({'name': topic, 'has_plan': has_plan})
                else:
                    topics_data.append({'name': topic, 'has_plan': True})
            return render_template('index.html', topics=topics_data, error="Please enter a topic name.")

        # If user selected a non-chapter learning mode, show the appropriate selector or mode page.
        if mode and mode != 'chapter':
            if mode == 'quiz':
                # Show quiz question count selector
                return render_template('quiz_select.html', topic_name=topic_name)
            topic_data = load_topic(topic_name) or {}
            flashcards = topic_data.get('flashcards', [])

            # Expect templates named like 'chat_mode.html', 'quiz_mode.html', etc.
            try:
                return render_template(f"{mode}_mode.html", topic_name=topic_name, flashcards=flashcards)
            except Exception:
                # Fallback: render index with an error message
                return render_template('index.html', topics=get_all_topics(), error=f"Mode {mode} not available")
        mode = request.form.get('mode', 'chapter')
        user_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
        print(f"DEBUG: User background in index: {user_background}")

        if mode == 'chapter':
            # Check if topic already exists
            if load_topic(topic_name):
                return redirect(url_for('learn_topic', topic_name=topic_name, step_index=0))

            # Use the PlannerAgent to generate the study plan
            plan_steps, error = planner.generate_study_plan(topic_name, user_background)
            if error:
                return f"<h1>Error Generating Plan</h1><p>{plan_steps}</p>"

            topic_data = {
                "name": topic_name,
                "plan": plan_steps,
                "steps": [{} for _ in plan_steps]
            }
            save_topic(topic_name, topic_data)

            return redirect(url_for('learn_topic', topic_name=topic_name, step_index=0))
        else:
            render_template(f'{mode}_mode.html')

    topics = get_all_topics()
    # Load topic data to determine which mode to use for each
    topics_data = []
    for topic in topics:
        data = load_topic(topic)
        if data:
            has_plan = bool(data.get('plan'))
            has_flashcards = bool(data.get('flashcards'))
            has_quiz = bool(data.get('quiz'))
            topics_data.append({
                'name': topic,
                'has_plan': has_plan,
                'has_flashcards': has_flashcards,
                'has_quiz': has_quiz
            })
        else:
            topics_data.append({'name': topic, 'has_plan': True, 'has_flashcards': False, 'has_quiz': False})
    
    return render_template('index.html', topics=topics_data)

@app.route('/background', methods=['GET', 'POST'])
def set_background():
    if request.method == 'POST':
        session['user_background'] = request.form['user_background']
        set_key(find_dotenv(), "USER_BACKGROUND", session['user_background'])
        return redirect(url_for('index'))

    current_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
    return render_template('background.html', user_background=current_background)

@app.route('/flashcard_mode/<topic_name>')
def flashcard_mode(topic_name):
    """Display flashcard mode with saved flashcards or generation UI."""
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404
    
    flashcards = topic_data.get('flashcards', [])
    return render_template('flashcard_mode.html', topic_name=topic_name, flashcards=flashcards)

@app.route('/learn/<topic_name>/<int:step_index>')
def learn_topic(topic_name, step_index):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    plan_steps = topic_data.get('plan', [])
    
    # If topic has no plan (quiz/flashcard only), redirect to appropriate mod
    if not plan_steps:
        if 'flashcards' in topic_data and topic_data['flashcards']:
            return redirect(url_for('flashcard_mode', topic_name=topic_name))
        elif 'quiz' in topic_data:
            return redirect(url_for('quiz_mode', topic_name=topic_name))
    
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
    return render_template('learn_step.html',
                           topic=topic_data,
                           step_index=step_index,
                           total_steps=len(plan_steps),
                           step_title=plan_steps[step_index],
                           step_content=current_step_data.get('teaching_material', ''),
                           question_data=current_step_data.get('questions', None),
                           show_assessment=show_assessment)

@app.route('/assess/<topic_name>/<int:step_index>', methods=['POST'])
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
        return redirect(url_for('complete_topic', topic_name=topic_name))

    return render_template('feedback.html',
                           feedback_results=feedback_results,
                           score=score,
                           topic=topic_data,
                           step_index=step_index,
                           next_step_index=step_index + 1,
                           total_steps=len(topic_data['plan']))

@app.route('/generate-audio/<int:step_index>', methods=['POST'])
def generate_audio_route(step_index):
    teaching_material = request.json.get('text')
    if not teaching_material:
        return {"error": "No text provided"}, 400

    audio_path, error = generate_audio(teaching_material, step_index)
    if error:
        return {"error": str(error)}, 500

    audio_url = url_for('static', filename=os.path.basename(audio_path))
    return {"audio_url": audio_url}


@app.route('/flashcards/generate', methods=['POST'])
def generate_flashcards_route():
    data = request.get_json() or {}
    topic_name = data.get('topic')
    count = data.get('count', 'auto')

    if not topic_name:
        return {"error": "No topic provided"}, 400

    user_background = os.getenv('USER_BACKGROUND', 'a beginner')

    # Determine flashcard count
    if isinstance(count, str) and count.lower() == 'auto':
        num, error = teacher.get_flashcard_count_for_topic(topic_name, user_background=user_background)
        if error:
            # Log the error and proceed with a default
            print(f"Error getting flashcard count: {error}")
            num = 25
    else:
        try:
            num = int(count)
        except (ValueError, TypeError):
            num = 25

    user_background = os.getenv('USER_BACKGROUND', 'a beginner')

    cards, error = teacher.generate_flashcards(topic_name, count=num, user_background=user_background)
    if error:
        return {"error": cards}, 500

    # Persist flashcards
    topic_data = load_topic(topic_name) or {"name": topic_name, "plan": [], "steps": []}
    topic_data['flashcards'] = cards
    save_topic(topic_name, topic_data)

    return {"flashcards": cards}

@app.route('/chat/<topic_name>/<int:step_index>', methods=['POST'])
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

@app.route('/complete/<topic_name>')
def complete_topic(topic_name):
    topic_data, average_score = _get_topic_data_and_score(topic_name)
    if not topic_data:
        return "Topic not found", 404

    return render_template('complete.html', topic_name=topic_name, average_score=average_score)

@app.route('/export/<topic_name>')
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

@app.route('/export/<topic_name>/pdf')
def export_topic_pdf(topic_name):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    # Check if this is a flashcard topic or a chapter topic
    if topic_data.get('flashcards'):
        # Render flashcards as PDF
        html = render_template('flashcard_export_template.html', topic_name=topic_name, flashcards=topic_data.get('flashcards', []))
    else:
        # Render chapter/quiz as PDF
        average_score = 0
        if topic_data.get('steps'):
            total_score = 0
            answered_questions = 0
            for step in topic_data['steps']:
                if 'teaching_material' in step:
                    step['teaching_material'] = md.render(step['teaching_material'])
                if 'score' in step and step.get('user_answers'):
                    total_score += step['score']
                    answered_questions += 1
            average_score = (total_score / answered_questions) if answered_questions > 0 else 0
        
        html = render_template('pdf_export_template.html', topic=topic_data, average_score=average_score)
    
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

@app.route('/delete/<topic_name>')
def delete_topic_route(topic_name):
    delete_topic(topic_name)
    return redirect(url_for('index'))

@app.route('/quiz/generate/<topic_name>/<count>', methods=['GET', 'POST'])
def generate_quiz(topic_name, count):
    """Generate a quiz with the specified number of questions and save it."""
    user_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
    
    # Handle 'auto' or numeric count
    if count.lower() != 'auto':
        try:
             count = int(count)
        except ValueError:
             count = 10 # Default fallback
             
    quiz_data, error = quiz_agent.generate_quiz(topic_name, user_background, count=count)

    if error:
        return f"<h1>Error Generating Quiz</h1><p>{quiz_data}</p>"

    # Save quiz to topic data
    topic_data = load_topic(topic_name) or {"name": topic_name, "plan": [], "steps": []}
    topic_data['quiz'] = quiz_data
    save_topic(topic_name, topic_data)

    session['quiz_questions'] = quiz_data.get('questions', [])
    return render_template('quiz_mode.html', topic_name=topic_name, quiz_data=quiz_data)

@app.route('/quiz/<topic_name>')
def quiz_mode(topic_name):
    """Load quiz from saved data or generate new one."""
    topic_data = load_topic(topic_name)
    
    # If quiz exists in saved data, use it
    if topic_data and 'quiz' in topic_data:
        quiz_data = topic_data['quiz']
        session['quiz_questions'] = quiz_data.get('questions', [])
        return render_template('quiz_mode.html', topic_name=topic_name, quiz_data=quiz_data)
    
    # Otherwise show the quiz count selector
    return render_template('quiz_select.html', topic_name=topic_name)

@app.route('/quiz/<topic_name>/submit', methods=['POST'])
def submit_quiz(topic_name):
    user_answers_indices = [request.form.get(f'answers_{i}') for i in range(len(session.get('quiz_questions', [])))]
    questions = session.get('quiz_questions', [])
    num_correct = 0
    feedback_results = []

    for i, question in enumerate(questions):
        user_answer_index = user_answers_indices[i]

        feedback_data, _ = feedback_agent.evaluate_answer(question, user_answer_index, answer_is_index=True)

        if feedback_data['is_correct']:
            num_correct += 1

        # Get the full text for user and correct answers for display
        correct_answer_letter = question.get('correct_answer')
        correct_answer_index = ord(correct_answer_letter.upper()) - ord('A')
        correct_answer_text = question['options'][correct_answer_index]

        user_answer_text = "No answer"
        if user_answer_index is not None:
            try:
                user_answer_text = question['options'][int(user_answer_index)]
            except (ValueError, IndexError):
                user_answer_text = "Invalid answer"

        feedback_results.append({
            'question': question.get('question'),
            'user_answer': user_answer_text,
            'correct_answer': correct_answer_text,
            'feedback': feedback_data['feedback'],
            'is_correct': feedback_data['is_correct']
        })

    score = (num_correct / len(questions) * 100) if questions else 0
    
    # Store results in session for PDF export
    session['last_quiz_results'] = {
        'topic_name': topic_name,
        'score': score,
        'feedback_results': feedback_results,
        'date': datetime.date.today().isoformat()
    }
    
    session.pop('quiz_questions', None)
    return render_template('quiz_feedback.html',
                           topic_name=topic_name,
                           score=score,
                           feedback_results=feedback_results)

@app.route('/quiz/<topic_name>/export/pdf')
def export_quiz_pdf(topic_name):
    quiz_results = session.get('last_quiz_results')
    
    if not quiz_results or quiz_results.get('topic_name') != topic_name:
         return "No quiz results found for this topic", 404

    # Render a dedicated template for the PDF
    html = render_template('quiz_result_pdf.html', **quiz_results)
    
    pdf = HTML(string=html).write_pdf(
        document_metadata={
            'title': f"Quiz Results - {topic_name}",
            'created': quiz_results['date']
        }
    )

    response = make_response(pdf)
    response.headers["Content-Disposition"] = f"attachment; filename=quiz_results_{topic_name}.pdf"
    response.headers["Content-Type"] = "application/pdf"
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
