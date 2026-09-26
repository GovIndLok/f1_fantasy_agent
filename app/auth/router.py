from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.schema import RegisterCredentials, UserCredentials
from app.auth.utils import CredentialsDep, SupabaseDep, get_current_player_id

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(creds: RegisterCredentials, supabase: SupabaseDep):
    """
    Register a new player.

    Creates the Supabase Auth account and persists the username inside
    Supabase user_metadata.  No local user/player table is written —
    Supabase is the single source of truth for user identity.
    """
    try:
        res = supabase.auth.sign_up(
            {
                "email": creds.email,
                "password": creds.password,
                "options": {"data": {"username": creds.username}},
            }
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return {"message": "User registered successfully", "user_id": res.user.id}


@router.post("/login")
def login_user(creds: UserCredentials, supabase: SupabaseDep):
    """
    Log in an existing player.

    Authenticates with Supabase and returns a JWT session token. Use the token
    as a Bearer token on all authenticated endpoints.
    """
    try:
        res = supabase.auth.sign_in_with_password(
            {"email": creds.email, "password": creds.password}
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return {"access_token": res.session.access_token, "token_type": "bearer"}


@router.post("/logout")
def logout_user(
    credentials: CredentialsDep,
    supabase: SupabaseDep,
    _: str = Depends(get_current_player_id),
):
    """
    Log out the current player.

    Revokes the current session token in Supabase via the admin API,
    which accepts the JWT directly — no session state required.
    Requires a valid Bearer token.
    """
    try:
        supabase.auth.admin.sign_out(credentials.credentials)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token revocation failed: {e}",
        ) from e

    return {"message": "Successfully logged out"}

