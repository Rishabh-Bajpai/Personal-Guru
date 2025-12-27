from app.core.utils import call_llm
from app.core.agents import ChatAgent
from app.modes.chat.prompts import get_chat_system_message, get_welcome_prompt

class ChatModeMainChatAgent(ChatAgent):
    def __init__(self):
        super().__init__(get_chat_system_message)

    def get_welcome_message(self, topic_name, user_background, plan=None):
        # We override/implement this here since it's specific to the main chat start
        prompt = get_welcome_prompt(topic_name, user_background, plan)
        answer, error = call_llm(prompt)
        if error:
            return f"Error getting welcome message from LLM: {error}", error
        return answer, None

