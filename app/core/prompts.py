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
