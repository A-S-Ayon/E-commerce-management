from fastapi import APIRouter, Depends, HTTPException
from app.db import get_pool
from app.auth.dependencies import get_current_user, require_admin
from app.products.queries import log_admin_action
from app.wallet.queries import credit_wallet, get_wallet, get_wallet_transactions
from app.wallet.schemas import CreditRequest, WalletOut, TransactionOut

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.get("", response_model=WalletOut)
async def view_my_wallet(current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        wallet = await get_wallet(conn, current_user["user_id"])
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    return {**dict(wallet), "user_id": str(wallet["user_id"])}


@router.get("/transactions", response_model=list[TransactionOut])
async def view_my_transactions(current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await get_wallet_transactions(conn, current_user["user_id"])
    return [dict(r) for r in rows]



@router.post("/credit", response_model=WalletOut)
async def admin_credit_wallet(payload: CreditRequest, admin: dict = Depends(require_admin)):
    if payload.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    pool = get_pool()
    async with pool.acquire() as conn:
        wallet = await credit_wallet(conn, payload.user_id, payload.amount)
        if not wallet:
            raise HTTPException(404, "User wallet not found")
        await log_admin_action(
            conn, admin["user_id"], f"Credited {payload.amount} to user {payload.user_id}"
        )
    return {**dict(wallet), "user_id": str(wallet["user_id"])}