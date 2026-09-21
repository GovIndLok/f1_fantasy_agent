"""
Auth utilities — Supabase client factory and token verification.

Swap the auth backend here without touching routing or schemas.
"""
import os
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

_security = HTTPBearer()


def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
    return create_client(url, key)


SupabaseDep = Annotated[Client, Depends(get_supabase)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials, Depends(_security)]


def get_current_player_id(credentials: CredentialsDep, supabase: SupabaseDep) -> str:
    try:
        user_res = supabase.auth.get_user(credentials.credentials)
        if not user_res or not user_res.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        return user_res.user.id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {e}",
        ) from e

