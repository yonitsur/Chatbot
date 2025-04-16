

import os
import uuid
from unittest.mock import MagicMock, ANY 
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from httpx import ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError
import asyncio
import time 

load_dotenv()



TEST_DATABASE_URL = "sqlite:///:memory:"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

os.environ["OPENAI_KEY"] = os.getenv("OPENAI_KEY", "test-key-if-not-set")
os.environ["QDRANT_URL"] = "http://test-qdrant:6333"
os.environ["UVICORN_PORT"] = "8899" 


from main import app as real_app
from services.conversation_db import Base, Status, Conversation, add_message as db_add_message 
from services.dependencies import get_openai_client, get_neural_searcher
from config import REJECTION_MESSAGE, NO_HISTORY_SUMMARY_MESSAGE, DEFAULT_USER_ID, QDRANT_TOP_K 
from services.middleware import setup_middleware, get_db 


sync_test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SyncTestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=sync_test_engine, class_=Session
)


try:
    
    with sync_test_engine.connect() as connection:
        
        with connection.begin():
            Base.metadata.drop_all(connection)
            Base.metadata.create_all(connection)
except Exception as e:
    print(f"ERROR during initial test DDL setup with sync driver: {e}")
    
    import traceback
    traceback.print_exc()
    pytest.fail(f"Failed initial test DDL setup: {e}", pytrace=True)



@pytest.fixture(scope="function")
def db_sync_session() -> Session:
    """Provides a synchronous session for overriding the app's dependency, ensuring cleanup."""
    db = SyncTestingSessionLocal()
    try:
        yield db
    finally:
        
        db.rollback()
        
        with sync_test_engine.connect() as connection:
            with connection.begin():
                
                for table in reversed(Base.metadata.sorted_tables):
                    connection.execute(table.delete())
        db.close()


@pytest.fixture
def mock_openai_client():
    mock_client = MagicMock()
    
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    
    mock_message.content = "Mocked OpenAI response about startups."
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]
    
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client

@pytest.fixture
def mock_neural_searcher():
    mock_searcher = MagicMock()
    
    mock_searcher.search = MagicMock(
        return_value=[
            {"name": "Test Startup A", "city": "Test City", "description": "Desc A"},
            {"name": "Test Startup B", "city": "Test City", "description": "Desc B"},
        ]
    )
    return mock_searcher



@pytest.fixture(scope="function")
def client(
    db_sync_session: Session, mock_openai_client, mock_neural_searcher
):
    """Overrides dependencies for each test function."""
    
    real_app.dependency_overrides[get_db] = lambda: db_sync_session
    
    real_app.dependency_overrides[get_openai_client] = lambda: mock_openai_client
    real_app.dependency_overrides[get_neural_searcher] = lambda: mock_neural_searcher

    
    with TestClient(real_app) as test_client:
        yield test_client

    
    real_app.dependency_overrides = {}



def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_basic_query_success(
    client: TestClient, mock_openai_client, mock_neural_searcher, mocker
):
    user_id = "test_user_basic"
    session_id = str(uuid.uuid4())
    message = "Tell me about startups in Test City"
    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=True)
    mocker.patch("services.chatbot_service._rewrite_query_with_history", return_value=message)
    
    mock_chatbot_search = mocker.patch(
        "services.chatbot_service.Chatbot.search",
        return_value="Detailed answer about Test Startup A and B.",
    )

    response = client.post(
        "/query", json={"message": message, "user_id": user_id, "session_id": session_id}
    )

    assert response.status_code == 200
    assert "Detailed answer about Test Startup A and B." in response.json()["output"]
    
    mock_neural_searcher.search.assert_called_once_with(text=message, top_k=QDRANT_TOP_K)
    mock_chatbot_search.assert_called_once()


def test_irrelevant_query_rejection(client: TestClient, mocker):
    user_id = "test_user_irrelevant"
    session_id = str(uuid.uuid4())
    message = "What's the weather like?"

    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=False)
    
    mocker.patch("services.chatbot_service._rewrite_query_with_history", return_value=message)
    
    mock_chatbot_search = mocker.patch("services.chatbot_service.Chatbot.search")

    response = client.post(
        "/query", json={"message": message, "user_id": user_id, "session_id": session_id}
    )

    assert response.status_code == 200 
    assert response.json()["output"] == REJECTION_MESSAGE
    
    mock_chatbot_search.assert_not_called()


def test_summarize_no_history(client: TestClient, mocker): 
    user_id = "test_user_summary_empty"
    session_id = str(uuid.uuid4())
    
    mock_get_summary = mocker.patch("services.chatbot_service.Chatbot.get_summary")

    response = client.get(f"/summarize?user-id={user_id}&session-id={session_id}")

    assert response.status_code == 200
    
    
    assert response.json()["summary"] == "No history available."
    mock_get_summary.assert_not_called() 


def test_summarize_with_history(
    client: TestClient, db_sync_session: Session, mocker 
):
    user_id = "test_user_summary"
    session_id = str(uuid.uuid4())
    
    db_add_message(
        db_sync_session, user_id, session_id, "user", "Query about startup X", Status.processed
    )
    db_add_message(
        db_sync_session, user_id, session_id, "assistant", "Answer about startup X", Status.processed
    )
    db_add_message(
        db_sync_session, user_id, session_id, "user", "Follow up on X", Status.processed
    )
    db_add_message(
        db_sync_session, user_id, session_id, "assistant", "Details about X", Status.processed
    )
    
    

    
    mock_get_summary = mocker.patch(
        "services.chatbot_service.Chatbot.get_summary",
        return_value="Mocked conversation summary about startup X.",
    )

    response = client.get(f"/summarize?user-id={user_id}&session-id={session_id}")

    assert response.status_code == 200
    assert response.json()["summary"] == "Mocked conversation summary about startup X."
    
    mock_get_summary.assert_called_once()
    
    
    


def test_context_change_query_rewriting(
    client: TestClient, mock_neural_searcher, mocker
):
    user_id = "test_user_context"
    session_id = str(uuid.uuid4())
    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=True)
    
    mock_rewrite = mocker.patch("services.chatbot_service._rewrite_query_with_history")
    
    mocker.patch("services.chatbot_service.Chatbot.search", return_value="Some answer.")

    
    mock_rewrite.return_value = "startups in City A" 
    client.post(
        "/query",
        json={ "message": "Tell me about startups in City A", "user_id": user_id, "session_id": session_id, },
    )
    mock_rewrite.assert_called_with(ANY, "Tell me about startups in City A", []) 
    mock_neural_searcher.search.assert_called_with(text="startups in City A", top_k=QDRANT_TOP_K)


    
    mock_rewrite.return_value = "startups in City B" 
    
    mock_neural_searcher.search.reset_mock()
    mock_rewrite.reset_mock() 

    response = client.post(
        "/query",
        json={ "message": "What about in City B?", "user_id": user_id, "session_id": session_id, },
    )

    assert response.status_code == 200
    
    mock_rewrite.assert_called_with(ANY, "What about in City B?", mocker.ANY) 
    
    mock_neural_searcher.search.assert_called_with(text="startups in City B", top_k=QDRANT_TOP_K)


def test_rag_grounding_hallucination(
    client: TestClient, mock_neural_searcher, mock_openai_client, mocker
):
    user_id = "test_user_rag"
    session_id = str(uuid.uuid4())
    message_known = "Tell me about 'Specific RAG Startup'"
    message_unknown = "Tell me about 'Unknown Startup'"

    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=True)
    
    mocker.patch("services.chatbot_service._rewrite_query_with_history", side_effect=lambda _, msg, hist: msg)
    
    mock_chatbot_search = mocker.patch("services.chatbot_service.Chatbot.search")

    
    rag_data_found = [{"name": "Specific RAG Startup", "city": "RAG City", "description": "The only real detail."}]
    mock_neural_searcher.search.return_value = rag_data_found
    mock_chatbot_search.return_value = "LLM response based on Specific RAG Startup data."

    response_known = client.post(
        "/query",
        json={"message": message_known, "user_id": user_id, "session_id": session_id},
    )

    assert response_known.status_code == 200
    assert "LLM response based on Specific RAG Startup data." in response_known.json()["output"]
    
    mock_neural_searcher.search.assert_called_with(text=message_known, top_k=QDRANT_TOP_K)
    
    mock_chatbot_search.assert_called_with(
        openai_client=mock_openai_client,
        retrieved_data=rag_data_found, 
        user_message=message_known,
        conversation_history=mocker.ANY, 
        
        
    )

    
    mock_neural_searcher.search.return_value = [] 
    mock_chatbot_search.return_value = "LLM response indicating no specific data found."
    
    mock_neural_searcher.search.reset_mock()
    mock_chatbot_search.reset_mock()

    response_unknown = client.post(
        "/query",
        json={"message": message_unknown, "user_id": user_id, "session_id": session_id},
    )

    assert response_unknown.status_code == 200
    assert "LLM response indicating no specific data found." in response_unknown.json()["output"]
    
    mock_neural_searcher.search.assert_called_with(text=message_unknown, top_k=QDRANT_TOP_K)
    
    mock_chatbot_search.assert_called_with(
        openai_client=mock_openai_client,
        retrieved_data=[], 
        user_message=message_unknown,
        conversation_history=mocker.ANY 
    )


def test_consecutive_messages_skipping(
    client: TestClient, db_sync_session: Session, mocker
):
    user_id = "test_user_consecutive"
    session_id = str(uuid.uuid4())
    message1 = "Are there startups about wine in Chicago?"
    message2 = "Oops, I meant in New York!"

    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=True)
    
    mocker.patch(
        "services.chatbot_service._rewrite_query_with_history",
        side_effect=lambda _, msg, hist: "startups about wine in New York" if msg == message2 else msg
    )
    mocker.patch(
        "services.chatbot_service.Chatbot.search",
        return_value="Answer about NY wine startups.", 
    )
    mocker.patch(
        "services.neural_search_service.NeuralSearcher.search",
        return_value=[{"name": "NY Wine Startup"}], 
    )

    
    
    response1 = client.post(
        "/query",
        json={"message": message1, "user_id": user_id, "session_id": session_id},
    )
    
    response2 = client.post(
        "/query",
        json={"message": message2, "user_id": user_id, "session_id": session_id},
    )

    
    
    time.sleep(2.5) 

    
    
    assert response2.status_code == 200
    assert "Answer about NY wine startups." in response2.json()["output"]

    
    
    assert response1.status_code in [200, 202]

    
    messages = (
        db_sync_session.query(Conversation)
        .filter(Conversation.user_id == user_id, Conversation.session_id == session_id)
        .order_by(Conversation.id)
        .all()
    )

    print(f"Messages found: {len(messages)}")
    for msg in messages:
        print(
            f"  ID: {msg.id}, Role: {msg.role}, Status: {msg.status.value}, Msg: {msg.message[:30]}"
        )

    
    
    assert len(messages) >= 3 

    
    user_messages = [m for m in messages if m.role == 'user']
    assistant_messages = [m for m in messages if m.role == 'assistant']

    assert len(user_messages) == 2
    user_msg1 = user_messages[0]
    user_msg2 = user_messages[1]

    assert user_msg1.message == message1
    assert user_msg2.message == message2

    
    assert user_msg2.status == Status.processed

    
    
    assert user_msg1.status in [Status.skipped, Status.processed]

    
    if user_msg1.status == Status.skipped:
        assert response1.status_code == 202
        
        assert len(assistant_messages) == 1
        assert assistant_messages[0].message == "Answer about NY wine startups."
    elif user_msg1.status == Status.processed:
         
        assert response1.status_code == 200
        
        assert len(assistant_messages) >= 1


def test_openai_error_handling(
    client: TestClient, mock_openai_client, mock_neural_searcher, mocker 
):
    user_id = "test_user_openai_error"
    session_id = str(uuid.uuid4())
    message = "This will cause an error"

    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=True)
    mocker.patch("services.chatbot_service._rewrite_query_with_history", return_value=message)
    
    mock_neural_searcher.search.return_value=[]

    
    from openai import RateLimitError 
    error_body = {"error": {"message": "Rate limit exceeded"}}
    mock_response = MagicMock()
    mock_response.status_code = 429
    
    
    openai_error = RateLimitError(
        message="Rate limit exceeded", response=mock_response, body=error_body
    )
    
    
    
    mocker.patch("services.chatbot_service.Chatbot.search", side_effect=openai_error)
    
    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=True)
    mocker.patch("services.chatbot_service._rewrite_query_with_history", return_value=message)


    
    response = client.post(
        "/query", json={"message": message, "user_id": user_id, "session_id": session_id}
    )

    
    assert response.status_code == 503 
    detail = response.json().get("detail", "").lower() 
    assert "ai service unavailable" in detail
    
    
    assert "rate limit exceeded" in detail or "429" in detail 


def test_generic_error_handling(client: TestClient, mocker):
    user_id = "test_user_generic_error"
    session_id = str(uuid.uuid4())
    message = "This will cause a generic error"

    
    mocker.patch(
        "services.chatbot_service._rewrite_query_with_history",
        side_effect=ValueError("Unexpected problem during rewrite"),
    )
    
    mocker.patch("services.conversation_db.add_message", return_value=1) 
    mocker.patch("services.conversation_db.mark_older_pending_as_skipped")

    response = client.post(
        "/query", json={"message": message, "user_id": user_id, "session_id": session_id}
    )

    assert response.status_code == 500 
    detail = response.json().get("detail", "")
    
    assert "Internal Server Error: ValueError" in detail



def test_user_session_isolation(
    client: TestClient, db_sync_session: Session, mocker
):
    user1_id = "user_iso_1"
    user2_id = "user_iso_2"
    session1_id = str(uuid.uuid4())
    session2_id = str(uuid.uuid4()) 
    session3_id = str(uuid.uuid4()) 

    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=True)
    mocker.patch("services.chatbot_service._rewrite_query_with_history", side_effect=lambda _, msg, hist: msg)
    mock_chatbot_search = mocker.patch("services.chatbot_service.Chatbot.search")
    mocker.patch("services.neural_search_service.NeuralSearcher.search", return_value=[])

    
    mock_chatbot_search.return_value = "Response for User1/Session1"
    client.post("/query", json={"message": "Msg U1S1", "user_id": user1_id, "session_id": session1_id})

    mock_chatbot_search.return_value = "Response for User1/Session2"
    client.post("/query", json={"message": "Msg U1S2", "user_id": user1_id, "session_id": session2_id})

    mock_chatbot_search.return_value = "Response for User2/Session3"
    client.post("/query", json={"message": "Msg U2S3", "user_id": user2_id, "session_id": session3_id})

    
    
    hist1 = db_sync_session.query(Conversation).filter(
        Conversation.user_id == user1_id, Conversation.session_id == session1_id
    ).all()
    assert len(hist1) == 2
    assert hist1[0].message == "Msg U1S1"
    assert hist1[1].message == "Response for User1/Session1"

    
    hist2 = db_sync_session.query(Conversation).filter(
        Conversation.user_id == user1_id, Conversation.session_id == session2_id
    ).all()
    assert len(hist2) == 2
    assert hist2[0].message == "Msg U1S2"
    assert hist2[1].message == "Response for User1/Session2"

    
    hist3 = db_sync_session.query(Conversation).filter(
        Conversation.user_id == user2_id, Conversation.session_id == session3_id
    ).all()
    assert len(hist3) == 2
    assert hist3[0].message == "Msg U2S3"
    assert hist3[1].message == "Response for User2/Session3"

    
    total_user1 = db_sync_session.query(Conversation).filter(Conversation.user_id == user1_id).count()
    assert total_user1 == 4

     
    total_user2 = db_sync_session.query(Conversation).filter(Conversation.user_id == user2_id).count()
    assert total_user2 == 2



def test_clear_db_endpoint(client: TestClient, db_sync_session: Session, mocker):
    
    user_id_to_clear = "user_clear"
    user_id_other = "user_other"
    session_id1 = str(uuid.uuid4())
    session_id2 = str(uuid.uuid4())
    session_id_other = str(uuid.uuid4())

    
    mocker.patch("services.chatbot_service._is_conversation_about_startups", return_value=True)
    mocker.patch("services.chatbot_service._rewrite_query_with_history", side_effect=lambda _, msg, hist: msg)
    mocker.patch("services.chatbot_service.Chatbot.search", return_value="Response")
    mocker.patch("services.neural_search_service.NeuralSearcher.search", return_value=[])

    
    client.post("/query", json={"message": "Msg 1", "user_id": user_id_to_clear, "session_id": session_id1}) 
    client.post("/query", json={"message": "Msg 2", "user_id": user_id_to_clear, "session_id": session_id2}) 
    client.post("/query", json={"message": "Msg Other", "user_id": user_id_other, "session_id": session_id_other}) 

    initial_count_user_clear = db_sync_session.query(Conversation).filter(Conversation.user_id == user_id_to_clear).count()
    initial_count_other = db_sync_session.query(Conversation).filter(Conversation.user_id == user_id_other).count()
    initial_total_count = db_sync_session.query(Conversation).count()

    assert initial_count_user_clear == 4
    assert initial_count_other == 2
    assert initial_total_count == 6

    
    response_clear_session1 = client.post(
        f"/clear_db_testing_only?user-id={user_id_to_clear}&session-id={session_id1}"
    )
    assert response_clear_session1.status_code == 200
    assert f"cleared for session '{session_id1}' for user '{user_id_to_clear}'" in response_clear_session1.json()["message"]

    count_after_clear1_user = db_sync_session.query(Conversation).filter(Conversation.user_id == user_id_to_clear).count()
    count_after_clear1_other = db_sync_session.query(Conversation).filter(Conversation.user_id == user_id_other).count()
    count_after_clear1_total = db_sync_session.query(Conversation).count()

    assert count_after_clear1_user == 2 
    assert count_after_clear1_other == 2 
    assert count_after_clear1_total == 4

    
    response_clear_user = client.post(f"/clear_db_testing_only?user-id={user_id_to_clear}")
    assert response_clear_user.status_code == 200
    expected_detail_substring = f"ALL sessions for user '{user_id_to_clear}'"
    assert expected_detail_substring in response_clear_user.json()["message"]

    count_after_clear_user_target = db_sync_session.query(Conversation).filter(Conversation.user_id == user_id_to_clear).count()
    count_after_clear_user_other = db_sync_session.query(Conversation).filter(Conversation.user_id == user_id_other).count()
    count_after_clear_user_total = db_sync_session.query(Conversation).count()

    assert count_after_clear_user_target == 0 
    assert count_after_clear_user_other == 2 
    assert count_after_clear_user_total == 2

     
    
    client.post("/query", json={"message": "Msg 3", "user_id": user_id_to_clear, "session_id": session_id1}) 
    assert db_sync_session.query(Conversation).count() == 4 

    response_clear_all = client.post("/clear_db_testing_only?clear_all=true")
    assert response_clear_all.status_code == 200
    assert "cleared for the ENTIRE database" in response_clear_all.json()["message"]

    assert db_sync_session.query(Conversation).count() == 0 

    
    response_bad_session_only = client.post(f"/clear_db_testing_only?session-id={session_id1}")
    assert response_bad_session_only.status_code == 400 
    assert "Cannot specify session-id without user-id" in response_bad_session_only.json()["detail"]

    response_bad_no_params = client.post("/clear_db_testing_only")
    assert response_bad_no_params.status_code == 400 
    assert "Specify user-id, user-id/session-id, or clear_all=true" in response_bad_no_params.json()["detail"]