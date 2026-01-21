---
sidebar_label: agent
title: modes.chat.agent
---

## ChatModeMainChatAgent Objects

```python
class ChatModeMainChatAgent(ChatAgent)
```

Main agent for handling chat interactions in the dedicated Chat mode.

#### \_\_init\_\_

```python
def __init__()
```

Initializes the ChatModeMainChatAgent with the chat system message.

#### get\_welcome\_message

```python
def get_welcome_message(topic_name, user_background, plan=None)
```

Generates a personalized welcome message to start a chat session.

Args:
    topic_name (str): The name of the topic.
    user_background (str): The background of the user.
    plan (list, optional): The current study plan.

Returns:
    tuple: The welcome message string and an error object (or None).

## ChatModeChatPopupAgent Objects

```python
class ChatModeChatPopupAgent(ChatAgent)
```

Agent for handling chat interactions specifically in Chat mode popup.

#### \_\_init\_\_

```python
def __init__()
```

Initializes the ChatModeChatPopupAgent with the popup system message.
