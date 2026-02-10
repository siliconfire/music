from datetime import datetime, timedelta, timezone

from fastapi import Security, HTTPException, Depends
from fastapi.security import APIKeyHeader
from jose import jwt, JWTError
from starlette.status import HTTP_403_FORBIDDEN

SECRET_KEY = "super-secret-don't-tell-anyone-ts"    # Seriously, move this to .env later lol
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

API_KEY_NAME = "X-Session-ID"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def create_access_token(user_id: str):
    """Encodes the user's unique ID into the 'sub' field of the JWT."""
    to_encode = {"sub": str(user_id)}
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_permanent_token(user_id: str):
    """Encodes the user's unique ID into the 'sub' field of the JWT without an expiration."""
    to_encode = {"sub": str(user_id)}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Security(api_key_header)):
    """Decodes the JWT and returns the full payload (containing the 'sub' ID)."""
    if not token:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="No token provided")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="token is missing the id field (getting a new one might help)"
            )
        return payload

    except JWTError:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="invalid/expired token"
        )


def is_token_valid(token: str) -> bool:
    """Checks if a token is valid and not expired. Returns a strict boolean."""
    # This will NOT raise an exception. Use for manual checks, not Depends().
    if not token:
        return False
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False