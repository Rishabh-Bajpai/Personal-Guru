from app.core.agents import ChatAgent, TopicTeachingAgent
from app.modes.chapter.prompts import get_chapter_system_message
import re
from app.core.utils import call_llm

class ChapterModeChatAgent(ChatAgent):
    def __init__(self):
        super().__init__(get_chapter_system_message)

class ChapterTeachingAgent(TopicTeachingAgent):
    def generate_teaching_material(self, topic, full_plan, user_background, incorrect_questions=None):
        from app.modes.chapter.prompts import get_teaching_material_prompt
        prompt = get_teaching_material_prompt(topic, full_plan, user_background, incorrect_questions)
        teaching_material, error = call_llm(prompt)
        
        if error:
            return teaching_material, error

        # Filter out <think> tags
        teaching_material = re.sub(r'<think>.*?</think>', '', teaching_material, flags=re.DOTALL).strip()
        
        return teaching_material, None

class AssessorAgent:
    def generate_question(self, teaching_material, user_background):
        from app.modes.chapter.prompts import get_assessment_prompt
        prompt = get_assessment_prompt(teaching_material, user_background)
        question_data, error = call_llm(prompt, is_json=True)
        if error:
             return question_data, error
             
        # Validate structure (basic check)
        if not question_data or "questions" not in question_data:
             return "Invalid question format", "Format Error"
             
        return question_data, None
