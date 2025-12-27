def get_feedback_prompt(question_text, correct_answer_text, user_answer_text):
    return f"""
You are an expert educator providing feedback on a quiz answer.
The user was asked the following question:
"{question_text}"

The correct answer is: "{correct_answer_text}"
The user incorrectly answered: "{user_answer_text}"

Please provide a concise, helpful explanation for why the user's answer is incorrect and why the correct answer is the right choice.
The explanation should be friendly and encouraging. Limit it to 2-4 sentences.
"""

def get_study_plan_prompt(topic, user_background):
    return f"""
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

def get_plan_update_prompt(topic_name, user_background, current_plan, comment):
    return f"""
You are an expert curriculum designer. Your task is to revise a study plan based on user feedback. Only change the parts of the plan that the user has requested to change.

Topic: {topic_name}
User's Background: {user_background}

Current Study Plan:
- {chr(10).join(f"- {step}" for step in current_plan)}

User's Feedback for Modification:
"{comment}"

    Based on the user's feedback, generate a revised, concise study plan as a Python list of strings.
    - Analyze the user's request in the <analysis> block.
- The output MUST be ONLY a Python list of strings. For example: ["Introduction to Core Concepts", "Advanced Topic A", "Practical Application B"]
- Do NOT add any introductory text or explanation outside the list.
- The number of steps in the plan should be between 3 and 7.
"""

def get_code_execution_prompt(code):
    return f"""
You are an expert Python coding assistant.
Your goal is to enhance the provided code snippet to make it runnable, robust, and visually appealing if it involves plots.

INPUT CODE:
```python
{code}
```

INSTRUCTIONS:
1. **Import Dependencies**: Ensure all necessary libraries (e.g., matplotlib, pandas, numpy) are imported.
2. **Error Handling**: Wrap the main logic in try-except blocks to print meaningful errors instead of crashing.
3. **Visualization**: If the code generates plots, ensure they are saved to a file or buffer if needed, or better yet, assume standard plt.show() works in the sandbox which captures stdout/images.
4. **Dependencies List**: Identify all external pip packages required.

OUTPUT FORMAT:
Return a strictly valid JSON object with the following structure:
{{
    "code": "The full enhanced python code string...",
    "dependencies": ["list", "of", "pip", "packages"]
}}
"""
