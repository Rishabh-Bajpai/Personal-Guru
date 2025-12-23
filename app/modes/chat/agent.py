import re
from app.core.agents import call_llm

class ChatAgent:
    def get_answer(self, question, context, user_background):
        prompt = f"""
You are a helpful teaching assistant. The user is asking a question about the following learning material.
Provide a concise and helpful answer to the user's question.
The user's background is: '{user_background}'
Learning Material: "{context}"

User's Question: "{question}"
"""
        answer, error = call_llm(prompt)
        if error:
            return f"Error getting answer from LLM: {error}", error

        # Filter out content within <think> tags
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()

        return answer, None
