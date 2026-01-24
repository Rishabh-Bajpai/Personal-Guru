def get_chapter_popup_system_message(
        context,
        user_background,
        is_guided_mode,
        plan=None):
    """
    Returns a system message for the Chapter Mode side-chat.
    Focuses on concise, direct answers based on the teaching material.
    """

    base_prompt = f"""
You are an expert Tutor assisting a student with a specific learning module.
Your goal is to answer questions about the current content concisely and directly.

The user's background is: '{user_background}'.
The current learning material is:
"{context}"

INSTRUCTIONS:
1. **Be Concise**: Keep answers short and to the point. Avoid long paragraphs.
2. **Study Plan Updates**: If the user requests to change, update, or modify the study plan, you must inform them that you cannot update the plan yourself. Instruct them to use the "Modify the Plan" side panel to update the study plan.
3. **Context First**: Answer based primarily on the provided learning material content.
4. **Directness**: Do not use "Certainly!" or "Here is the answer". Just answer.
5. **No Artifacts**: Do not output internal thought processes, pig tags, or <think> tags. Output ONLY the answer.
6. **Formatting**: You can use bullet points for lists, but keep them compact.
7. **No Code**: Do not output code.

"""
    return base_prompt


def get_teaching_material_prompt(
        topic,
        full_plan,
        user_background,
        incorrect_questions=None):
    """
    Generate a prompt for creating detailed teaching material.

    Args:
        topic: Current study topic.
        full_plan: List of all steps in the plan.
        user_background: User's knowledge level/background.
        incorrect_questions: Optional list of previously failed questions.

    Returns:
        str: Detailed prompt for the LLM.
    """
    prompt = f"""
You are an expert tutor. Your role is to teach a topic in detail.
The current topic is: "{topic}"
The user's background is: "{user_background}".
FULL STUDY PLAN CONTEXT:
{chr(10).join([f"- {s}" for s in full_plan])}

INSTRUCTIONS:
1. Based on the topic, the full study plan, and the user's incorrect answers (if any), generate detailed teaching material for the current topic.
2. Avoid generating content that is covered in other steps of the study plan.
3. The material should be comprehensive and include code examples where appropriate and real-world analogies for complex topics.
4. Don't ask any questions to the user or repeat the content.
5. The output should be a single string of markdown-formatted text, bullet points, and code blocks for readability.
"""
    if incorrect_questions:
        prompt += f"""
IMPORTANT: The user previously struggled with the following questions. Please pay extra attention to clarifying these concepts:
{chr(10).join([f"- {q.get('question')}" for q in incorrect_questions])}
"""
    return prompt


def get_assessment_prompt(teaching_material, user_background):
    """
    Generate a prompt for creating assessments.

    Args:
        teaching_material: The content to test on.
        user_background: User's background.

    Returns:
        str: Prompt for generating 3 multiple-choice questions.
    """
    return f"""
You are an expert examiner. Based on the teaching material provided below, generate a set of 3 multiple-choice assessment questions to test the user's understanding of the topic.

TEACHING MATERIAL:
{teaching_material}

USER BACKGROUND:
{user_background}

INSTRUCTIONS:
1. Generate exactly 3 questions.
2. Each question must have 4 options (A, B, C, D).
3. Identify the correct answer option.
4. The output must be a valid JSON object with a single key "questions", which is a list of question objects.

JSON FORMAT:
{{
    "questions": [
        {{
            "question": "Question text here?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "A"
        }},
        ...
    ]
}}
"""


def get_podcast_script_prompt(context, user_background):
    """
    Generate a prompt for the podcast script.

    Args:
        context: Content to be discussed.
        user_background: Target audience profile.

    Returns:
        str: Prompt for generating a dialogue script.
    """
    return f"""
            You are an expert podcast script writer for podcast "Personal-Guru".
            Your goal is to generate a engaging podcast script between two speakers, Alex and Jamie to teach the audience about current learning material.

            The audience's background is: '{user_background}'.
            The learning material is:
            "{context}"

            Rules:
            1. Keep it concise but highly informative.
            2. Use simple and easy to understand language.
            3. Don't repeat the same point multiple times.
            4. Use the audience's background to decide the level of difficulty of the content only.
            5. Format the output exactly as follows:\n
            "Alex: [text]\n"
            "Jamie: [text]\n"
            "Alex: [text]\n"
            "...and so on."
            6. CRITICAL: Start every single line with "Alex:" or "Jamie:". Do NOT use any other names, titles, or variations like "Alex (Host)" or "Jamie (Guest)".
        """
