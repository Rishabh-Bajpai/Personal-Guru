from app.common.utils import call_llm, validate_quiz_structure


class QuizAgent:
    """
    Agent responsible for generating and determining the scope of quizzes.
    """

    def generate_quiz(self, topic, user_background, count=10):
        """
        Generates a quiz with a specific number of questions.

        Args:
            topic (str): The subject of the quiz.
            user_background (str): The user's background information.
            count (int or str): Number of questions to generate (default 10, or 'auto').

        Returns:
            tuple: A dictionary containing the quiz data and an error object (or None).
        """
        if isinstance(count, str) and count.lower() == 'auto':
            count = self.get_quiz_count_for_topic(
                topic, user_background)
        else:
            count = int(count) if count else 10

        from app.modes.quiz.prompts import get_quiz_generation_prompt
        prompt = get_quiz_generation_prompt(topic, count, user_background)
        quiz_data = call_llm(prompt, is_json=True)

        # Attempt fallback parsing if the returned data is not in expected
        # format
        if not isinstance(quiz_data, dict):
            from app.core.exceptions import LLMResponseError
            raise LLMResponseError("Invalid quiz format from LLM", error_code="LLM043")

        # If 'questions' key is missing, try to find it in the response
        if "questions" not in quiz_data:
            print(
                f"DEBUG: 'questions' key not found. Available keys: {list(quiz_data.keys())}")
            # Try to find a list-like value that could be questions
            for k, v in quiz_data.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    if 'question' in v[0] and 'options' in v[0]:
                        print(f"DEBUG: Found questions under key '{k}'")
                        quiz_data['questions'] = v
                        break

        # Detailed validation of the quiz structure
        validate_quiz_structure(quiz_data)

        return quiz_data

    def get_quiz_count_for_topic(self, topic, user_background=None):
        """
        Estimate the number of quiz questions needed for a topic based on its complexity.
        Returns (count, None) on success or (default_count, error) on failure.
        """
        if user_background is None:
            from app.common.utils import get_user_context
            user_background = get_user_context()

        from app.modes.quiz.prompts import get_quiz_count_prompt
        prompt = get_quiz_count_prompt(topic, user_background)
        try:
            data = call_llm(prompt, is_json=True)
        except Exception:
            return 10

        if isinstance(
                data,
                dict) and 'count' in data and isinstance(
                data['count'],
                int):
            count = data['count']
            # Clamp the value to a reasonable range
            return max(5, min(30, count))

        return 10
