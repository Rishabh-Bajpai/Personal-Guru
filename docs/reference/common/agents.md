---
sidebar_label: agents
title: common.agents
---

## CodeExecutionAgent Objects

```python
class CodeExecutionAgent()
```

Agent responsible for preparing code snippets for execution.

#### \_\_init\_\_

```python
def __init__()
```

Initializes the CodeExecutionAgent.

#### enhance\_code

```python
def enhance_code(original_code)
```

Enhances the code adding imports, visualization and ensuring runnability.
Returns: { &#x27;code&#x27;: str, &#x27;dependencies&#x27;: list[str] }

## FeedbackAgent Objects

```python
class FeedbackAgent()
```

Agent responsible for evaluating user answers and providing feedback.

#### evaluate\_answer

```python
def evaluate_answer(question_obj, user_answer, answer_is_index=False)
```

Evaluates a user&#x27;s answer against a question object.

Args:
    question_obj (dict or str): The question object or string.
    user_answer (str or int): The user&#x27;s answer.
    answer_is_index (bool): Whether the user_answer is an index (for multiple choice).

Returns:
    tuple: A dictionary with &#x27;is_correct&#x27; (bool) and &#x27;feedback&#x27; (str), and an error object (or None).

## TopicTeachingAgent Objects

```python
class TopicTeachingAgent()
```

Base agent for generating teaching materials for a topic.

#### generate\_teaching\_material

```python
def generate_teaching_material(topic, **kwargs)
```

Base method for generating teaching material.
Subclasses should implement this method.

## PlannerAgent Objects

```python
class PlannerAgent()
```

Agent responsible for generating and updating study plans.

#### generate\_study\_plan

```python
def generate_study_plan(topic, user_background)
```

Generates a study plan for a given topic and user background.

Args:
    topic (str): The topic to study.
    user_background (str): The user&#x27;s background information.

Returns:
    list: A list of study steps (strings)

Raises:
    LLMResponseError: If LLM fails to generate a valid plan

#### update\_study\_plan

```python
def update_study_plan(topic_name, user_background, current_plan, comment)
```

Updates an existing study plan based on user feedback.

Args:
    topic_name (str): The name of the topic.
    user_background (str): The user&#x27;s background.
    current_plan (list): The current list of study steps.
    comment (str): The user&#x27;s feedback or request for change.

Returns:
    list: The updated list of steps

Raises:
    LLMResponseError: If LLM returns invalid plan format

## ChatAgent Objects

```python
class ChatAgent()
```

Agent responsible for handling chat interactions.

#### \_\_init\_\_

```python
def __init__(system_message_generator)
```

Initializes the ChatAgent.

Args:
    system_message_generator (callable): A function that generates the system message.

#### get\_answer

```python
def get_answer(question,
               conversation_history,
               context,
               user_background,
               plan=None)
```

Generates an answer to a user&#x27;s question.

Args:
    question (str): The user&#x27;s question.
    conversation_history (list): List of previous messages.
    context (str): Context for the conversation.
    user_background (str): User&#x27;s background info.
    plan (list, optional): The study plan.

Returns:
    tuple: The generated answer string and an error object (or None).

## SuggestionAgent Objects

```python
class SuggestionAgent()
```

Agent responsible for suggesting new topics.

#### generate\_suggestions

```python
def generate_suggestions(user_profile, past_topics)
```

Generates a list of suggested topics based on user profile and history.

Args:
    user_profile (str): The user&#x27;s profile description.
    past_topics (list): List of topics the user has already studied.

Returns:
    tuple: A list of suggested topic strings and an error object (or None).
