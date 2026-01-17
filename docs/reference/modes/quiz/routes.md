---
sidebar_label: routes
title: modes.quiz.routes
---

#### generate\_quiz

```python
@quiz_bp.route('/generate/<topic_name>/<count>', methods=['GET', 'POST'])
def generate_quiz(topic_name, count)
```

Generate a quiz with the specified number of questions and save it.

#### mode

```python
@quiz_bp.route('/<topic_name>')
def mode(topic_name)
```

Load quiz from saved data or generate new one.
