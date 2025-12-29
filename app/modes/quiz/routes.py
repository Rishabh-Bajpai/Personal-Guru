from flask import render_template, request, session, make_response
from . import quiz_bp
from app.core.storage import load_topic, save_topic
from app.core.agents import FeedbackAgent
from .agent import QuizAgent
from weasyprint import HTML
import datetime

quiz_agent = QuizAgent()
feedback_agent = FeedbackAgent()

@quiz_bp.route('/generate/<topic_name>/<count>', methods=['GET', 'POST'])
def generate_quiz(topic_name, count):
    """Generate a quiz with the specified number of questions and save it."""
    from app.core.utils import get_user_context
    user_background = get_user_context()
    
    # Handle 'auto' or numeric count
    if count.lower() != 'auto':
        try:
             count = int(count)
        except ValueError:
             count = 10 
             
    quiz_data, error = quiz_agent.generate_quiz(topic_name, user_background, count=count)

    if error:
        return f"<h1>Error Generating Quiz</h1><p>{quiz_data}</p>"

    # Save quiz to topic data
    topic_data = load_topic(topic_name) or {"name": topic_name, "plan": [], "steps": []}
    topic_data['quiz'] = quiz_data
    save_topic(topic_name, topic_data)

    session['quiz_questions'] = quiz_data.get('questions', [])
    return render_template('quiz/mode.html', topic_name=topic_name, quiz_data=quiz_data)

@quiz_bp.route('/<topic_name>')
def mode(topic_name):
    """Load quiz from saved data or generate new one."""
    topic_data = load_topic(topic_name)
    
    # If quiz exists in saved data, use it
    if topic_data and topic_data.get('quiz'):
        quiz_data = topic_data['quiz']
        session['quiz_questions'] = quiz_data.get('questions', [])
        return render_template('quiz/mode.html', topic_name=topic_name, quiz_data=quiz_data)
    
    # Otherwise show the quiz count selector
    return render_template('quiz/select.html', topic_name=topic_name)

@quiz_bp.route('/<topic_name>/submit', methods=['POST'])
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
        
        # Robust handling of correct_answer_letter
        if correct_answer_letter:
             try:
                correct_answer_index = ord(correct_answer_letter.upper()) - ord('A')
                correct_answer_text = question['options'][correct_answer_index]
             except (ValueError, IndexError):
                correct_answer_text = "Unknown"
        else:
             correct_answer_text = "Unknown"

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
    
    # Store results in topic data (server-side)
    topic_data = load_topic(topic_name)
    if topic_data:
        topic_data['last_quiz_result'] = {
            'topic_name': topic_name,
            'score': score,
            'feedback_results': feedback_results,
            'date': datetime.date.today().isoformat()
        }
        
        # Ensure the score is also saved to the Quiz table
        if topic_data.get('quiz'):
            topic_data['quiz']['score'] = score

        save_topic(topic_name, topic_data)
    
    session.pop('quiz_questions', None)
    return render_template('quiz/feedback.html',
                           topic_name=topic_name,
                           score=score,
                           feedback_results=feedback_results)

@quiz_bp.route('/<topic_name>/export/pdf')
def export_quiz_pdf(topic_name):
    topic_data = load_topic(topic_name)
    quiz_results = topic_data.get('last_quiz_result') if topic_data else None
    
    if not quiz_results:
         return "No quiz results found for this topic", 404

    # Render a dedicated template for the PDF
    html = render_template('quiz/result_pdf.html', **quiz_results)
    
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
