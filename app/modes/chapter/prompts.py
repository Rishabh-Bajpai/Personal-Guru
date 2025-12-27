def get_teaching_material_prompt(topic, full_plan_text, user_background, incorrect_questions_text):
    return f"""
You are an expert teacher. Your role is to teach a topic in detail.
The full study plan is:
{full_plan_text}
The user's background is: '{user_background}'
The current topic is: "{topic}"

The user has previously answered the following questions incorrectly:
{incorrect_questions_text}

Based on the topic, the full study plan, and the user's incorrect answers, generate detailed teaching material for the current topic.
Avoid generating content that is covered in other steps of the plan.
The material should be comprehensive and include python code examples with minimal dependencies/libraries where appropriate.
The output should be a single string of markdown-formatted text.
"""

def get_assessment_question_prompt(step_text, user_background):
    return f"""
You are an expert assessor. Based on the following learning material, create between 1 and 3 multiple-choice questions to test understanding.
The number of questions should be appropriate for the length and complexity of the material.
Return a JSON object with a single key "questions", which is an array of question objects.
Each question object MUST have keys:
- "question": string
- "options": array of 4 strings
- "correct_answer": string (one of 'A', 'B', 'C', 'D')

The user's background is: '{user_background}'
Learning Material: "{step_text}"

Example JSON response:
{{
  "questions": [
    {{
      "question": "What is the primary function of the Flask `request` object?",
      "options": [
        "To render HTML templates.",
        "To handle incoming HTTP requests and access data.",
        "To connect to the database.",
        "To serve static files."
      ],
      "correct_answer": "B"
    }}
  ]
}}
"""


CODE_EXECUTION_PROMPT = """
You are a Python expert. Your task is to take a user-provided code snippet and transform it into a complete, runnable, and visually appealing script.

Original Code:
```python
{code}
```

Instructions:
1.  **Completeness**: Add any missing imports. Ensure the code is self-contained, and error free. and use minimal dependencies/libraries.
2.  **Visualization**:
    *   If the code involves data or math, use `matplotlib` or `seaborn` to create a plot.
    *   **Crucial**: Save the plot to a file named 'plot.png' using `plt.savefig('plot.png')`. Do NOT use `plt.show()`.
    *   Ensure the plot has a title, labels, and a legend if applicable.
3.  **Refinement**: Improve the code structure and add comments. Print meaningful output to stdout.
4.  **Dependencies**: List any external/extra libraries required to run the code (e.g., 'matplotlib', 'numpy').

Response Format:
You MUST return ONLY a valid JSON object with the following structure:
{{
    "code": "The complete python script as a string",
    "dependencies": ["list", "of", "libraries"]
}}
"""
