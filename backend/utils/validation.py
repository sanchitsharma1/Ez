import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from email_validator import validate_email, EmailNotValidError
from pydantic import ValidationError
import validators

def validate_email_address(email: str) -> bool:
    """Validate email address format."""
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False

def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength and return detailed feedback."""
    errors = []
    score = 0
    
    # Length check
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    elif len(password) >= 12:
        score += 2
    else:
        score += 1
    
    # Uppercase check
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    else:
        score += 1
    
    # Lowercase check
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    else:
        score += 1
    
    # Number check
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one number")
    else:
        score += 1
    
    # Special character check
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        errors.append("Password must contain at least one special character")
    else:
        score += 1
    
    # Common password check
    common_passwords = [
        "password", "123456", "password123", "admin", "qwerty",
        "letmein", "welcome", "monkey", "1234567890"
    ]
    if password.lower() in common_passwords:
        errors.append("Password is too common")
        score = max(0, score - 2)
    
    # Determine strength
    if score >= 5 and not errors:
        strength = "strong"
    elif score >= 3:
        strength = "medium"
    else:
        strength = "weak"
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "strength": strength,
        "score": score
    }

def validate_username(username: str) -> Dict[str, Any]:
    """Validate username format."""
    errors = []
    
    # Length check
    if len(username) < 3:
        errors.append("Username must be at least 3 characters long")
    elif len(username) > 50:
        errors.append("Username must be less than 50 characters")
    
    # Character check
    if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
        errors.append("Username can only contain letters, numbers, dots, dashes, and underscores")
    
    # Start/end check
    if username.startswith('.') or username.endswith('.'):
        errors.append("Username cannot start or end with a dot")
    
    # Consecutive dots check
    if '..' in username:
        errors.append("Username cannot contain consecutive dots")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }

def validate_agent_id(agent_id: str) -> bool:
    """Validate agent ID format."""
    valid_agents = ["carol", "alex", "sofia", "morgan", "judy"]
    return agent_id.lower() in valid_agents

def validate_content_type(content_type: str) -> bool:
    """Validate memory content type."""
    valid_types = ["conversation", "task", "document", "voice_transcription", "approval"]
    return content_type in valid_types

def validate_priority(priority: str) -> bool:
    """Validate task priority."""
    valid_priorities = ["low", "medium", "high", "urgent"]
    return priority in valid_priorities

def validate_status(status: str, valid_statuses: List[str]) -> bool:
    """Validate status against allowed values."""
    return status in valid_statuses

def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID format."""
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(uuid_string))

def validate_datetime_string(datetime_str: str) -> Optional[datetime]:
    """Validate and parse datetime string."""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(datetime_str, fmt)
            # If no timezone info, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    return None

def validate_url(url: str) -> bool:
    """Validate URL format."""
    return validators.url(url) is True

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format (international)."""
    # Basic international phone number validation
    pattern = r"^\+?1?\d{9,15}$"
    return bool(re.match(pattern, phone.replace(' ', '').replace('-', '')))

def validate_json_data(data: Any, required_fields: List[str] = None) -> Dict[str, Any]:
    """Validate JSON data structure."""
    errors = []
    
    if not isinstance(data, dict):
        errors.append("Data must be a JSON object")
        return {"is_valid": False, "errors": errors}
    
    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }

def validate_file_size(file_size: int, max_size_mb: int = 10) -> bool:
    """Validate file size."""
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_size_bytes

def validate_file_type(filename: str, allowed_extensions: List[str]) -> bool:
    """Validate file type by extension."""
    if not filename:
        return False
    
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    return f".{extension}" in [ext.lower() for ext in allowed_extensions]

def sanitize_string(text: str, max_length: int = None, allow_html: bool = False) -> str:
    """Sanitize string input."""
    if not isinstance(text, str):
        return ""
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Remove HTML tags if not allowed
    if not allow_html:
        text = re.sub(r'<[^>]+>', '', text)
    
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')
    
    # Truncate if max_length specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text

def validate_search_query(query: str) -> Dict[str, Any]:
    """Validate search query."""
    errors = []
    
    if not query or not query.strip():
        errors.append("Search query cannot be empty")
    elif len(query.strip()) < 2:
        errors.append("Search query must be at least 2 characters long")
    elif len(query) > 1000:
        errors.append("Search query is too long")
    
    # Check for SQL injection patterns
    suspicious_patterns = [
        r"union\s+select", r"drop\s+table", r"delete\s+from",
        r"insert\s+into", r"update\s+set", r"--", r"/\*", r"\*/"
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, query.lower()):
            errors.append("Query contains invalid characters")
            break
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "sanitized_query": sanitize_string(query, max_length=1000)
    }