import os
import json
from datetime import datetime
from app.core.agents import call_llm, validate_quiz_structure

class QuizAgent:
    def generate_quiz(self, topic, user_background, count=10):
        """
        Generate a quiz with the specified number of questions.
        count can be 'auto' (default 10), 25, or 50.
        """
        if isinstance(count, str) and count.lower() == 'auto':
            count, error = self.get_quiz_count_for_topic(topic, user_background)
            if error:
                 print(f"Error determining quiz count: {error}")
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
        quiz_data, error = call_llm(prompt, is_json=True)
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
        validation_error, error_type = validate_quiz_structure(quiz_data)
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

    def get_quiz_count_for_topic(self, topic, user_background=None):
        """
        Estimate the number of quiz questions needed for a topic based on its complexity.
        Returns (count, None) on success or (default_count, error) on failure.
        """
        if user_background is None:
            user_background = os.getenv("USER_BACKGROUND", "a beginner")

        prompt = f"""
Analyze the complexity of the topic '{topic}' for a user with background: '{user_background}'.
Based on the topic's breadth and depth, suggest an ideal number of quiz questions to generate for a comprehensive assessment.
Return a JSON object with a single key "count".
For a very simple topic, suggest 5-10 questions. For a moderately complex topic, 10-20. For a very complex topic, 20-30.
"""
        data, error = call_llm(prompt, is_json=True)
        if error:
            return 10, error

        if isinstance(data, dict) and 'count' in data and isinstance(data['count'], int):
            count = data['count']
            # Clamp the value to a reasonable range
            return max(5, min(30, count)), None

        return 10, "Invalid format from LLM"
