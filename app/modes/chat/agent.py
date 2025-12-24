import re
from app.core.utils import call_llm

class ChatAgent:
    def get_answer(self, question, context, user_background):
        from app.modes.chat.prompts import get_chat_answer_prompt
        prompt = get_chat_answer_prompt(question, context, user_background)
        answer, error = call_llm(prompt)
        if error:
            return f"Error getting answer from LLM: {error}", error

        # Filter out content within <think> tags
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()

        return answer, None
