import re
from app.core.utils import call_llm, validate_quiz_structure
from app.core.agents import TopicTeachingAgent

class ChapterTeachingAgent(TopicTeachingAgent):
    def generate_teaching_material(self, topic, full_plan, user_background=None, incorrect_questions=None, **kwargs):
        incorrect_questions_text = "None"
        if incorrect_questions:
            incorrect_questions_text = "\n".join([f"- {q['question']}" for q in incorrect_questions])

        full_plan_text = "\n".join([f"- {step}" for step in full_plan])

        from app.modes.chapter.prompts import get_teaching_material_prompt
        prompt = get_teaching_material_prompt(topic, full_plan_text, user_background, incorrect_questions_text)
        teaching_material, error = call_llm(prompt)
        if error:
            return teaching_material, error

        # Filter out content within <think> tags
        teaching_material = re.sub(r'<think>.*?</think>', '', teaching_material, flags=re.DOTALL).strip()

        return teaching_material, None

class AssessorAgent:
    def generate_question(self, step_text, user_background):
        from app.modes.chapter.prompts import get_assessment_question_prompt
        prompt = get_assessment_question_prompt(step_text, user_background)
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


