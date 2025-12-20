# Software Architecture

This document describes the high-level architecture of the Personal Guru application using the C4 model.

## 1. System Context Diagram (Level 1)

This diagram shows the Personal Guru system in the context of its users and external systems.

```mermaid
C4Context
    title System Context Diagram for Personal Guru

    Person(user, "User", "A person who wants to learn a new topic.")
    System(personal_guru, "Personal Guru", "Generates study plans, quizzes, and flashcards.")

    System_Ext(openai, "LLM Provider", "OpenAI / Ollama / LMStudio")
    System_Ext(youtube, "YouTube", "Provides video content for Reel Mode.")
    System_Ext(coqui, "Coqui TTS", "Text-to-Speech Engine for audio generation.")

    Rel(user, personal_guru, "Uses", "HTTPS")
    Rel(personal_guru, openai, "Generates Content via", "API")
    Rel(personal_guru, youtube, "Search & Embeds", "API")
    Rel(personal_guru, coqui, "Generates Audio via", "API")
```

## 2. Container Diagram (Level 2)

This diagram shows the high-level technical building blocks of the system.

```mermaid
C4Container
    title Container Diagram for Personal Guru

    Person(user, "User", "Learner")

    Container_Boundary(c1, "Personal Guru System") {
        Container(web_app, "Web Application", "Python, Flask", "Handles user requests, coordinates agents, and renders UI.")
        ContainerDb(fs, "File System", "JSON Files", "Stores user sessions, topic plans, progress, and flashcards in /data.")
    }

    System_Ext(openai, "LLM Provider", "Generates study material")
    System_Ext(youtube, "YouTube", "Serves video content")
    System_Ext(coqui, "Coqui TTS", "Generates audio")

    Rel(user, web_app, "Interacts with", "HTTPS/HTML")
    Rel(web_app, fs, "Reads/Writes", "File I/O")
    Rel(web_app, openai, "Calls", "JSON/REST")
    Rel(web_app, youtube, "Calls", "REST")
    Rel(web_app, coqui, "Calls", "REST")
```

## 3. Component Diagram (Level 3)

This diagram breaks down the Web Application into its core logical components.

```mermaid
C4Component
    title Component Diagram - Web Application

    Container(web_app, "Web Application", "Flask", "The main application container")

    Component(app_routes, "App Routes", "app.py", "Handles HTTP requests and routing.")
    
    Container_Boundary(agents, "AI Agents") {
        Component(planner, "PlannerAgent", "class", "Generates study plans.")
        Component(teacher, "TopicTeachingAgent", "class", "Generates lesson content and flashcards.")
        Component(assessor, "AssessorAgent", "class", "Generates quizzes.")
        Component(feedback, "FeedbackAgent", "class", "Evaluates user answers.")
        Component(chat, "ChatAgent", "class", "Answers free-form questions.")
    }

    Container_Boundary(reels, "Reel Services") {
        Component(start_reels, "Reel Search", "youtube_search.py", "Searches YouTube for shorts.")
        Component(validator, "Embed Validator", "embed_validator.py", "Checks if videos are embeddable.")
        Component(logger, "Session Logger", "session_logger.py", "Tracks video interactions.")
    }

    Component(storage, "Storage Ops", "storage.py", "Helper functions for File I/O.")
    Component(llm_client, "LLM Client", "agents.py: _call_llm", "Unified Interface for LLM calls.")

    Rel(app_routes, planner, "Uses")
    Rel(app_routes, teacher, "Uses")
    Rel(app_routes, assessor, "Uses")
    Rel(app_routes, feedback, "Uses")
    Rel(app_routes, chat, "Uses")
    
    Rel(app_routes, start_reels, "Uses")
    Rel(start_reels, validator, "Uses")
    Rel(app_routes, logger, "Uses")

    Rel(app_routes, storage, "Persists Data")
    
    Rel(planner, llm_client, "Calls")
    Rel(teacher, llm_client, "Calls")
    Rel(assessor, llm_client, "Calls")
    Rel(chat, llm_client, "Calls")
```

## 4. Dynamic Views (Sequence Diagrams)

### 4.1 Generate Study Plan
**Use Case:** User enters a topic to start a new course.

```mermaid
sequenceDiagram
    participant User
    participant App as App Routes (app.py)
    participant Planner as PlannerAgent
    participant LLM as LLM Client
    participant Storage as Storage Ops

    User->>App: POST / (topic="Quantum Physics")
    App->>Storage: load_topic("Quantum Physics")
    Storage-->>App: None (New Topic)
    
    App->>Planner: generate_study_plan("Quantum Physics")
    Planner->>LLM: _call_llm(Prompt)
    LLM-->>Planner: JSON Plan
    Planner-->>App: List[Steps]
    
    App->>Storage: save_topic("Quantum Physics", Plan)
    Storage-->>App: confirm save
    
    App-->>User: Redirect to /learn/Quantum Physics/0
```

### 4.2 Study Step Loading (Content Generation)
**Use Case:** User clicks "Start Learning" or "Next Step". The system generates content and quiz questions on-the-fly.

```mermaid
sequenceDiagram
    participant User
    participant App as App Routes
    participant Teacher as TopicTeachingAgent
    participant Assessor as AssessorAgent
    participant LLM as LLM Client
    participant Storage

    User->>App: GET /learn/<topic>/<step_index>
    App->>Storage: load_topic(topic)
    Storage-->>App: Topic Data
    
    opt "teaching_material" not yet generated
        App->>Teacher: generate_teaching_material(Step, FullPlan, Background)
        Teacher->>LLM: _call_llm(Prompt)
        LLM-->>Teacher: Markdown Content
        Teacher-->>App: Content
        
        App->>Assessor: generate_question(Content, Background)
        Assessor->>LLM: _call_llm(Prompt)
        LLM-->>Assessor: JSON Questions
        Assessor-->>App: Questions List
        
        App->>Storage: save_topic(Updated Data)
    end
    
    App-->>User: Render learn_step.html
```

### 4.3 Assessment & Feedback
**Use Case:** User submits answers to the quiz at the end of a step.

```mermaid
sequenceDiagram
    participant User
    participant App
    participant Feedback as FeedbackAgent
    participant Storage

    User->>App: POST /assess/<topic>/<step_index> (Answers)
    
    loop For each Question
        App->>Feedback: evaluate_answer(UserAns, CorrectAns)
        Feedback-->>App: Result (Correct/Incorrect)
    end
    
    App->>App: Calculate Score
    
    opt Score < 50%
        App->>App: Store Incorrect Questions in Session
    end
    
    App->>Storage: Save Results (Score, Feedback)
    App-->>User: Render feedback.html
```

### 4.4 Q&A Chat
**Use Case:** User asks a clarifying question about the reading material.

```mermaid
sequenceDiagram
    participant User
    participant App
    participant Chat as ChatAgent
    participant LLM

    User->>App: POST /chat/<topic>/<step> (Question)
    App->>App: Retrieve Current Step Context
    App->>Chat: get_answer(Question, Context, Background)
    Chat->>LLM: _call_llm(Prompt)
    LLM-->>Chat: Answer
    Chat-->>App: Answer
    App-->>User: JSON Response
```

### 4.5 Flashcard Generation
**Use Case:** User requests flashcards for a topic.

```mermaid
sequenceDiagram
    participant User
    participant App
    participant Teacher as TopicTeachingAgent
    participant LLM
    participant Storage

    User->>App: POST /flashcards/generate
    App->>Teacher: get_flashcard_count_for_topic(Topic) (Optional)
    Teacher->>LLM: _call_llm
    LLM-->>App: Count
    
    App->>Teacher: generate_flashcards(Topic, Count)
    Teacher->>LLM: _call_llm
    LLM-->>Teacher: List[Flashcards]
    Teacher-->>App: Flashcards
    
    App->>Storage: save_topic(Topic, Flashcards)
    App-->>User: JSON Flashcards
```

### 4.6 Reel Search & Interaction
**Use Case:** User searches for educational shorts in Reel Mode and swipes/views them.

```mermaid
sequenceDiagram
    participant User
    participant App
    participant ReelSearch as YouTube Search
    participant Validator as Embed Validator
    participant Logger as SessionLogger
    participant ExtYT as YouTube API

    User->>App: POST /api/reels/search (Topic)
    App->>Logger: Create Session
    App->>ReelSearch: search_youtube_reels(Topic)
    ReelSearch->>ExtYT: Search Query
    ExtYT-->>ReelSearch: Video List
    
    App->>Validator: validate_videos_batch(Videos)
    Validator->>Validator: Check Embeddability
    Validator-->>App: Authenticated Embeddable Videos
    
    App->>Storage: Save Session Log
    App-->>User: JSON Video List + SessionID
    
    par Async Interaction Logging
        User->>App: POST /api/reels/video-event (Play/Skip)
        App->>Logger: update_video_interaction(Event)
    end
```

### 4.7 Set User Background
**Use Case:** User updates their persona (e.g., "Beginner", "Expert").

```mermaid
sequenceDiagram
    participant User
    participant App
    participant Session
    participant Env as .env File

    User->>App: POST /background (New Background)
    App->>Session: session['user_background'] = Value
    App->>Env: set_key("USER_BACKGROUND", Value)
    App-->>User: Redirect to Index
```
