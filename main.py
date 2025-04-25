from fastapi import FastAPI, Depends, HTTPException, status,  Query as QueryParam
import logging

from services.dependencies import get_openai_client, get_neural_searcher
from services.conversation_db import (
    init_db, add_message, update_message_status,
    get_recent_messages_for_summary, mark_older_pending_as_skipped,
    get_message_status, clear_db, Status,
    get_user_sessions, get_messages_for_session
)
from services.chatbot_service import Chatbot
from services.middleware import setup_middleware, get_db
from sqlalchemy.orm import Session
from openai import OpenAI, OpenAIError
from services.neural_search_service import NeuralSearcher
from config import (
    API_TITLE,
    LOG_LEVEL,
    LOG_FORMAT,
    UVICORN_HOST,
    UVICORN_PORT,
    UVICORN_RELOAD,
    DEFAULT_USER_ID,
    DEFAULT_SESSION_ID,
    MESSAGE_STATUS_CHECK_DELAY_SECONDS

)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import asyncio
from fastapi import Path
from contextlib import asynccontextmanager

logging.basicConfig(level=LOG_LEVEL.upper(), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup: Initializing database...")
    try:
        init_db()
        logger.info("Database initialized successfully during startup.")
    except Exception as e:
        logger.exception("Fatal error during database initialization on startup.")
        raise RuntimeError("Failed to initialize database on startup") from e

    yield

    logger.info(
        "Application shutdown: No specific cleanup needed for DB engine with current setup."
    )


try:
    app = FastAPI(title=API_TITLE, lifespan=lifespan)
except Exception as e:
    logger.exception("Fatal error during application setup (before startup event).")
    raise

setup_middleware(app)

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    message: str = Field(..., min_length=1, description="User's message/question")
    user_id: str = Field(DEFAULT_USER_ID, description="User ID")
    session_id: str = Field(DEFAULT_SESSION_ID, description="Session ID")


class QueryResponse(BaseModel):
    output: str
    session_id: str
    message_id: int


class SummaryResponse(BaseModel):
    summary: str


class SkippedResponse(BaseModel):
    output: str
    detail: str = "Message processing skipped because a newer message was received."
    session_id: str = Field(..., description="Session ID")
    message_id: int = Field(..., description="Message ID")


class SessionInfo(BaseModel):
    session_id: str
    start_time: datetime


class SessionListResponse(BaseModel):
    sessions: List[SessionInfo]


class MessageHistoryItem(BaseModel):
    id: int
    user_id: str
    session_id: str
    timestamp: datetime
    role: str
    message: str
    status: Status


class MessageHistoryResponse(BaseModel):
    messages: List[MessageHistoryItem]


@app.post("/query", response_model=QueryResponse, responses={
    200: {"model": QueryResponse, "description": "Successful response"},
    202: {"model": SkippedResponse, "description": "Message processing skipped"},
})
async def query(
    query_data: Query,
    db: Session = Depends(get_db),
    openai_client: OpenAI = Depends(get_openai_client),
    neural_searcher: NeuralSearcher = Depends(get_neural_searcher),
):
    start_time = asyncio.get_event_loop().time()
    user_message = query_data.message.strip()
    user_id = query_data.user_id
    session_id = query_data.session_id

    logger.info(
        f"Received query from user '{user_id}', session '{session_id}': "
        f"'{user_message[:100]}...'"
    )

    try:
        user_message_id = await asyncio.to_thread(
            lambda: add_message(db, user_id, session_id, "user", user_message, Status.pending)
        )
        if user_message_id == -1:
            logger.error(
                f"Failed to store initial message for user '{user_id}', session '{session_id}', query: '{user_message[:100]}...'"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store user message.",
            )

        await asyncio.to_thread(
            lambda: mark_older_pending_as_skipped(db, user_id, session_id, user_message_id)
        )

        await asyncio.sleep(MESSAGE_STATUS_CHECK_DELAY_SECONDS)

        current_status = await asyncio.to_thread(
            lambda: get_message_status(db, user_message_id)
        )

        if current_status == Status.skipped:
            logger.info(
                f"Message ID {user_message_id} (user '{user_id}', session '{session_id}') was skipped."
            )

            return SkippedResponse(
                output="This message was skipped because a newer message was received.",
                session_id=session_id,
                message_id=user_message_id
            )

        if current_status != Status.pending:
            logger.error(
                f"Message ID {user_message_id} (user '{user_id}', session '{session_id}') has unexpected status {current_status} after skip check. Aborting."
            )
            await asyncio.to_thread(
                lambda: update_message_status(db, user_message_id, Status.error)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal state error for message {user_message_id}.",
            )

        logger.info(
            f"Proceeding to process message ID {user_message_id} (user '{user_id}', session '{session_id}')."
        )

        answer, assistant_message_id = await Chatbot.process_query(
            db=db,
            openai_client=openai_client,
            neural_searcher=neural_searcher,
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            message_id=user_message_id,
        )

        end_time = asyncio.get_event_loop().time()
        logger.info(
            f"Total processing time for user message ID {user_message_id}: {end_time - start_time:.2f} seconds"
        )

        return QueryResponse(
            output=answer, session_id=session_id, message_id=assistant_message_id
        )

    except OpenAIError as e:
        logger.exception(
            f"OpenAI API error processing user message ID {user_message_id} (user '{user_id}', session '{session_id}'): {e}"
        )
        await asyncio.to_thread(
            lambda: update_message_status(db, user_message_id, Status.error)
        )
        error_msg = f"Sorry, failed to connect to AI service ({getattr(e, 'status_code', 'N/A')})."
        await asyncio.to_thread(
            lambda: add_message(db, user_id, session_id, "assistant", error_msg, Status.error)
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service unavailable: {getattr(e, 'body', 'Unknown Error')}",
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(
            f"Unexpected error processing user message ID {user_message_id} (user '{user_id}', session '{session_id}'): {e}"
        )
        await asyncio.to_thread(
            lambda: update_message_status(db, user_message_id, Status.error)
        )
        error_msg = "Sorry, an internal server error occurred."
        await asyncio.to_thread(
            lambda: add_message(db, user_id, session_id, "assistant", error_msg, Status.error)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal Server Error: {type(e).__name__}",
        )


@app.get("/summarize", response_model=SummaryResponse)
async def summarize(
    user_id_param: str = QueryParam(..., alias="user-id", description="User ID is required"),
    session_id_param: str = QueryParam(..., alias="session-id", description="Session ID is required"),
    db: Session = Depends(get_db),
    openai_client: OpenAI = Depends(get_openai_client),
):
    user_id = user_id_param
    session_id = session_id_param

    logger.info(f"Generating summary for user '{user_id}', session '{session_id}'.")
    try:
        messages_for_summary = await asyncio.to_thread(
            lambda: get_recent_messages_for_summary(
                db, user_id, session_id, limit=10
            )
        )

        if not messages_for_summary:
            return SummaryResponse(summary="No history available.")

        conversation_text = "\n".join(
            [f"{msg.role}: {msg.message}" for msg in messages_for_summary]
        )
        if not conversation_text.strip():
            return SummaryResponse(summary="No history available.")

        summary = await asyncio.to_thread(
            lambda: Chatbot.get_summary(openai_client, conversation_text)
        )
        return SummaryResponse(summary=summary)
    except OpenAIError as e:
        logger.exception(
            f"OpenAI error generating summary for user '{user_id}', session '{session_id}': {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable during summarization.",
        )
    except Exception as e:
        logger.exception(
            f"Error generating conversation summary for user '{user_id}', session '{session_id}': %s",
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal Server Error during summarization: {type(e).__name__}",
        )


@app.get("/sessions/{user_id}", response_model=SessionListResponse)
async def list_user_sessions(
    user_id: str = Path(..., description="The ID of the user whose sessions to retrieve"),
    db: Session = Depends(get_db),
):
    logger.info(f"Request received for sessions list for user '{user_id}'.")
    try:
        sessions_data = await asyncio.to_thread(lambda: get_user_sessions(db, user_id))
        sessions_list = [
            SessionInfo(session_id=s["session_id"], start_time=s["start_time"])
            for s in sessions_data
        ]
        return SessionListResponse(sessions=sessions_list)
    except Exception as e:
        logger.exception(f"Error retrieving sessions for user '{user_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user sessions.",
        )


@app.get("/history/{user_id}/{session_id}", response_model=MessageHistoryResponse)
async def get_session_history(
    user_id: str = Path(..., description="User ID"),
    session_id: str = Path(..., description="Session ID"),
    limit: int = QueryParam(100, description="Maximum number of messages to return"),
    db: Session = Depends(get_db),
):
    logger.info(
        f"Request received for message history for user '{user_id}', session '{session_id}'."
    )
    try:
        messages_data = await asyncio.to_thread(
            lambda: get_messages_for_session(db, user_id, session_id, limit=limit)
        )
        history_items = [MessageHistoryItem(**msg) for msg in messages_data]
        return MessageHistoryResponse(messages=history_items)
    except Exception as e:
        logger.exception(
            f"Error retrieving history for user '{user_id}', session '{session_id}': {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session history.",
        )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/clear_db_testing_only")
async def clear_db_endpoint(
    user_id: Optional[str] = QueryParam(None, alias="user-id", description="Optional: User ID to clear history for."),
    session_id: Optional[str] = QueryParam(None, alias="session-id", description="Optional: Specific Session ID to clear (requires user-id). If omitted with user-id, clears ALL sessions for that user."),
    clear_all: bool = QueryParam(False, description="Set to true to clear the entire database (ignores user-id/session-id). Use with caution!"),
    db: Session = Depends(get_db),
):
    target_user_id: Optional[str] = user_id
    target_session_id: Optional[str] = session_id
    log_detail: str = ""
    clear_user_id: Optional[str] = None
    clear_session_id: Optional[str] = None

    if clear_all:
        log_detail = "the ENTIRE database"
        logger.warning("Received request to clear the ENTIRE database.")
        clear_user_id = None
        clear_session_id = None
    elif target_user_id is not None and target_session_id is not None:
        clear_user_id = target_user_id
        clear_session_id = target_session_id
        log_detail = f"session '{clear_session_id}' for user '{clear_user_id}'"
        logger.warning(f"Received request to clear {log_detail}.")
    elif target_user_id is not None and target_session_id is None:
        clear_user_id = target_user_id
        clear_session_id = None
        log_detail = f"ALL sessions for user '{clear_user_id}'"
        logger.warning(f"Received request to clear {log_detail}.")
    elif target_user_id is None and target_session_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot specify session-id without user-id (unless clearing all).",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specify user-id, user-id/session-id, or clear_all=true.",
        )

    try:
        await asyncio.to_thread(
            lambda: clear_db(db, user_id=clear_user_id, session_id=clear_session_id)
        )
        return {"message": f"Conversation database cleared for {log_detail}."}
    except Exception as e:
        logger.exception(f"Error during DB clear operation targeting {log_detail}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear database for {log_detail}.",
        )


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Uvicorn server...")
    uvicorn.run(
        "main:app", host=UVICORN_HOST, port=UVICORN_PORT, reload=UVICORN_RELOAD
    )