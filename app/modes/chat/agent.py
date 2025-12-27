import re
from app.core.utils import call_llm

class ChatAgent:
    def get_welcome_message(self, topic_name, user_background, plan=None):
        from app.modes.chat.prompts import get_welcome_prompt
        prompt = get_welcome_prompt(topic_name, user_background, plan)
        answer, error = call_llm(prompt)
        if error:
            return f"Error getting welcome message from LLM: {error}", error
        return answer, None

    def update_study_plan(self, topic_name, user_background, current_plan, comment):
        from app.modes.chat.prompts import get_plan_update_prompt
        import ast

        prompt = get_plan_update_prompt(topic_name, user_background, current_plan, comment)
        response, error = call_llm(prompt)

        if error:
            return None, f"Error getting new plan from LLM: {error}"

        try:
            # Remove analysis block if present
            response = re.sub(r'<analysis>.*?</analysis>', '', response, flags=re.DOTALL)

            # Extract list from response if it contains other text
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                response = match.group(0)

            # The response is expected to be a string representation of a list
            new_plan = ast.literal_eval(response)
            if isinstance(new_plan, list):
                return new_plan, None
            else:
                return None, "LLM did not return a valid list for the new plan."
        except (ValueError, SyntaxError):
            return None, f"Could not parse the new plan from LLM response: {response}"

    def get_answer(self, question, conversation_history, context, user_background, plan=None):
        from app.modes.chat.prompts import get_chat_answer_prompt

        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history]) if conversation_history else "No history yet."

        prompt = get_chat_answer_prompt(question, history_str, context, user_background, len(conversation_history) > 0, plan)
        answer, error = call_llm(prompt)
        if error:
            return f"Error getting answer from LLM: {error}", error

        # Filter out content within <think> tags
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()

        return answer, None
