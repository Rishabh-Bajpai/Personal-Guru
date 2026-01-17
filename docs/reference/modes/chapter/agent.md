---
sidebar_label: agent
title: modes.chapter.agent
---

## ChapterModeChatAgent Objects

```python
class ChapterModeChatAgent(ChatAgent)
```

Agent for handling chat interactions specifically in Chapter mode.

#### \_\_init\_\_

```python
def __init__()
```

Initializes the ChapterModeChatAgent with the chapter system message.

## ChapterTeachingAgent Objects

```python
class ChapterTeachingAgent(TopicTeachingAgent)
```

Agent responsible for generating teaching material for a specific chapter.

#### generate\_teaching\_material

```python
def generate_teaching_material(topic,
                               full_plan,
                               user_background,
                               incorrect_questions=None)
```

Generates teaching material for the current topic.

Args:
    topic (str): The current topic/chapter title.
    full_plan (list): The complete study plan.
    user_background (str): Background information of the user.
    incorrect_questions (list, optional): List of questions the user missed previously.

Returns:
    tuple: The generated teaching material (markdown) and an error object (or None).

## AssessorAgent Objects

```python
class AssessorAgent()
```

Agent responsible for generating assessment question data based on teaching material.

#### generate\_question

```python
def generate_question(teaching_material, user_background)
```

Generates assessment question data for the provided teaching material.

The returned dictionary is expected to include a ``&quot;questions&quot;`` key containing
a list of assessment questions.

Args:
    teaching_material (str): The material to base questions on.
    user_background (str): The background of the user.

Returns:
    tuple: A dictionary containing the generated assessment question data and
    an error object (or None).

## PodcastAgent Objects

```python
class PodcastAgent()
```

Agent responsible for generating podcast scripts.

#### generate\_script

```python
def generate_script(context, user_background)
```

Generates a podcast script for the given context.
