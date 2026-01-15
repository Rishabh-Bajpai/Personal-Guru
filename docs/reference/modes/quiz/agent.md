---
sidebar_label: agent
title: modes.quiz.agent
---

## QuizAgent Objects

```python
class QuizAgent()
```

Agent responsible for generating and determining the scope of quizzes.

#### generate\_quiz

```python
def generate_quiz(topic, user_background, count=10)
```

Generates a quiz with a specific number of questions.

Args:
    topic (str): The subject of the quiz.
    user_background (str): The user&#x27;s background information.
    count (int or str): Number of questions to generate (default 10, or &#x27;auto&#x27;).

Returns:
    tuple: A dictionary containing the quiz data and an error object (or None).

#### get\_quiz\_count\_for\_topic

```python
def get_quiz_count_for_topic(topic, user_background=None)
```

Estimate the number of quiz questions needed for a topic based on its complexity.
Returns (count, None) on success or (default_count, error) on failure.
