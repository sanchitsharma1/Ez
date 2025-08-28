import logging
import sys
from pathlib import Path
from typing import Any, Dict
import structlog
from structlog.stdlib import LoggerFactory
from .config import settings

def setup_logging() -> None:
    """Configure structured logging for the application."""
    
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if not settings.DEBUG else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )
    
    # Configure file handlers
    file_handler = logging.FileHandler(log_dir / "supremeai.log")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    
    # Configure error file handler
    error_handler = logging.FileHandler(log_dir / "error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    
    # Add handlers to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)

class LoggerMixin:
    """Mixin to add logging capabilities to classes."""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get logger for this class."""
        return get_logger(self.__class__.__name__)

def log_function_call(func_name: str, **kwargs: Any) -> None:
    """Log function calls with parameters."""
    logger = get_logger("function_calls")
    logger.info(f"Calling {func_name}", **kwargs)

def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """Log errors with context."""
    logger = get_logger("errors")
    logger.error(
        "Error occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context or {},
        exc_info=True
    )

def log_user_action(user_id: str, action: str, **kwargs: Any) -> None:
    """Log user actions for audit purposes."""
    logger = get_logger("user_actions")
    logger.info(
        f"User action: {action}",
        user_id=user_id,
        action=action,
        **kwargs
    )

def log_agent_interaction(agent_id: str, action: str, **kwargs: Any) -> None:
    """Log agent interactions."""
    logger = get_logger("agent_interactions")
    logger.info(
        f"Agent {agent_id}: {action}",
        agent_id=agent_id,
        action=action,
        **kwargs
    )

def log_api_call(endpoint: str, method: str, user_id: str = None, **kwargs: Any) -> None:
    """Log API calls."""
    logger = get_logger("api_calls")
    logger.info(
        f"{method} {endpoint}",
        endpoint=endpoint,
        method=method,
        user_id=user_id,
        **kwargs
    )