import os
import requests
import json
import re
from dotenv import load_dotenv

load_dotenv()

OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", 4096))

def _call_ollama(prompt, is_json=False):
    """A helper function to call the Ollama API."""
    if not OLLAMA_ENDPOINT or not OLLAMA_MODEL_NAME:
        return "Error: Ollama environment variables not set.", "Config Error"

    data = {
        "model": OLLAMA_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX
        }
    }
    if is_json:
        data["format"] = "json"

    try:
        api_url = f"{OLLAMA_ENDPOINT}/api/generate"
        print(f"Calling Ollama API (JSON: {is_json}): {api_url}")
        response = requests.post(api_url, json=data, timeout=300)
        response.raise_for_status()

        response_json = response.json()
        content = response_json.get("response", "")
        print(f"LLM Response: {content}")

        if is_json:
            # The content is a string of JSON, so parse it
            return json.loads(content), None
        return content, None

    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error calling Ollama or parsing JSON: {e}")
        return f"Error communicating with LLM: {e}", e

class PlannerAgent:
    def generate_study_plan(self, topic, user_background):
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
        plan_data, error = _call_ollama(prompt, is_json=True)
        if error:
            return plan_data, error

        plan_steps = plan_data.get("plan", [])
        if not plan_steps or not isinstance(plan_steps, list):
            return "Error: Could not parse study plan from LLM response.", "Invalid format"

        return plan_steps, None


class AssessorAgent:
    def generate_question(self, step_text):
        prompt = f"""
You are an expert assessor. Based on the following learning material, create between 1 and 5 concise multiple-choice questions to test understanding.
The number of questions should be appropriate for the length and complexity of the material.
Each question should have 4 options (A, B, C, D) and one correct answer.
Return a JSON object with a single key "questions", which is an array of question objects.
Each question object should have keys "question", "options" (an array of 4 strings), and "correct_answer" (the letter 'A', 'B', 'C', or 'D').

Learning Material: "{step_text}"

Example JSON response:
{{
  "questions": [
    {{
      "question": "What is the capital of France?",
      "options": ["London", "Berlin", "Paris", "Madrid"],
      "correct_answer": "C"
    }},
    {{
      "question": "What is the currency of Japan?",
      "options": ["Yen", "Won", "Yuan", "Dollar"],
      "correct_answer": "A"
    }}
  ]
}}
"""
        question_data, error = _call_ollama(prompt, is_json=True)
        if error:
            return question_data, error

        # Basic validation
        if "questions" not in question_data or not isinstance(question_data["questions"], list):
            return "Error: Invalid questions format from LLM.", "Invalid format"

        return question_data, None

class FeedbackAgent:
    def evaluate_answer(self, user_answer, correct_answer):
        """
        Evaluates if the user's answer is correct.
        In a real scenario, this could be an LLM call for more nuanced feedback.
        For this implementation, we'll do a simple check against the correct letter.
        """
        is_correct = str(user_answer).strip().upper() == str(correct_answer).strip().upper()
        if is_correct:
            feedback = "That's correct! Great job."
        else:
            feedback = f"Not quite. The correct answer was {correct_answer}. Keep trying!"

        return {"is_correct": is_correct, "feedback": feedback}, None

class ChatAgent:
    def get_answer(self, question, context):
        prompt = f"""
You are a helpful teaching assistant. The user is asking a question about the following learning material.
Provide a concise and helpful answer to the user's question.

Learning Material: "{context}"

User's Question: "{question}"
"""
        answer, error = _call_ollama(prompt)
        if error:
            return f"Error getting answer from LLM: {error}", error

        # Filter out content within <think> tags
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()

        return answer, None

class TopicTeachingAgent:
    def generate_teaching_material(self, topic, full_plan, incorrect_questions=None):
        incorrect_questions_text = "None"
        if incorrect_questions:
            incorrect_questions_text = "\n".join([f"- {q['question']}" for q in incorrect_questions])

        full_plan_text = "\n".join([f"- {step}" for step in full_plan])

        prompt = f"""
You are an expert teacher. Your role is to teach a topic in detail.
The full study plan is:
{full_plan_text}

The current topic is: "{topic}"

The user has previously answered the following questions incorrectly:
{incorrect_questions_text}

Based on the topic, the full study plan, and the user's incorrect answers, generate detailed teaching material for the current topic.
Avoid generating content that is covered in other steps of the plan.
The material should be comprehensive and include code examples where appropriate.
The output should be a single string of markdown-formatted text.
"""
        teaching_material, error = _call_ollama(prompt)
        if error:
            return teaching_material, error

        # Filter out content within <think> tags
        teaching_material = re.sub(r'<think>.*?</think>', '', teaching_material, flags=re.DOTALL).strip()

        return teaching_material, None
