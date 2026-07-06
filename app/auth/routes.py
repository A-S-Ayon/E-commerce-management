from fastapi import APIRouter, HTTPException, status
from app.db import get_pool
from app.auth.schemas import SignupRequest, LoginRequest, TokenResponse
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.queries import get_user_by_email, create_user_with_wallet, get_customer_role_id
from fastapi import Depends
from app.auth.dependencies import get_current_user



router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def read_current_user(current_user: dict = Depends(get_current_user)):
    return current_user

@router.post("/signup", response_model=TokenResponse)
async def signup(payload: SignupRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await get_user_by_email(conn, payload.email)
        if existing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

        role_id = await get_customer_role_id(conn)
        hashed = hash_password(payload.password)
        user = await create_user_with_wallet(conn, payload.name, payload.email, hashed, role_id)

    token = create_access_token(user["id"], user["role_id"])
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await get_user_by_email(conn, payload.email)

    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    token = create_access_token(user["id"], user["role_id"])
    return TokenResponse(access_token=token)