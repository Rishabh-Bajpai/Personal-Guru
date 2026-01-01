from app.core.utils import call_llm
from app.core.prompts import get_code_execution_prompt
import re
import json

class CodeExecutionAgent:
    """
    Agent responsible for preparing code snippets for execution.
    """
    def __init__(self):
        """Initializes the CodeExecutionAgent."""
        pass

    def enhance_code(self, original_code):
        """
        Enhances the code adding imports, visualization and ensuring runnability.
        Returns: { 'code': str, 'dependencies': list[str] }
        """
        prompt = get_code_execution_prompt(original_code)
        
        # Use call_llm utility
        # It returns (response_content, error)
        response, error = call_llm(prompt)
        
        if error:
            print(f"LLM Error in enhanced_code: {error}")
            return {"code": original_code, "dependencies": []}
        
        # Parse JSON from response
        try:
            # 1. Try to find JSON within markdown code blocks first (most reliable)
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if code_block_match:
                return json.loads(code_block_match.group(1))

            # 2. Fallback: Find the first valid JSON object structure using greedy match
            # Note: This might fail if there are trailing braces in the text, but it's a reasonable fallback
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data
            else:
                # Fallback if no JSON found
                return {"code": original_code, "dependencies": []}
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            return {"code": original_code, "dependencies": []}

class FeedbackAgent:
    """
    Agent responsible for evaluating user answers and providing feedback.
    """
    def evaluate_answer(self, question_obj, user_answer, answer_is_index=False):
        """
        Evaluates a user's answer against a question object.

        Args:
            question_obj (dict or str): The question object or string.
            user_answer (str or int): The user's answer.
            answer_is_index (bool): Whether the user_answer is an index (for multiple choice).

        Returns:
            tuple: A dictionary with 'is_correct' (bool) and 'feedback' (str), and an error object (or None).
        """
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
    """
    Base agent for generating teaching materials for a topic.
    """
    def generate_teaching_material(self, topic, **kwargs):
        """
        Base method for generating teaching material.
        Subclasses should implement this method.
        """
        raise NotImplementedError("Subclasses must implement generate_teaching_material")


class PlannerAgent:
    """
    Agent responsible for generating and updating study plans.
    """
    def generate_study_plan(self, topic, user_background):
        """
        Generates a study plan for a given topic and user background.

        Args:
            topic (str): The topic to study.
            user_background (str): The user's background information.

        Returns:
            tuple: A list of study steps (strings) and an error object (or None).
        """
        print(f"DEBUG: Generating study plan for user with background: {user_background}")
        from app.core.prompts import get_study_plan_prompt
        prompt = get_study_plan_prompt(topic, user_background)
        plan_data, error = call_llm(prompt, is_json=True)
        if error:
            return plan_data, error

        plan_steps = plan_data.get("plan", [])
        if not plan_steps or not isinstance(plan_steps, list):
            return "Error: Could not parse study plan from LLM response (missing or invalid 'plan' key).", "Invalid format"

        if not all(isinstance(step, str) and step.strip() for step in plan_steps):
            return "Error: Could not parse study plan from LLM response (plan contains invalid steps).", "Invalid format"

        return plan_steps, None

    def update_study_plan(self, topic_name, user_background, current_plan, comment):
        """
        Updates an existing study plan based on user feedback.

        Args:
            topic_name (str): The name of the topic.
            user_background (str): The user's background.
            current_plan (list): The current list of study steps.
            comment (str): The user's feedback or request for change.

        Returns:
            tuple: The updated list of steps and an error object (or None).
        """
        from app.core.prompts import get_plan_update_prompt
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

class ChatAgent:
    """
    Agent responsible for handling chat interactions.
    """
    def __init__(self, system_message_generator):
        """
        Initializes the ChatAgent.

        Args:
            system_message_generator (callable): A function that generates the system message.
        """
        self.system_message_generator = system_message_generator

    def get_welcome_message(self, topic_name, user_background, plan=None):
        # This might be mode specific, but for now we can keep it generic 
        # or require a welcome_prompt_generator. 
        # Let's assume the subclass might override or we use a standard one.
        # For now, let's keep the existing logic found in chat/agent.py 
        # but we might need to import the prompt.
        # To avoid circular imports, maybe we pass the welcome prompt function too?
        # For this refactor, let's just use the one from chat prompts as default or 
        # expect the subclass to handle it if it differs.
        
        # Actually, the user requirement is about 'get_answer' using distinct prompts.
        # We will implement get_answer here using the generator.
        pass

    def get_answer(self, question, conversation_history, context, user_background, plan=None):
        """
        Generates an answer to a user's question.

        Args:
            question (str): The user's question.
            conversation_history (list): List of previous messages.
            context (str): Context for the conversation.
            user_background (str): User's background info.
            plan (list, optional): The study plan.

        Returns:
            tuple: The generated answer string and an error object (or None).
        """
        # Determine if this is guided mode
        is_guided_mode = len(conversation_history) > 0

        system_message = self.system_message_generator(context, user_background, is_guided_mode, plan)
        
        messages = [{"role": "system", "content": system_message}]
        
        # Add history
        if conversation_history:
            messages.extend(conversation_history)
        
        # Ensure the user's question is included.
        if not conversation_history or conversation_history[-1].get('content') != question:
            messages.append({"role": "user", "content": question})

        answer, error = call_llm(messages)
        if error:
            return f"Error getting answer from LLM: {error}", error

        # Filter out content within <think> tags
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()
        
        # Filter out <tool_call> tags if present (cleanup artifact)
        answer = re.sub(r'<tool_call>.*?</tool_call>', '', answer, flags=re.DOTALL).strip()

        return answer, None

class SuggestionAgent:
    """
    Agent responsible for suggesting new topics.
    """
    def generate_suggestions(self, user_profile, past_topics):
        """
        Generates a list of suggested topics based on user profile and history.

        Args:
            user_profile (str): The user's profile description.
            past_topics (list): List of topics the user has already studied.

        Returns:
            tuple: A list of suggested topic strings and an error object (or None).
        """
        from app.core.prompts import get_topic_suggestions_prompt
        prompt = get_topic_suggestions_prompt(user_profile, past_topics)
        
        response, error = call_llm(prompt, is_json=True)
        if error:
            return [], error
            
        suggestions = response.get("suggestions", [])
        if not isinstance(suggestions, list):
             return [], "Invalid format from LLM"
             
        return suggestions, None
