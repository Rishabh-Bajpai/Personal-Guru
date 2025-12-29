from app.core.agents import ChatAgent, TopicTeachingAgent
from app.modes.chapter.prompts import get_chapter_system_message
import re
from app.core.utils import call_llm

class ChapterModeChatAgent(ChatAgent):
    """
    Agent for handling chat interactions specifically in Chapter mode.
    """
    def __init__(self):
        """Initializes the ChapterModeChatAgent with the chapter system message."""
        super().__init__(get_chapter_system_message)

class ChapterTeachingAgent(TopicTeachingAgent):
    """
    Agent responsible for generating teaching material for a specific chapter.
    """
    def generate_teaching_material(self, topic, full_plan, user_background, incorrect_questions=None):
        """
        Generates teaching material for the current topic.

        Args:
            topic (str): The current topic/chapter title.
            full_plan (list): The complete study plan.
            user_background (str): Background information of the user.
            incorrect_questions (list, optional): List of questions the user missed previously.

        Returns:
            tuple: The generated teaching material (markdown) and an error object (or None).
        """
        from app.modes.chapter.prompts import get_teaching_material_prompt
        prompt = get_teaching_material_prompt(topic, full_plan, user_background, incorrect_questions)
        teaching_material, error = call_llm(prompt)
        
        if error:
            return teaching_material, error

        # Filter out <think> tags
        teaching_material = re.sub(r'<think>.*?</think>', '', teaching_material, flags=re.DOTALL).strip()
        
        return teaching_material, None

class AssessorAgent:
    """
    Agent responsible for generating assessment questions based on teaching material.
    """
    def generate_question(self, teaching_material, user_background):
        """
        Generates assessment questions for the provided teaching material.

        Args:
            teaching_material (str): The material to base questions on.
            user_background (str): The background of the user.

        Returns:
            tuple: A dictionary containing questions and an error object (or None).
        """
        from app.modes.chapter.prompts import get_assessment_prompt
        prompt = get_assessment_prompt(teaching_material, user_background)
        question_data, error = call_llm(prompt, is_json=True)
        if error:
             return question_data, error
             
        # Validate structure (basic check)
        if not question_data or "questions" not in question_data:
             return "Invalid question format", "Format Error"
             
        return question_data, None
