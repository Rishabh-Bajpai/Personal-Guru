from app.core.utils import call_llm
import re

class FeedbackAgent:
    def evaluate_answer(self, question_obj, user_answer, answer_is_index=False):
        # Handle free-form questions from the assessment feature
        if isinstance(question_obj, str):
            is_correct = str(user_answer).strip().upper() == str(question_obj).strip().upper()
            if is_correct:
                feedback = "That's correct! Great job."
            else:
                feedback = f"Not quite. The correct answer was {question_obj}. Keep trying!"
            return {"is_correct": is_correct, "feedback": feedback}, None

        # Handle multiple-choice questions from the quiz feature
        correct_answer_letter = question_obj.get('correct_answer')

        try:
            options = question_obj.get('options', [])
            question_text = question_obj.get('question')
            correct_answer_index = ord(correct_answer_letter.upper()) - ord('A')
            correct_answer_text = options[correct_answer_index]

            is_correct = False
            user_answer_text = "No answer"

            if user_answer is not None:
                if answer_is_index:
                    user_answer_index = int(user_answer)
                    is_correct = (user_answer_index == correct_answer_index)
                else: # answer is letter
                    is_correct = (str(user_answer).strip().upper() == str(correct_answer_letter).strip().upper())
                    user_answer_index = ord(str(user_answer).upper()) - ord('A')

                if 0 <= user_answer_index < len(options):
                    user_answer_text = options[user_answer_index]
                else:
                    user_answer_text = "Invalid answer"

        except (IndexError, TypeError, ValueError):
            return {"is_correct": False, "feedback": f"Not quite. The correct answer was {correct_answer_letter}. Keep trying!"}, None

        if is_correct:
            feedback = "That's correct! Great job."
            return {"is_correct": True, "feedback": feedback}, None

        from app.core.prompts import get_feedback_prompt
        prompt = get_feedback_prompt(question_text, correct_answer_text, user_answer_text)
        feedback, error = call_llm(prompt)
        if error:
            # Fallback on LLM error
            return {"is_correct": False, "feedback": f"Not quite. The correct answer was {correct_answer_text}. Keep trying!"}, None

        feedback = re.sub(r'<think>.*?</think>', '', feedback, flags=re.DOTALL).strip()
        return {"is_correct": False, "feedback": feedback}, None


class TopicTeachingAgent:
    def generate_teaching_material(self, topic, **kwargs):
        """
        Base method for generating teaching material.
        Subclasses should implement this method.
        """
        raise NotImplementedError("Subclasses must implement generate_teaching_material")
