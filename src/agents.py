import os
import requests
import json
import re
from dotenv import load_dotenv

load_dotenv()

LLM_ENDPOINT = os.getenv("LLM_ENDPOINT")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", 4096))
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")

def _call_llm(prompt, is_json=False):
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
            
            return json.loads(content), None
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
        plan_data, error = _call_llm(prompt, is_json=True)
        if error:
            return plan_data, error

        plan_steps = plan_data.get("plan", [])
        if not plan_steps or not isinstance(plan_steps, list):
            return "Error: Could not parse study plan from LLM response.", "Invalid format"

        return plan_steps, None


class AssessorAgent:
    def generate_question(self, step_text, user_background):
        prompt = f"""
You are an expert assessor. Based on the following learning material, create between 1 and 5 concise multiple-choice questions to test understanding.
The number of questions should be appropriate for the length and complexity of the material.
Each question should have 4 options (A, B, C, D) and one correct answer.
Return a JSON object with a single key "questions", which is an array of question objects.
Each question object should have keys "question", "options" (an array of 4 strings), and "correct_answer" (the letter 'A', 'B', 'C', or 'D').
The user's background is: '{user_background}'
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
        question_data, error = _call_llm(prompt, is_json=True)
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
    def get_answer(self, question, context, user_background):
        prompt = f"""
You are a helpful teaching assistant. The user is asking a question about the following learning material.
Provide a concise and helpful answer to the user's question.
The user's background is: '{user_background}'
Learning Material: "{context}"

User's Question: "{question}"
"""
        answer, error = _call_llm(prompt)
        if error:
            return f"Error getting answer from LLM: {error}", error

        # Filter out content within <think> tags
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()

        return answer, None

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
        teaching_material, error = _call_llm(prompt)
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
        data, error = _call_llm(prompt, is_json=True)
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
            extra_data, extra_err = _call_llm(extra_prompt, is_json=True)
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
        data, error = _call_llm(prompt, is_json=True)
        if error:
            return 25, error  # Default on error

        if isinstance(data, dict) and 'count' in data and isinstance(data['count'], int):
            count = data['count']
            # Clamp the value to a reasonable range
            return max(10, min(50, count)), None

        return 25, "Invalid format from LLM"
