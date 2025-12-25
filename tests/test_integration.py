import pytest
import os

# Mark all tests in this file as 'integration'
pytestmark = pytest.mark.integration

# Skip all tests in this file if the RUN_INTEGRATION_TESTS environment variable is not set
# This allows us to run unit tests (`pytest`) without running integration tests.
# To run integration tests, run `pytest -m integration`.
if os.getenv("RUN_INTEGRATION_TESTS") != "1":
    pytest.skip("Skipping integration tests", allow_module_level=True)

from app.core.utils import call_llm

def test_call_llm():
    """Test that the LLM call function is working."""
    prompt = "Hello, LLM! Please respond with a short message."
    response, error = call_llm(prompt)
    assert error is None
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0


from app.modes.quiz.agent import QuizAgent

def test_quiz_agent():
    """Test that the QuizAgent can generate a quiz."""
    agent = QuizAgent()
    quiz, error = agent.generate_quiz("Math", "beginner", count=2)
    assert error is None
    assert quiz is not None
    assert "questions" in quiz
    assert len(quiz["questions"]) == 2


from app.modes.chapter.agent import PlannerAgent

def test_planner_agent():
    """Test that the PlannerAgent can generate a study plan."""
    agent = PlannerAgent()
    plan, error = agent.generate_study_plan("History", "beginner")
    assert error is None
    assert plan is not None
    assert isinstance(plan, list)
    assert len(plan) > 0


from app.core.agents import FeedbackAgent

def test_feedback_agent():
    """Test that the FeedbackAgent can generate feedback."""
    agent = FeedbackAgent()
    question = {"question": "What is 2+2?", "options": ["3", "4", "5"], "correct_answer": "B"}
    feedback, error = agent.evaluate_answer(question, "A")
    assert error is None
    assert feedback is not None
    assert "feedback" in feedback
    assert not feedback["is_correct"]


from app.modes.chapter.agent import ChapterTeachingAgent

def test_chapter_teaching_agent():
    """Test that the ChapterTeachingAgent can generate teaching material."""
    agent = ChapterTeachingAgent()
    material, error = agent.generate_teaching_material("Science", ["Introduction"], "beginner")
    assert error is None
    assert material is not None
    assert isinstance(material, str)
    assert len(material) > 0


from app.modes.flashcard.agent import FlashcardTeachingAgent

def test_flashcard_teaching_agent():
    """Test that the FlashcardTeachingAgent can generate flashcards."""
    agent = FlashcardTeachingAgent()
    flashcards, error = agent.generate_teaching_material("Vocabulary", count=3)
    assert error is None
    assert flashcards is not None
    assert isinstance(flashcards, list)
    assert len(flashcards) > 0


from app.modes.chapter.agent import AssessorAgent

def test_assessor_agent():
    """Test that the AssessorAgent can generate a question."""
    agent = AssessorAgent()
    question, error = agent.generate_question("A chapter about Python.", "beginner")
    assert error is None
    assert question is not None
    assert "questions" in question
    assert len(question["questions"]) > 0
