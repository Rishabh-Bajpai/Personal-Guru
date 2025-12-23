import re
from app.core.utils import call_llm
from app.core.agents import validate_quiz_structure, TopicTeachingAgent

class ChapterTeachingAgent(TopicTeachingAgent):
    def generate_teaching_material(self, topic, full_plan, user_background=None, incorrect_questions=None, **kwargs):
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
        teaching_material, error = call_llm(prompt)
        if error:
            return teaching_material, error

        # Filter out content within <think> tags
        teaching_material = re.sub(r'<think>.*?</think>', '', teaching_material, flags=re.DOTALL).strip()

        return teaching_material, None

class AssessorAgent:
    def generate_question(self, step_text, user_background):
        prompt = f"""
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
        question_data, error = call_llm(prompt, is_json=True)
        if error:
            return question_data, error

        # Detailed validation of the assessment structure (reusing quiz validation logic as structure is now same)
        # We can implement a specific one or reuse _validate_quiz_structure if it fits
        # _validate_quiz_structure checks for 4 options and A-D answer. Perfect.
        # It is defined in this module, so we can call it directly.
        validation_error, error_type = validate_quiz_structure(question_data)
        if validation_error:
            # Fallback for old structure or retry could go here, but for now return error
            return validation_error, error_type

        return question_data, None
