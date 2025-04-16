import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_KEY", "")

CHATBOT_MODEL = os.getenv("CHATBOT_MODEL", "gpt-4o-mini")
DOMAIN_CLASSIFIER_MODEL = os.getenv("DOMAIN_CLASSIFIER_MODEL", "gpt-4o-mini")
QUERY_REWRITER_MODEL = os.getenv("QUERY_REWRITER_MODEL", "gpt-4o-mini")
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gpt-4o-mini")

CHATBOT_TEMPERATURE = float(os.getenv("CHATBOT_TEMPERATURE", "0.3"))
DOMAIN_CLASSIFIER_TEMPERATURE = float(os.getenv("DOMAIN_CLASSIFIER_TEMPERATURE", "0.0"))
DOMAIN_CLASSIFIER_MAX_TOKENS = int(os.getenv("DOMAIN_CLASSIFIER_MAX_TOKENS", "5"))
QUERY_REWRITER_TEMPERATURE = float(os.getenv("QUERY_REWRITER_TEMPERATURE", "0.0"))
QUERY_REWRITER_MAX_TOKENS = int(os.getenv("QUERY_REWRITER_MAX_TOKENS", "50"))
SUMMARY_TEMPERATURE = float(os.getenv("SUMMARY_TEMPERATURE", "0.3"))
SUMMARY_MAX_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", "150"))

HISTORY_LIMIT_FOR_LLM = int(os.getenv("HISTORY_LIMIT_FOR_LLM", "10"))
SUMMARY_HISTORY_LIMIT = int(os.getenv("SUMMARY_HISTORY_LIMIT", "10"))
HISTORY_LIMIT_FOR_CONTEXT = int(os.getenv("HISTORY_LIMIT_FOR_CONTEXT", "4"))
DOMAIN_CHECK_HISTORY_SIZE = int(os.getenv("DOMAIN_CHECK_HISTORY_SIZE", "2"))
DOMAIN_CHECK_RAG_SUMMARY_COUNT = int(os.getenv("DOMAIN_CHECK_RAG_SUMMARY_COUNT", "2"))

QDRANT_MODEL_NAME = os.getenv("QDRANT_MODEL_NAME", "all-MiniLM-L6-v2")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "startups")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_TOP_K = int(os.getenv("QDRANT_TOP_K", "7"))

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///conversation.db")

DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "default_user")
DEFAULT_SESSION_ID = os.getenv("DEFAULT_SESSION_ID", "default_session")
MESSAGE_STATUS_CHECK_DELAY_SECONDS = float(os.getenv("MESSAGE_STATUS_CHECK_DELAY_SECONDS", "0.3"))
QUERY_REWRITER_MIN_LENGTH = int(os.getenv("QUERY_REWRITER_MIN_LENGTH", "3"))
REJECTION_MESSAGE = os.getenv("REJECTION_MESSAGE",
                              "My expertise is limited to startups and venture capital. Please ask a relevant question.")
NO_HISTORY_SUMMARY_MESSAGE = os.getenv("NO_HISTORY_SUMMARY_MESSAGE",
                                       "No conversation history available for this user/session to summarize.")

API_TITLE = os.getenv("API_TITLE", "Startup Knowledge Chatbot API")
UVICORN_HOST = os.getenv("UVICORN_HOST", "0.0.0.0")
UVICORN_PORT = int(os.getenv("UVICORN_PORT", "8000"))
UVICORN_RELOAD = os.getenv("UVICORN_RELOAD", "True").lower() in ('true', '1', 'yes')

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

