from pydantic import BaseModel
from datetime import datetime

class CreditRequest(BaseModel):
    user_id: str
    amount: float

class WalletOut(BaseModel):
    id: int
    user_id: str
    balance: float

class TransactionOut(BaseModel):
    id: int
    amount: float
    type: str
    created_at: datetime