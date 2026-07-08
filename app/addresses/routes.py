from fastapi import APIRouter, Depends, HTTPException
from app.db import get_pool
from app.auth.dependencies import get_current_user
from app.addresses.queries import list_addresses, create_address, delete_address
from app.addresses.schemas import AddressCreate, AddressOut

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("", response_model=list[AddressOut])
async def get_my_addresses(current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await list_addresses(conn, current_user["user_id"])
    return [{**dict(r), "user_id": str(r["user_id"])} for r in rows]


@router.post("", response_model=AddressOut, status_code=201)
async def add_address(payload: AddressCreate, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await create_address(conn, current_user["user_id"], payload.model_dump())
    return {**dict(row), "user_id": str(row["user_id"])}


@router.delete("/{address_id}", status_code=204)
async def remove_address(address_id: int, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await delete_address(conn, address_id, current_user["user_id"])
        if result == "DELETE 0":
            raise HTTPException(404, "Address not found")
    return None