import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.core.config import settings

_basic = HTTPBasic(auto_error=False)

def require_auth(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> str:
    """Single-owner HTTP Basic gate. Configure APP_USERNAME/APP_PASSWORD and use HTTPS."""
    if not settings.app_username or not settings.app_password:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    valid_user = secrets.compare_digest(credentials.username, settings.app_username)
    valid_password = secrets.compare_digest(credentials.password, settings.app_password)
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
