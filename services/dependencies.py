import logging
from functools import lru_cache
from openai import OpenAI

from config import OPENAI_KEY, QDRANT_COLLECTION_NAME
from services.neural_search_service import NeuralSearcher
from services.conversation_db import SessionLocal

logger = logging.getLogger(__name__)


@lru_cache()
def get_openai_client() -> OpenAI:
    logger.debug("Creating OpenAI client instance")
    return OpenAI(api_key=OPENAI_KEY)


@lru_cache()
def get_neural_searcher() -> NeuralSearcher:
    logger.debug("Creating NeuralSearcher instance")
    try:
        return NeuralSearcher(collection_name=QDRANT_COLLECTION_NAME)
    except RuntimeError as e:
        logger.exception("Failed to initialize NeuralSearcher in dependency.")
        raise


def get_db_session():
    db = SessionLocal()
    logger.debug(f"DB Session {id(db)} created.")
    try:
        yield db
    except Exception:
        db.rollback()
        logger.exception("Rolling back DB session due to exception.")
        raise
    finally:
        logger.debug(f"DB Session {id(db)} removed.")
        SessionLocal.remove()
