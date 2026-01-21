---
sidebar_label: routes
title: core.routes
---

#### index

```python
@main_bp.route('/', methods=['GET', 'POST'])
def index()
```

Render home page with topics list or redirect to selected learning mode.

#### login

```python
@main_bp.route('/login', methods=['GET', 'POST'])
def login()
```

Handle user login with username and password authentication.

#### signup

```python
@main_bp.route('/signup', methods=['GET', 'POST'])
def signup()
```

Handle new user registration and profile creation.

#### logout

```python
@main_bp.route('/logout')
def logout()
```

Log out the current user and redirect to home page.

#### user\_profile

```python
@main_bp.route('/user_profile', methods=['GET', 'POST'])
@login_required
def user_profile()
```

Display and update user profile information.

#### delete\_topic\_route

```python
@main_bp.route('/delete/<topic_name>')
def delete_topic_route(topic_name)
```

Delete the specified topic and redirect to home page.

#### suggest\_topics

```python
@main_bp.route('/api/suggest-topics', methods=['GET', 'POST'])
@login_required
def suggest_topics()
```

Generate AI-powered topic suggestions based on user profile.

#### settings

```python
@main_bp.route('/settings', methods=['GET', 'POST'])
def settings()
```

Display and update application settings stored in .env file.

#### transcribe

```python
@main_bp.route('/api/transcribe', methods=['POST'])
@login_required
def transcribe()
```

Transcribe uploaded audio file to text using STT service.

#### submit\_feedback

```python
@main_bp.route('/api/feedback', methods=['POST'])
@login_required
def submit_feedback()
```

Handle user feedback form submissions.

Accepts JSON with feedback_type, rating (1-5), and comment.
Saves to the Feedback table and logs telemetry event.

Returns:
    JSON response with success status or error message.
