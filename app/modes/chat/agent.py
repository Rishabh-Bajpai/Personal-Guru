from app.core.utils import call_llm
from app.core.agents import ChatAgent
from app.modes.chat.prompts import get_chat_system_message, get_welcome_prompt

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

