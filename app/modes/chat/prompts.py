def get_chat_answer_prompt(question, context, user_background):
    return f"""
You are a helpful teaching assistant. The user is asking a question about the following learning material.
Provide a concise and helpful answer to the user's question.
The user's background is: '{user_background}'
Learning Material: "{context}"

User's Question: "{question}"
"""
