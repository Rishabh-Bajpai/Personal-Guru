def get_feedback_prompt(question_text, correct_answer_text, user_answer_text):
    return f"""
You are an expert educator providing feedback on a quiz answer.
The user was asked the following question:
"{question_text}"

The correct answer is: "{correct_answer_text}"
The user incorrectly answered: "{user_answer_text}"

Please provide a concise, helpful explanation for why the user's answer is incorrect and why the correct answer is the right choice.
The explanation should be friendly and encouraging. Limit it to 2-4 sentences.
"""
