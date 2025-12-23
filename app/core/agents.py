import os
import requests
import json
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

LLM_ENDPOINT = os.getenv("LLM_ENDPOINT")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", 4096))
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")

def call_llm(prompt, is_json=False):
    """
    A helper function to call the LLM API using OpenAI-compatible protocol.
    Works with OpenAI, Ollama, LMStudio, VLLM, etc.
    """
    if not LLM_ENDPOINT or not LLM_MODEL_NAME:
        return "Error: LLM environment variables not set.", "Config Error"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }

    # Ensure the endpoint targets the chat completion path if not provided
    # Standard OpenAI base is like 'https://api.openai.com/v1'
    # Users might provide 'http://localhost:11434/v1' or just 'http://localhost:11434'
    # We will try to be smart or strictly follow a convention. 
    # Convention: LLM_ENDPOINT should be the base URL ending in /v1 (or similar root).
    # We append /chat/completions.
    
    # However, to be robust against trailing slashes:
    base_url = LLM_ENDPOINT.rstrip('/')
    if not base_url.endswith('/v1'):
       # some users might just put the host.
       # For ollama: http://localhost:11434/v1/chat/completions is valid.
       # IF user put http://localhost:11434, we might need to append /v1 if it's missing?
       # Let's assume the user follows the instruction to provide base url.
       # But commonly for ollama, they might forget.
       if "11434" in base_url and "/v1" not in base_url:
           base_url += "/v1"
           
    api_url = f"{base_url}/chat/completions"

    try:
        print(f"Calling LLM: {api_url}")
        
        messages = [{"role": "user", "content": prompt}]
        
        data = {
            "model": LLM_MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
        }
        
        # Note: Ollama via OpenAI-compat supports 'json_object' in recent versions.
        # But standard prompt engineering is safer for broader compatibility unless we know the provider supports response_format.
        if is_json:
            # We can try hinting via valid OpenAI param content or just rely on prompt.
            # Uncomment below if using a provider that strictly needs it for JSON
            # data["response_format"] = {"type": "json_object"} 
            pass

        response = requests.post(api_url, headers=headers, json=data, timeout=300)
        response.raise_for_status()
        
        response_json = response.json()
        content = response_json['choices'][0]['message']['content']

        print(f"LLM Response: {content}")

        if is_json:
            # The content is a string of JSON, so parse it
            # Sometimes LLMs wrap in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            try:
                # First, try to parse the entire content as JSON
                return json.loads(content), None
            except json.JSONDecodeError:
                # If that fails, try to find a JSON object embedded in the text
                print("Failed to parse content directly, attempting to extract JSON object.")
                try:
                    # Regex to find a JSON object within the text.
                    # We match from the first { to the last }
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        return json.loads(json_str), None
                except json.JSONDecodeError:
                    pass
                
                # Parsing failed
                return f"Error parsing JSON from LLM response: {content[:100]}...", json.JSONDecodeError("Failed to parse", content, 0)

        return content, None

    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Error calling LLM or parsing JSON: {e}")
        return f"Error communicating with LLM: {e}", e

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
