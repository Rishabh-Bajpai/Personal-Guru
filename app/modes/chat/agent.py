from app.common.utils import call_llm
from app.common.agents import ChatAgent
from app.modes.chat.prompts import (
    get_chat_system_message,
    get_welcome_prompt,
    get_chat_popup_system_message,
)


class ChatModeMainChatAgent(ChatAgent):
    """
    Main agent for handling chat interactions in the dedicated Chat mode.
    """

    def __init__(self):
        """Initializes the ChatModeMainChatAgent with the chat system message."""
        super().__init__(get_chat_system_message)

    def get_welcome_message(self, topic_name, user_background, plan=None):
        """
        Generates a personalized welcome message to start a chat session.

        Args:
            topic_name (str): The name of the topic.
            user_background (str): The background of the user.
            plan (list, optional): The current study plan.

        Returns:
            tuple: The welcome message string and an error object (or None).
        """
        # We override/implement this here since it's specific to the main chat
        # start
        prompt = get_welcome_prompt(topic_name, user_background, plan)
        answer = call_llm(prompt)
        return answer


class ChatModeChatPopupAgent(ChatAgent):
    """
    Agent for handling chat interactions specifically in Chat mode popup.
    """

    def __init__(self):
        """Initializes the ChatModeChatPopupAgent with the popup system message."""
        super().__init__(get_chat_popup_system_message)
