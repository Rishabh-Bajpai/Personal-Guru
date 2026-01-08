
import pytest
from unittest.mock import patch, MagicMock
from app.common.utils import summarize_text
from app.core.models import ChatSession, Topic

def test_summarize_text_function():
    with patch('app.common.utils.call_llm') as mock_llm:
        mock_llm.return_value = "Summary: Short text."
        
        text = "This is a very long text that needs summarization. " * 10
        summary = summarize_text(text)
        
        assert summary == "Summary: Short text."
        mock_llm.assert_called_once()
        args, _ = mock_llm.call_args
        assert "Requirements:" in args[0]


def test_chat_summary_integration(auth_client, app):
    """
    Test that sending messages updates both history and history_summary.
    """
    topic_name = "SummarizationTest"
    
    # 1. Start topic by visiting (creates it)
    auth_client.get(f'/chat/{topic_name}', follow_redirects=True)
    
    with app.app_context():
        # Verify topic created
        from app.core.models import Topic
        topic = Topic.query.filter_by(name=topic_name).first()
        assert topic is not None
        assert topic.chat_session is not None
        # Should be empty initially
        assert len(topic.chat_session.history) == 1 # Welcome message
        # history_summary defaults to None in DB if just added, or [] via load_topic logic
        # But accessing model directly (topic.chat_session.history_summary) gives raw value.
        # It should be None or empty.
        val = topic.chat_session.history_summary
        assert val is None or len(val) == 0
    
    # Mock LLM to return distinct answers and summaries
    # We patch app.common.utils.call_llm because summarize_text uses it.
    # We patch app.common.agents.call_llm because ChatAgent (parent of chat_agent) uses it.
    with patch('app.common.utils.call_llm') as mock_llm_utils, \
         patch('app.common.agents.call_llm') as mock_llm_agents:
        
        # Setup mocks
        # mock_llm_utils is called by summarize_text
        mock_llm_utils.side_effect = lambda prompt, **kwargs: f"SUMMARY_OF_ANSWER"
        
        # mock_llm_agents is called by chat_agent.get_answer
        mock_llm_agents.return_value = "FULL_ANSWER_CONTENT"

        # 2. Send a message
        auth_client.post(f'/chat/{topic_name}/send', data={'message': 'User Question 1'}, follow_redirects=True)
        
    with app.app_context():
        topic = Topic.query.filter_by(name=topic_name).first()
        session = topic.chat_session
        
        print(f"History: {len(session.history)}")
        summary_len = len(session.history_summary) if session.history_summary else 0
        print(f"Summary: {summary_len}")
        
        assert len(session.history) == 3
        # Welcome (1) + User (1) + Assistant (1) = 3
        
        assert summary_len == 3
        # Welcome (copied) + User (copied) + Assistant (summarized)
        
        # Check content
        # History has full answer
        assert session.history[-1]['content'] == "FULL_ANSWER_CONTENT"
        # Summary has summarized answer
        assert session.history_summary[-1]['content'] == "SUMMARY_OF_ANSWER"
        
        # Verify Welcome message exists in summary (unsummarized because it was copied)
        assert session.history_summary[0]['content'] == session.history[0]['content']


def test_chat_context_construction(auth_client, app):
    """
    Test that context construction uses summaries for older messages.
    """
    topic_name = "ContextTest"
    auth_client.get(f'/chat/{topic_name}', follow_redirects=True)
    
    with patch('app.common.utils.call_llm') as mock_llm_utils, \
         patch('app.common.agents.call_llm') as mock_llm_agents:
        
        mock_llm_utils.return_value = "SUM"
        mock_llm_agents.return_value = "ANS"

        # Send 4 messages (4 turns)
        for i in range(4):
            auth_client.post(f'/chat/{topic_name}/send', data={'message': f'Msg {i}'}, follow_redirects=True)

    with app.app_context():
        topic = Topic.query.filter_by(name=topic_name).first()
        sess = topic.chat_session
        # History: W(0), U0(1), A0(2), U1(3), A1(4), U2(5), A2(6), U3(7), A3(8) = 9 messages
        assert len(sess.history) == 9 
        assert sess.history_summary and len(sess.history_summary) == 9
        assert sess.history_summary[-1]['content'] == "SUM"

    # Now verify the next call uses the correct context.
    # We want to inspect what is passed to `chat_agent.get_answer` -> `call_llm`.
    
    with patch('app.common.utils.call_llm') as mock_llm_utils, \
         patch('app.modes.chat.agent.ChatModeMainChatAgent.get_answer') as mock_agent:
        
        mock_agent.return_value = "FinalAns"
        mock_llm_utils.return_value = "SUM_FINAL"
        
        auth_client.post(f'/chat/{topic_name}/send', data={'message': 'CurrentMsg'}, follow_redirects=True)
        
        # Verify call args
        mock_agent.assert_called_once()
        args, _ = mock_agent.call_args
        # args[1] is messages_for_llm
        passed_history = args[1]
        
        # Expected:
        # Full history: W, U0, A0, U1, A1, U2, A2, U3, A3, CurrentMsg (10 msgs)
        # KEEP_FULL_COUNT = 5
        # Older part: Summary[:-5] -> Indexes 0 to 4 (5 messages)
        #   W(0), U0(1), S0(2), U1(3), S1(4)
        # Recent part: Full[-5:] -> Indexes 5 to 9 (5 messages)
        #   U2(5), A2(6), U3(7), A3(8), Curr(9)
        
        assert len(passed_history) == 10
        # Index 4 is S1 (Summary of Assistant 1). Since mock returned "SUM", it should be "SUM".
        assert passed_history[4]['content'] == "SUM"
        # Index 6 is A2 (Full Assistant 2). Since mock returned "ANS", it should be "ANS".
        assert passed_history[6]['content'] == "ANS"
