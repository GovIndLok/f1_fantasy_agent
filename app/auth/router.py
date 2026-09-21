from fastapi import APIRouter, HTTPException

from app.auth.schema import UserCredentials
from app.auth.utils import SupabaseDep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register_user(creds: UserCredentials, supabase: SupabaseDep):
    try:
        res = supabase.auth.sign_up({"email": creds.email, "password": creds.password})
        return {"message": "User registered successfully", "user": res.user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/login")
def login_user(creds: UserCredentials, supabase: SupabaseDep):
    try:
        res = supabase.auth.sign_in_with_password(
            {"email": creds.email, "password": creds.password}
        )
        return {"access_token": res.session.access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

