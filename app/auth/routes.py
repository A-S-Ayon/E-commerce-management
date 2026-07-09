from fastapi import APIRouter, HTTPException, status
from app.db import get_pool
from app.auth.schemas import SignupRequest, LoginRequest, TokenResponse
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.queries import get_user_by_email, create_user_with_wallet, get_customer_role_id
from fastapi import Depends
from app.auth.dependencies import get_current_user
from app.auth.queries import (
    get_user_by_id, create_password_reset, get_valid_reset,
    mark_reset_used, update_user_password,
)
from app.auth.schemas import ForgotPasswordRequest, ResetPasswordRequest
from app.email.mailer import send_reset_email
from app.config import settings
from datetime import datetime, timezone

from app.auth.queries import (
    create_verification_code, get_valid_code, mark_code_used, mark_user_verified,
)
from app.auth.schemas import VerifyEmailRequest, ResendCodeRequest
from app.email.mailer import send_verification_email



router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def read_current_user(current_user: dict = Depends(get_current_user)):
    return current_user



@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await get_user_by_email(conn, payload.email)
        if user:
            token = await create_password_reset(conn, user["id"])
            reset_link = f"{settings.FRONTEND_RESET_URL}?token={token}"
            await send_reset_email(user["email"], reset_link)

    # Always return the same message whether or not the email exists —
    # prevents leaking which emails are registered
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        reset = await get_valid_reset(conn, payload.token)

        if not reset:
            raise HTTPException(400, "Invalid or expired reset token")
        if reset["used"]:
            raise HTTPException(400, "This reset link has already been used")
        if reset["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "This reset link has expired")

        new_hash = hash_password(payload.new_password)
        await update_user_password(conn, reset["user_id"], new_hash)
        await mark_reset_used(conn, reset["id"])

    return {"message": "Password has been reset successfully"}



@router.post("/signup")
async def signup(payload: SignupRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await get_user_by_email(conn, payload.email)
        if existing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

        role_id = await get_customer_role_id(conn)
        hashed = hash_password(payload.password)
        user = await create_user_with_wallet(conn, payload.name, payload.email, hashed, role_id)

        code = await create_verification_code(conn, user["id"])

    await send_verification_email(user["email"], code)

    # No token issued yet — user must verify before logging in
    return {"message": "Signup successful. Check your email for a verification code."}


@router.post("/verify-email", response_model=TokenResponse)
async def verify_email(payload: VerifyEmailRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await get_user_by_email(conn, payload.email)
        if not user:
            raise HTTPException(400, "Invalid email or code")

        record = await get_valid_code(conn, user["id"], payload.code)
        if not record:
            raise HTTPException(400, "Invalid email or code")
        if record["used"]:
            raise HTTPException(400, "This code has already been used")
        if record["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "This code has expired")

        await mark_code_used(conn, record["id"])
        await mark_user_verified(conn, user["id"])

    token = create_access_token(user["id"], user["role_id"])
    return TokenResponse(access_token=token)


@router.post("/resend-code")
async def resend_code(payload: ResendCodeRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await get_user_by_email(conn, payload.email)
        if user and not user["is_verified"]:
            code = await create_verification_code(conn, user["id"])
            await send_verification_email(user["email"], code)

    return {"message": "If that email needs verification, a new code has been sent."}


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await get_user_by_email(conn, payload.email)

    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    if not user["is_verified"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please verify your email before logging in")

    token = create_access_token(user["id"], user["role_id"])
    return TokenResponse(access_token=token)