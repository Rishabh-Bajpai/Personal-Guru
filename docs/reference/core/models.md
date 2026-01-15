---
sidebar_label: models
title: core.models
---

## TimestampMixin Objects

```python
class TimestampMixin()
```

Mixin providing created_at and modified_at timestamp columns.

## SyncMixin Objects

```python
class SyncMixin()
```

Mixin providing sync_status column for DCS synchronization.

## Topic Objects

```python
class Topic(TimestampMixin, SyncMixin, db.Model)
```

User study topic with associated learning modes.

#### study\_plan

Storing list of strings as JSON

## ChatMode Objects

```python
class ChatMode(TimestampMixin, SyncMixin, db.Model)
```

Stores chat conversation history for a topic.

#### time\_spent

Duration in seconds

## ChapterMode Objects

```python
class ChapterMode(TimestampMixin, SyncMixin, db.Model)
```

Stores chapter-based learning content and assessments.

#### content

Markdown content

#### podcast\_audio\_path

path e.g. &quot;/data/audio/podcast_&lt;user_id&gt;&lt;topic&gt;&lt;step_id&gt;.mp3&quot;

#### popup\_chat\_history

Store chat history for this step

#### time\_spent

Duration in seconds

## QuizMode Objects

```python
class QuizMode(TimestampMixin, SyncMixin, db.Model)
```

Stores quiz questions and results for a topic.

#### questions

List of question objects

#### result

Detailed result (last_quiz_result)

#### time\_spent

Duration in seconds

## FlashcardMode Objects

```python
class FlashcardMode(TimestampMixin, SyncMixin, db.Model)
```

Stores flashcard term-definition pairs for a topic.

#### time\_spent

Duration in seconds

## User Objects

```python
class User(TimestampMixin, SyncMixin, db.Model)
```

Extended user profile with learning preferences and demographics.

#### languages

Storing list of strings as JSON

#### to\_context\_string

```python
def to_context_string()
```

Generates a text description of the user profile for LLM context.

## Installation Objects

```python
class Installation(TimestampMixin, SyncMixin, db.Model)
```

Tracks application installations with hardware info.

#### installation\_id

UUID

#### install\_method

&#x27;docker&#x27;, &#x27;local&#x27;, &#x27;cloud&#x27;

## SyncLog Objects

```python
class SyncLog(TimestampMixin, db.Model)
```

Records background data synchronization attempts.

#### status

&#x27;success&#x27;, &#x27;failed&#x27;, &#x27;partial&#x27;

#### details

Detailed stats or error message

## TelemetryLog Objects

```python
class TelemetryLog(TimestampMixin, SyncMixin, db.Model)
```

Stores user action events for analytics.

#### session\_id

UUID

#### triggers

event triggers like &#x27;user_action&#x27;, &#x27;auto_save&#x27;, etc.

## Feedback Objects

```python
class Feedback(TimestampMixin, SyncMixin, db.Model)
```

Stores user feedback and ratings.

#### feedback\_type

&#x27;form&#x27;, &#x27;in_place&#x27;

#### content\_reference

TODO: Define content tag like &#x27;chapter_1&#x27;, &#x27;quiz_2&#x27;, etc. Use topic_id, step_index etc. to uniquely identify content

## AIModelPerformance Objects

```python
class AIModelPerformance(TimestampMixin, SyncMixin, db.Model)
```

Tracks AI model latency and token usage metrics.

#### model\_type

&#x27;LLM&#x27;, &#x27;Embedding&#x27;, etc.

## PlanRevision Objects

```python
class PlanRevision(TimestampMixin, SyncMixin, db.Model)
```

Records changes made to study plans.

#### reason

Reason for revision, e.g., &quot;User requested more advanced topics&quot;

## Login Objects

```python
class Login(UserMixin, TimestampMixin, db.Model)
```

User authentication and identity model.

#### generate\_userid

```python
@staticmethod
def generate_userid(installation_id=None)
```

Generate a unique user ID, optionally prefixed with installation ID.

#### set\_password

```python
def set_password(password)
```

Hash and store the user password.

#### check\_password

```python
def check_password(password)
```

Verify password against stored hash.

#### get\_id

```python
def get_id()
```

Return the user ID for Flask-Login.

#### display\_name

```python
@property
def display_name()
```

Returns the name if set, otherwise &#x27;Learner&#x27;.
