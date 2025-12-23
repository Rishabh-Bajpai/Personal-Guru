from app.core.utils import call_llm

class PlannerAgent:
    def generate_study_plan(self, topic, user_background):
        print(f"DEBUG: Generating study plan for user with background: {user_background}")
        prompt = f"""
You are an expert in creating personalized study plans. For the topic '{topic}', create a high-level learning plan with 4-7 manageable steps, depending on the complexity of the topic.
The user's background is: '{user_background}'
The output should be a JSON object with a single key "plan", which is an array of strings. Each string is a step in the learning plan.
Do not generate the content for each step, only the plan itself.

Example of a good plan for the topic 'Flask':
"Our Flask Learning Plan:

Introduction to Flask & Setup: What is Flask? Why use it? Setting up a Conda environment and installing Flask. (Today)
Your First Flask App: A basic "Hello, World!" application. Understanding routes and the app object.
Templates & Rendering: Using Jinja2 templates to separate logic from presentation. Passing data to templates.
Static Files: Serving CSS, JavaScript, and images.
Request Handling: Accessing data sent by the user (form data, URL parameters).
Forms & User Input: Working with HTML forms and validating user data.
Databases (SQLite): Connecting to a database and performing basic operations.
More Advanced Topics (Optional): User authentication, sessions, and scaling."

Now, generate a similar plan for the topic: '{topic}'.
"""
        plan_data, error = call_llm(prompt, is_json=True)
        if error:
            return plan_data, error

        plan_steps = plan_data.get("plan", [])
        if not plan_steps or not isinstance(plan_steps, list):
            return "Error: Could not parse study plan from LLM response (missing or invalid 'plan' key).", "Invalid format"

        if not all(isinstance(step, str) and step.strip() for step in plan_steps):
            return "Error: Could not parse study plan from LLM response (plan contains invalid steps).", "Invalid format"

        return plan_steps, None

def validate_assessment_structure(assessment_data):
    """Validates the structure of an assessment JSON object (free-form questions)."""
    if not assessment_data or "questions" not in assessment_data or not isinstance(assessment_data["questions"], list) or not assessment_data["questions"]:
        return "Error: Invalid assessment format from LLM (missing or empty 'questions' list).", "Invalid format"

    for q in assessment_data["questions"]:
        if not isinstance(q, dict):
            return "Error: Invalid assessment format from LLM (question is not a dictionary).", "Invalid format"

        if not all(k in q for k in ["question", "correct_answer"]):
            return "Error: Invalid assessment format from LLM (missing 'question' or 'correct_answer' keys).", "Invalid format"

        if not isinstance(q["question"], str) or not q["question"].strip():
            return "Error: Invalid assessment format from LLM (question text is empty).", "Invalid format"

        if not isinstance(q["correct_answer"], str) or not q["correct_answer"].strip():
            return "Error: Invalid assessment format from LLM (correct_answer is empty).", "Invalid format"

    return None, None

def validate_quiz_structure(quiz_data):
    """Validates the structure of a quiz JSON object."""
    if not quiz_data or "questions" not in quiz_data or not isinstance(quiz_data["questions"], list) or not quiz_data["questions"]:
        return "Error: Invalid quiz format from LLM (missing or empty 'questions' list).", "Invalid format"

    for q in quiz_data["questions"]:
        if not isinstance(q, dict):
            return "Error: Invalid quiz format from LLM (question is not a dictionary).", "Invalid format"

        if not all(k in q for k in ["question", "options", "correct_answer"]):
            return "Error: Invalid quiz format from LLM (missing keys in question object).", "Invalid format"

        if not isinstance(q["question"], str) or not q["question"].strip():
            return "Error: Invalid quiz format from LLM (question text is empty).", "Invalid format"

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            return "Error: Invalid quiz format from LLM (options is not a list of 4).", "Invalid format"

        if not all(isinstance(opt, str) and opt.strip() for opt in q["options"]):
            return "Error: Invalid quiz format from LLM (one or more options are empty).", "Invalid format"

        correct_answer = q.get("correct_answer", "")
        if not isinstance(correct_answer, str) or correct_answer.upper() not in ['A', 'B', 'C', 'D']:
            return "Error: Invalid quiz format from LLM (correct_answer is invalid).", "Invalid format"

    return None, None


class FeedbackAgent:
    def evaluate_answer(self, question_obj, user_answer, answer_is_index=False):
        # Handle free-form questions from the assessment feature
        if isinstance(question_obj, str):
            is_correct = str(user_answer).strip().upper() == str(question_obj).strip().upper()
            if is_correct:
                feedback = "That's correct! Great job."
            else:
                feedback = f"Not quite. The correct answer was {question_obj}. Keep trying!"
            return {"is_correct": is_correct, "feedback": feedback}, None

        # Handle multiple-choice questions from the quiz feature
        correct_answer_letter = question_obj.get('correct_answer')

        try:
            options = question_obj.get('options', [])
            question_text = question_obj.get('question')
            correct_answer_index = ord(correct_answer_letter.upper()) - ord('A')
            correct_answer_text = options[correct_answer_index]

            is_correct = False
            user_answer_text = "No answer"

            if user_answer is not None:
                if answer_is_index:
                    user_answer_index = int(user_answer)
                    is_correct = (user_answer_index == correct_answer_index)
                else: # answer is letter
                    is_correct = (str(user_answer).strip().upper() == str(correct_answer_letter).strip().upper())
                    user_answer_index = ord(str(user_answer).upper()) - ord('A')

                if 0 <= user_answer_index < len(options):
                    user_answer_text = options[user_answer_index]
                else:
                    user_answer_text = "Invalid answer"

        except (IndexError, TypeError, ValueError):
            return {"is_correct": False, "feedback": f"Not quite. The correct answer was {correct_answer_letter}. Keep trying!"}, None

        if is_correct:
            feedback = "That's correct! Great job."
            return {"is_correct": True, "feedback": feedback}, None

        prompt = f"""
You are an expert educator providing feedback on a quiz answer.
The user was asked the following question:
"{question_text}"

The correct answer is: "{correct_answer_text}"
The user incorrectly answered: "{user_answer_text}"

Please provide a concise, helpful explanation for why the user's answer is incorrect and why the correct answer is the right choice.
The explanation should be friendly and encouraging. Limit it to 2-4 sentences.
"""
        feedback, error = call_llm(prompt)
        if error:
            # Fallback on LLM error
            return {"is_correct": False, "feedback": f"Not quite. The correct answer was {correct_answer_text}. Keep trying!"}, None

        feedback = re.sub(r'<think>.*?</think>', '', feedback, flags=re.DOTALL).strip()
        return {"is_correct": False, "feedback": feedback}, None


class TopicTeachingAgent:
    def generate_teaching_material(self, topic, **kwargs):
        """
        Base method for generating teaching material.
        Subclasses should implement this method.
        """
        raise NotImplementedError("Subclasses must implement generate_teaching_material")
