def get_flashcard_generation_prompt(topic, count, user_background):
    """Generate a prompt for creating flashcards."""
    return f"""
You are an expert educator. Generate {count} concise flashcards for the topic '{topic}',
tailored to a user with background: '{user_background}'.
Return a JSON object with key "flashcards" which is an array of objects with keys
"term" and "definition".
Each definition should be one to two sentences maximum and focused on the most
important concepts.
Don't include any extra commentary outside the JSON.
"""


def get_additional_flashcards_prompt(topic, remaining, user_background, seen_terms):
    """Generate a prompt for creating additional flashcards, avoiding duplicates."""
    return f"""
Generate {remaining} additional concise flashcards for the topic '{topic}',
tailored to a user with background: '{user_background}'.
Do NOT repeat any of these terms: {', '.join(sorted(seen_terms))}.
Return a JSON object with key "flashcards" which is an array of objects with keys
"term" and "definition".
"""


def get_flashcard_count_prompt(topic, user_background):
    """Generate a prompt for estimating the ideal number of flashcards."""
    return f"""
Analyze the complexity of the topic '{topic}' for a user with background:
'{user_background}'.
Based on the topic's breadth and depth, suggest an ideal number of flashcards to
generate for a comprehensive review.
Return a JSON object with a single key "count".
For a very simple topic, suggest 10-15 cards. For a moderately complex topic, 20-30.
For a very complex topic, 40-50.
"""
