import os
from app.core.utils import call_llm
from app.core.agents import TopicTeachingAgent

class FlashcardTeachingAgent(TopicTeachingAgent):
    def generate_teaching_material(self, topic, count=50, user_background=None, **kwargs):
        """
        Generate `count` concise flashcards (term + short definition) for `topic`.
        Returns (list_of_flashcards, None) on success or (error_message, error) on failure.
        Expected return JSON from LLM: {"flashcards": [{"term": "...", "definition": "..."}, ...]}
        """
        if user_background is None:
            user_background = os.getenv("USER_BACKGROUND", "a beginner")

        prompt = f"""
You are an expert educator. Generate {count} concise flashcards for the topic '{topic}', tailored to a user with background: '{user_background}'.
Return a JSON object with key "flashcards" which is an array of objects with keys "term" and "definition".
Each definition should be one to two sentences maximum and focused on the most important concepts.
Don't include any extra commentary outside the JSON.
"""
        data, error = call_llm(prompt, is_json=True)
        if error:
            return data, error

        if not isinstance(data, dict) or 'flashcards' not in data or not isinstance(data['flashcards'], list):
            return "Error: Invalid flashcards format from LLM.", "Invalid format"

        # Defensive parsing and validation
        cards = []
        if 'flashcards' in data and isinstance(data['flashcards'], list):
            for c in data['flashcards']:
                if isinstance(c, dict):
                    term = c.get('term')
                    definition = c.get('definition')
                    if term and definition and isinstance(term, str) and isinstance(definition, str):
                        cards.append({'term': term.strip(), 'definition': definition.strip()})

        if not cards:
            return "Error: LLM returned no valid flashcards.", "Invalid format"

        # If LLM returned fewer cards than requested, attempt to generate the remainder
        # by asking for additional cards (avoid duplicates). Retry a few times.
        try_count = 0
        seen_terms = {c['term'].strip().lower() for c in cards}
        while len(cards) < count and try_count < 3:
            remaining = count - len(cards)
            try_count += 1
            extra_prompt = f"""
Generate {remaining} additional concise flashcards for the topic '{topic}', tailored to a user with background: '{user_background}'.
Do NOT repeat any of these terms: {', '.join(sorted(seen_terms))}.
Return a JSON object with key "flashcards" which is an array of objects with keys "term" and "definition".
"""
            extra_data, extra_err = call_llm(extra_prompt, is_json=True)
            if extra_err or not isinstance(extra_data, dict) or 'flashcards' not in extra_data:
                break

            added = 0
            for c in extra_data['flashcards']:
                if not isinstance(c, dict):
                    continue
                term = c.get('term')
                definition = c.get('definition')
                if not term or not definition:
                    continue
                key = term.strip().lower()
                if key in seen_terms:
                    continue
                cards.append({'term': term, 'definition': definition})
                seen_terms.add(key)
                added += 1
            if added == 0:
                # nothing new added; stop to avoid infinite loop
                break

        # Trim to requested count in case of over-generation
        if len(cards) > count:
            cards = cards[:count]

        return cards, None

    def get_flashcard_count_for_topic(self, topic, user_background=None):
        """
        Estimate the number of flashcards needed for a topic based on its complexity.
        Returns (count, None) on success or (default_count, error) on failure.
        """
        if user_background is None:
            user_background = os.getenv("USER_BACKGROUND", "a beginner")

        prompt = f"""
Analyze the complexity of the topic '{topic}' for a user with background: '{user_background}'.
Based on the topic's breadth and depth, suggest an ideal number of flashcards to generate for a comprehensive review.
Return a JSON object with a single key "count".
For a very simple topic, suggest 10-15 cards. For a moderately complex topic, 20-30. For a very complex topic, 40-50.
"""
        data, error = call_llm(prompt, is_json=True)
        if error:
            return 25, error  # Default on error

        if isinstance(data, dict) and 'count' in data and isinstance(data['count'], int):
            count = data['count']
            # Clamp the value to a reasonable range
            return max(10, min(50, count)), None

        return 25, "Invalid format from LLM"
