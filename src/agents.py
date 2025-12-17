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
            try:
                # First, try to parse the entire content as JSON
                return json.loads(content), None
            except json.JSONDecodeError:
                # If that fails, try to find a JSON object embedded in the text
                print("Failed to parse content directly, attempting to extract JSON object.")

                # Regex to find a JSON object within the text.
                match = re.search(r'\{.*\}', content, re.DOTALL)

                if match:
                    json_str = match.group(0)
                    try:
                        return json.loads(json_str), None
                    except json.JSONDecodeError as e_inner:
                        print(f"Failed to parse extracted JSON: {json_str}")
                        # Re-raise to be caught by the outer block
                        raise e_inner

                # If we can't find a JSON object, we have to give up.
                # Re-raise the original parsing error by raising a new one.
                raise json.JSONDecodeError("No JSON object found in response", content, 0)

        return content, None

    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error calling Ollama or parsing JSON: {e}")
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
        plan_data, error = _call_ollama(prompt, is_json=True)
        if error:
            return plan_data, error

        plan_steps = plan_data.get("plan", [])
        if not plan_steps or not isinstance(plan_steps, list):
            return "Error: Could not parse study plan from LLM response (missing or invalid 'plan' key).", "Invalid format"

        if not all(isinstance(step, str) and step.strip() for step in plan_steps):
            return "Error: Could not parse study plan from LLM response (plan contains invalid steps).", "Invalid format"

        return plan_steps, None

def _validate_assessment_structure(assessment_data):
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

def _validate_quiz_structure(quiz_data):
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

class AssessorAgent:
    def generate_question(self, step_text, user_background):
        prompt = f"""
You are an expert assessor. Based on the following learning material, create between 1 and 3 concise questions to test understanding.
The number of questions should be appropriate for the length and complexity of the material.
Return a JSON object with a single key "questions", which is an array of question objects.
Each question object should have keys "question" and "correct_answer".
The user's background is: '{user_background}'
Learning Material: "{step_text}"

Example JSON response:
{{
  "questions": [
    {{
      "question": "What is the primary function of the Flask `request` object?",
      "correct_answer": "To handle incoming HTTP requests and access data from them (like form data or query parameters)."
    }},
    {{
      "question": "In which directory should you place static files like CSS and JavaScript in a Flask project?",
      "correct_answer": "The 'static' directory."
    }}
  ]
}}
"""
        question_data, error = _call_ollama(prompt, is_json=True)
        if error:
            return question_data, error

        # Detailed validation of the assessment structure
        validation_error, error_type = _validate_assessment_structure(question_data)
        if validation_error:
            return validation_error, error_type

        return question_data, None

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
        feedback, error = _call_ollama(prompt)
        if error:
            # Fallback on LLM error
            return {"is_correct": False, "feedback": f"Not quite. The correct answer was {correct_answer_text}. Keep trying!"}, None

        feedback = re.sub(r'<think>.*?</think>', '', feedback, flags=re.DOTALL).strip()
        return {"is_correct": False, "feedback": feedback}, None

class ChatAgent:
    def get_answer(self, question, context, user_background):
        prompt = f"""
You are a helpful teaching assistant. The user is asking a question about the following learning material.
Provide a concise and helpful answer to the user's question.
The user's background is: '{user_background}'
Learning Material: "{context}"

User's Question: "{question}"
"""
        answer, error = _call_ollama(prompt)
        if error:
            return f"Error getting answer from LLM: {error}", error

        # Filter out content within <think> tags
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()

        return answer, None

class QuizAgent:
    def generate_quiz(self, topic, user_background, count=10):
        """
        Generate a quiz with the specified number of questions.
        count can be 'auto' (default 10), 25, or 50.
        """
        if isinstance(count, str) and count.lower() == 'auto':
            count = 10
        else:
            count = int(count) if count else 10
        
        prompt = f"""
You are an expert in creating educational quizzes. For the topic '{topic}', create a quiz with {count} multiple-choice questions.
The user's background is: '{user_background}'
Output ONLY a JSON object with a single key "questions", which is an array of question objects.
Each question object MUST have keys "question", "options" (an array of exactly 4 strings), and "correct_answer" (one of 'A', 'B', 'C', or 'D').
Do NOT include any explanatory text, preamble, or markdown code blocks. Return ONLY valid JSON.

Example JSON response:
{{
  "questions": [
    {{
      "question": "What will be the output of this C++ code?",
      "options": ["Compilation Error", "Runtime Error", "Hello, World!", "No Output"],
      "correct_answer": "C"
    }},
    {{
      "question": "Which of the following describes the difference between a reference and a pointer in C++?",
      "options": [
        "A reference is an alias for an existing variable, while a pointer is a variable that stores a memory address.",
        "A pointer is an alias for an existing variable, while a reference is a variable that stores a memory address.",
        "There is no difference.",
        "References and pointers cannot be used in C++."
      ],
      "correct_answer": "A"
    }}
  ]
}}

Now, generate a quiz with exactly {count} questions for the topic: '{topic}'.
"""
        quiz_data, error = _call_ollama(prompt, is_json=True)
        if error:
            # Save raw response for debugging
            timestamp = datetime.now().isoformat().replace(':', '-')
            debug_file = f"data/debug-quiz-{timestamp}.txt"
            try:
                with open(debug_file, 'w') as f:
                    f.write(f"Topic: {topic}\n")
                    f.write(f"User Background: {user_background}\n")
                    f.write(f"Requested Count: {count}\n")
                    f.write(f"Raw Response: {str(quiz_data)}\n")
                print(f"DEBUG: Saved raw LLM response to {debug_file}")
            except Exception as e:
                print(f"DEBUG: Failed to save debug file: {e}")
            
            return quiz_data, error

        # Attempt fallback parsing if the returned data is not in expected format
        if not isinstance(quiz_data, dict):
            print(f"DEBUG: quiz_data is not a dict, it's a {type(quiz_data)}")
            return "Error: Invalid quiz format from LLM (response is not a JSON object).", "Invalid format"

        # If 'questions' key is missing, try to find it in the response
        if "questions" not in quiz_data:
            print(f"DEBUG: 'questions' key not found. Available keys: {list(quiz_data.keys())}")
            # Try to find a list-like value that could be questions
            for k, v in quiz_data.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    if 'question' in v[0] and 'options' in v[0]:
                        print(f"DEBUG: Found questions under key '{k}'")
                        quiz_data['questions'] = v
                        break

        # Detailed validation of the quiz structure
        validation_error, error_type = _validate_quiz_structure(quiz_data)
        if validation_error:
            # Save raw response for debugging on validation failure
            timestamp = datetime.now().isoformat().replace(':', '-')
            debug_file = f"data/debug-quiz-{timestamp}.txt"
            try:
                with open(debug_file, 'w') as f:
                    f.write(f"Topic: {topic}\n")
                    f.write(f"User Background: {user_background}\n")
                    f.write(f"Requested Count: {count}\n")
                    f.write(f"Validation Error: {validation_error}\n")
                    f.write(f"Raw Data: {json.dumps(quiz_data, indent=2)}\n")
                print(f"DEBUG: Saved validation failure to {debug_file}")
            except Exception as e:
                print(f"DEBUG: Failed to save debug file: {e}")
            
            return validation_error, error_type

        return quiz_data, None

class TopicTeachingAgent:
    def generate_teaching_material(self, topic, full_plan, user_background, incorrect_questions=None):
        incorrect_questions_text = "None"
        if incorrect_questions:
            incorrect_questions_text = "\n".join([f"- {q['question']}" for q in incorrect_questions])

        full_plan_text = "\n".join([f"- {step}" for step in full_plan])

        prompt = f"""
You are an expert teacher. Your role is to teach a topic in detail.
The full study plan is:
{full_plan_text}
The user's background is: '{user_background}'
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

    def generate_flashcards(self, topic, count=50, user_background=None):
        """
        Generate `count` concise flashcards (term + short definition) for `topic`.
        Returns (list_of_flashcards, None) on success or (error_message, error) on failure.
        Expected return JSON from LLM: {"flashcards": [{"term": "...", "definition": "..."}, ...]}
        """
        if user_background is None:
            user_background = os.getenv("USER_BACKGROUND", "a beginner")

        prompt = f"""
You are an expert educator. Generate {count} concise flashcards for the topic '{topic}', tailored to a user with background: '{user_background}'.
Return a JSON object with key "flashcards" which is an array of objects with keys "term" and "definition".
Each definition should be one to two sentences maximum and focused on the most important concepts.
Don't include any extra commentary outside the JSON.
"""
        data, error = _call_ollama(prompt, is_json=True)
        if error:
            return data, error

        if not isinstance(data, dict) or 'flashcards' not in data or not isinstance(data['flashcards'], list):
            return "Error: Invalid flashcards format from LLM.", "Invalid format"

        # Defensive parsing and validation
        cards = []
        if 'flashcards' in data and isinstance(data['flashcards'], list):
            for c in data['flashcards']:
                if isinstance(c, dict):
                    term = c.get('term')
                    definition = c.get('definition')
                    if term and definition and isinstance(term, str) and isinstance(definition, str):
                        cards.append({'term': term.strip(), 'definition': definition.strip()})

        if not cards:
            return "Error: LLM returned no valid flashcards.", "Invalid format"

        # If LLM returned fewer cards than requested, attempt to generate the remainder
        # by asking for additional cards (avoid duplicates). Retry a few times.
        try_count = 0
        seen_terms = {c['term'].strip().lower() for c in cards}
        while len(cards) < count and try_count < 3:
            remaining = count - len(cards)
            try_count += 1
            extra_prompt = f"""
Generate {remaining} additional concise flashcards for the topic '{topic}', tailored to a user with background: '{user_background}'.
Do NOT repeat any of these terms: {', '.join(sorted(seen_terms))}.
Return a JSON object with key "flashcards" which is an array of objects with keys "term" and "definition".
"""
            extra_data, extra_err = _call_ollama(extra_prompt, is_json=True)
            if extra_err or not isinstance(extra_data, dict) or 'flashcards' not in extra_data:
                break

            added = 0
            for c in extra_data['flashcards']:
                if not isinstance(c, dict):
                    continue
                term = c.get('term')
                definition = c.get('definition')
                if not term or not definition:
                    continue
                key = term.strip().lower()
                if key in seen_terms:
                    continue
                cards.append({'term': term, 'definition': definition})
                seen_terms.add(key)
                added += 1
            if added == 0:
                # nothing new added; stop to avoid infinite loop
                break

        # Trim to requested count in case of over-generation
        if len(cards) > count:
            cards = cards[:count]

        return cards, None

    def get_flashcard_count_for_topic(self, topic, user_background=None):
        """
        Estimate the number of flashcards needed for a topic based on its complexity.
        Returns (count, None) on success or (default_count, error) on failure.
        """
        if user_background is None:
            user_background = os.getenv("USER_BACKGROUND", "a beginner")

        prompt = f"""
Analyze the complexity of the topic '{topic}' for a user with background: '{user_background}'.
Based on the topic's breadth and depth, suggest an ideal number of flashcards to generate for a comprehensive review.
Return a JSON object with a single key "count".
For a very simple topic, suggest 10-15 cards. For a moderately complex topic, 20-30. For a very complex topic, 40-50.
"""
        data, error = _call_ollama(prompt, is_json=True)
        if error:
            return 25, error  # Default on error

        if isinstance(data, dict) and 'count' in data and isinstance(data['count'], int):
            count = data['count']
            # Clamp the value to a reasonable range
            return max(10, min(50, count)), None

        return 25, "Invalid format from LLM"
