def get_quiz_generation_prompt(topic, count, user_background):
    return f"""
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

def get_quiz_count_prompt(topic, user_background):
    return f"""
Analyze the complexity of the topic '{topic}' for a user with background: '{user_background}'.
Based on the topic's breadth and depth, suggest an ideal number of quiz questions to generate for a comprehensive assessment.
Return a JSON object with a single key "count".
For a very simple topic, suggest 5-10 questions. For a moderately complex topic, 10-20. For a very complex topic, 20-30.
"""
