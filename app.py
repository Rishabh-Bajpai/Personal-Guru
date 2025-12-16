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
from src.agents import PlannerAgent, AssessorAgent, FeedbackAgent, ChatAgent, TopicTeachingAgent
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
        topic_name = request.form['topic']
        mode = request.form.get('mode', 'chapter')

        # If user selected a non-chapter learning mode, show the placeholder page.
        if mode and mode != 'chapter':
            # Expect templates named like 'chat_mode.html', 'quiz_mode.html', etc.
            try:
                return render_template(f"{mode}_mode.html", topic_name=topic_name)
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
    return render_template('index.html', topics=topics)

@app.route('/background', methods=['GET', 'POST'])
def set_background():
    if request.method == 'POST':
        session['user_background'] = request.form['user_background']
        set_key(find_dotenv(), "USER_BACKGROUND", session['user_background'])
        return redirect(url_for('index'))

    current_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
    return render_template('background.html', user_background=current_background)

@app.route('/learn/<topic_name>/<int:step_index>')
def learn_topic(topic_name, step_index):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    plan_steps = topic_data['plan']
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
        correct_answer = question.get('correct_answer')

        if user_answer: # Only score answered questions
            feedback_data, _ = feedback_agent.evaluate_answer(user_answer, correct_answer)
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
    topic_data, average_score = _get_topic_data_and_score(topic_name)
    if not topic_data:
        return "Topic not found", 404

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
