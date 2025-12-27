def get_chapter_system_message(context, user_background, is_guided_mode, plan=None):
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
1. **Be Concise**: The user is looking at a side-panel chat. Keep answers short and to the point. Avoid long paragraphs.
2. **Context First**: Answer based primarily on the provided learning material content.
3. **Directness**: Do not use "Certainly!" or "Here is the answer". Just answer.
4. **No Artifacts**: Do not output internal thought processes, <tool_call> tags, or <think> tags. Output ONLY the answer.
5. **Formatting**: You can use bullet points for lists, but keep them compact.
"""
    return base_prompt

def get_code_execution_prompt(code):
    return f"""
You are an expert Python coding assistant.
Your goal is to enhance the provided code snippet to make it runnable, robust, and visually appealing if it involves plots.

INPUT CODE:
```python
{code}
```

INSTRUCTIONS:
1. **Import Dependencies**: Ensure all necessary libraries (e.g., matplotlib, pandas, numpy) are imported.
2. **Error Handling**: Wrap the main logic in try-except blocks to print meaningful errors instead of crashing.
3. **Visualization**: If the code generates plots, ensure they are saved to a file or buffer if needed, or better yet, assume standard plt.show() works in the sandbox which captures stdout/images.
4. **Dependencies List**: Identify all external pip packages required.

OUTPUT FORMAT:
Return a strictly valid JSON object with the following structure:
{{
    "code": "The full enhanced python code string...",
    "dependencies": ["list", "of", "pip", "packages"]
}}
"""

def get_teaching_material_prompt(topic, full_plan, user_background, incorrect_questions=None):
    prompt = f"""
You are an expert tutor. Create detailed teaching material for the topic: "{topic}".
The user's background is: "{user_background}".

FULL STUDY PLAN CONTEXT:
{chr(10).join([f"- {s}" for s in full_plan])}

INSTRUCTIONS:
1. **Explain the Topic**: Provide a clear, comprehensive explanation of the concept "{topic}".
2. **Relevance**: Explain why this is important in the context of the overall study plan.
3. **Examples**: Provide concrete code examples or real-world analogies.
4. **Formatting**: Use Markdown headers, bullet points, and code blocks for readability.
5. **Interactive Encouragement**: Encourage the user to try the code examples.
"""
    if incorrect_questions:
        prompt += f"""
IMPORTANT: The user previously struggled with the following questions. Please pay extra attention to clarifying these concepts:
{chr(10).join([f"- {q.get('question')}" for q in incorrect_questions])}
"""
    return prompt

def get_assessment_prompt(teaching_material, user_background):
    return f"""
You are an expert examiner. Based on the teaching material provided below, generate a set of 3 multiple-choice assessment questions to test the user's understanding.

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
