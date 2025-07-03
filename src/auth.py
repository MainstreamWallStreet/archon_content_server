"""
Authentication module for API key validation.
"""

import os
from typing import Annotated

from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer

from src.config import get_setting

# Security scheme for API key authentication
security = HTTPBearer(auto_error=False)


async def verify_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> str:
    """
    Verify API key from either Authorization header or X-API-Key header.
    
    Parameters
    ----------
    authorization : str | None
        Authorization header (Bearer token)
    x_api_key : str | None
        X-API-Key header
        
    Returns
    -------
    str
        The verified API key
        
    Raises
    ------
    HTTPException
        If API key is missing or invalid
    """
    # Get the expected API key from configuration
    expected_api_key = get_setting("ARCHON_API_KEY")
    
    # Check X-API-Key header first (preferred)
    if x_api_key:
        if x_api_key == expected_api_key:
            return x_api_key
        else:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
    
    # Check Authorization header (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
        if token == expected_api_key:
            return token
        else:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # No valid API key found
    raise HTTPException(
        status_code=401,
        detail="API key required. Use X-API-Key header or Authorization: Bearer <key>",
        headers={"WWW-Authenticate": "ApiKey"},
    )


# Dependency for endpoints that require authentication
APIKeyAuth = Annotated[str, Depends(verify_api_key)] 