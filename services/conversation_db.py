import datetime
import logging
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum as SQLEnum, desc, asc, Index, func
from sqlalchemy.orm import sessionmaker, scoped_session, Session, declarative_base
import enum
import threading

from config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
db_lock = threading.Lock()


class Status(enum.Enum):
    processed = "processed"
    pending = "pending"
    rejected = "rejected"
    skipped = "skipped"
    error = "error"


class Conversation(Base):
    __tablename__ = "conversation"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    role = Column(String, nullable=False)
    message = Column(String, nullable=False)
    status = Column(SQLEnum(Status), default=Status.pending, nullable=False)
    __table_args__ = (Index('ix_user_session_id', 'user_id', 'session_id'),
                      Index('ix_user_session_status_id', 'user_id', 'session_id', 'status', 'id'),
                      Index('ix_user_session_time', 'user_id', 'session_id', 'timestamp'))


    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "role": self.role,
            "message": self.message,
            "status": self.status.value,
        }


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Conversation DB initialized successfully.")
    except Exception as e:
        logger.exception("Error initializing conversation DB: %s", e)
        raise


def add_message(db: Session, user_id: str, session_id: str, role: str, message: str,
                status: Status = Status.pending) -> int:
    try:
        conversation = Conversation(
            user_id=user_id,
            session_id=session_id,
            role=role,
            message=message,
            status=status
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        logger.info(
            "Added %s message for user '%s' session '%s' with id %s and status %s.",
            role, user_id, session_id, conversation.id, status.value
        )
        return conversation.id
    except Exception as e:
        db.rollback()
        logger.exception(
            "Error adding message to conversation DB for user '%s' session '%s': %s",
            user_id, session_id, e
        )
        return -1


def update_message_status(db: Session, message_id: int, status: Status):
    if message_id <= 0:
        logger.warning("Attempted to update message with invalid ID: %s", message_id)
        return
    try:
        conversation = db.query(Conversation).filter(Conversation.id == message_id).first()
        if conversation:
            conversation.status = status
            db.commit()
            logger.info(
                "Updated message id %s (user '%s', session '%s') to status %s.",
                message_id, conversation.user_id, conversation.session_id, status.value
            )
        else:
            logger.warning("Message with id %s not found for status update.", message_id)
    except Exception as e:
        db.rollback()
        logger.exception("Error updating message status in conversation DB for id %s: %s", message_id, e)


def get_message_status(db: Session, message_id: int) -> Status | None:
    if message_id <= 0:
        return None
    try:
        result = db.query(Conversation.status).filter(Conversation.id == message_id).first()
        return result[0] if result else None
    except Exception as e:
        logger.exception("Error getting message status for id %s: %s", message_id, e)
        return None


def get_recent_messages_for_summary(db: Session, user_id: str, session_id: str, limit: int = 10) -> list[Conversation]:
    try:
        messages = db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.session_id == session_id,
            Conversation.status.in_([Status.processed, Status.pending, Status.error])
        ).order_by(desc(Conversation.id)).limit(limit).all()
        messages.reverse()
        result = messages
        logger.info(f"Retrieved {len(result)} messages for summary for user '{user_id}', session '{session_id}'.")
        return result
    except Exception as e:
        logger.exception(
            "Error retrieving recent messages for summary for user '%s', session '%s': %s",
            user_id, session_id, e
        )
        return []

def get_messages_for_session(db: Session, user_id: str, session_id: str, limit: int = 100) -> list[dict]:
    """Gets processed user and assistant messages for displaying a session's history."""
    try:
        messages = db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.session_id == session_id,
            Conversation.status.in_([Status.processed, Status.error, Status.rejected]),
            Conversation.role.in_(["user", "assistant"])
        ).order_by(asc(Conversation.id)).limit(limit).all()


        result = [msg.to_dict() for msg in messages]

        logger.info(f"Retrieved {len(result)} displayable messages for user '{user_id}', session '{session_id}'.")
        return result
    except Exception as e:
        logger.exception(
            "Error retrieving displayable history for user '%s', session '%s': %s",
            user_id, session_id, e
        )
        return []

def get_user_sessions(db: Session, user_id: str, limit: int = 50) -> list[dict]:
    """Gets a list of session IDs and their start times for a user."""
    try:
        session_data = db.query(
            Conversation.session_id,
            func.min(Conversation.timestamp).label('start_time')
        ).filter(
            Conversation.user_id == user_id
        ).group_by(
            Conversation.session_id
        ).order_by(
            desc('start_time')
        ).limit(limit).all()

        result = [
            {"session_id": session_id, "start_time": start_time.isoformat()}
            for session_id, start_time in session_data
        ]
        logger.info(f"Retrieved {len(result)} sessions for user '{user_id}'.")
        return result
    except Exception as e:
        logger.exception("Error retrieving sessions for user '%s': %s", user_id, e)
        return []


def mark_older_pending_as_skipped(db: Session, user_id: str, session_id: str, current_message_id: int):
    if current_message_id <= 0:
        return

    with db_lock:
        try:
            updated_count = db.query(Conversation).filter(
                Conversation.user_id == user_id,
                Conversation.session_id == session_id,
                Conversation.role == "user",
                Conversation.status == Status.pending,
                Conversation.id < current_message_id
            ).update({"status": Status.skipped}, synchronize_session=False)

            db.commit()
            if updated_count > 0:
                logger.info(
                    "Marked %d older pending user messages as skipped for user '%s' session '%s' before msg %d.",
                    updated_count, user_id, session_id, current_message_id
                )
        except Exception as e:
            db.rollback()
            logger.exception(
                "Error marking older pending messages as skipped for user '%s' session '%s': %s",
                user_id, session_id, e
            )


def clear_db(db: Session, user_id: str | None = None, session_id: str | None = None):
    try:
        query = db.query(Conversation)
        log_detail = ""
        if user_id and session_id:
            query = query.filter(Conversation.user_id == user_id, Conversation.session_id == session_id)
            log_detail = f"session '{session_id}' for user '{user_id}'"
        elif user_id:
            query = query.filter(Conversation.user_id == user_id)
            log_detail = f"all sessions for user '{user_id}'"
            logger.warning(f"Clearing all sessions for user '{user_id}'.")
        else:
            log_detail = "the entire database"
            logger.warning("Clearing the entire conversation database.")


        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        logger.warning(f"Cleared {deleted_count} records from conversation database for {log_detail}.")
    except Exception as e:
        db.rollback()
        logger.exception(f"Error clearing conversation database for {log_detail}: %s", e)

def get_processed_history(db: Session, user_id: str, session_id: str, limit: int = 10) -> list[dict]:
    """Gets limited processed history specifically for LLM context priming."""
    try:
        messages = db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.session_id == session_id,
            Conversation.status == Status.processed,
            Conversation.role.in_(["user", "assistant"])
        ).order_by(desc(Conversation.id)).limit(limit).all()
        messages.reverse()
        result = [{"role": msg.role, "content": msg.message} for msg in messages]
        logger.debug(f"Retrieved {len(result)} processed history messages for LLM context for user '{user_id}', session '{session_id}'.")
        return result
    except Exception as e:
        logger.exception(
            "Error retrieving processed history for LLM context for user '%s', session '%s': %s",
            user_id, session_id, e
        )
        return []