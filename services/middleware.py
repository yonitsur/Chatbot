from fastapi import FastAPI, Request
from sqlalchemy.exc import SQLAlchemyError
import logging
from services.conversation_db import SessionLocal

logger = logging.getLogger(__name__)


async def db_session_middleware(request: Request, call_next):
    """
    FastAPI middleware to manage database sessions.

    This middleware creates a new database session for each request and
    makes it available to the request's state. It also handles session
    commit and rollback, and ensures the session is closed properly.
    """
    try:
        request.state.db = SessionLocal()
        response = await call_next(request)
        if response.status_code < 400:
            try:
                request.state.db.commit()
            except SQLAlchemyError as e:
                logger.error(f"Error during database commit: {e}")
                request.state.db.rollback()
        else:
            request.state.db.rollback()
    except Exception as e:
        logger.error(f"Unexpected error during request processing: {e}")
        if hasattr(request.state, "db"):
            request.state.db.rollback()
        raise
    finally:
        if hasattr(request.state, "db"):
            request.state.db.close()
    return response


def get_db(request: Request):
    """
    Dependency to get the database session from the request's state.

    Usage: db: Session = Depends(get_db)
    """
    return request.state.db


def setup_middleware(app: FastAPI):
    """
    Function to register the database session middleware with the FastAPI app.
    """
    app.middleware("http")(db_session_middleware)