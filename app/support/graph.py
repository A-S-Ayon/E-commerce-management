from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage
from app.auth.dependencies import get_current_user
from app.db import get_support_checkpointer
from app.support.graph import build_graph_for_user
from app.support.schemas import ChatRequest, ChatResponse
import os
from langchain_fireworks import ChatFireworks

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    checkpointer = get_support_checkpointer()

    graph_app = build_graph_for_user(user_id, checkpointer)

    config = {"configurable": {"thread_id": user_id}}
    result = await graph_app.ainvoke(
        {"messages": [HumanMessage(content=payload.message)]},
        config=config,
    )

    reply = result["messages"][-1].content
    return ChatResponse(reply=reply)


@router.get("/test-fireworks")
async def test_fireworks():
    api_key = os.getenv("FIREWORKS_API_KEY")

    print("=== FIREWORKS TEST ===")
    print("Key exists:", bool(api_key))
    print("Key length:", len(api_key) if api_key else 0)
    print("Key prefix:", api_key[:8] if api_key else None)

    llm = ChatFireworks(
        api_key=api_key,
        model="accounts/fireworks/models/glm-5p2",
        timeout=30,
    )

    response = await llm.ainvoke(
        "What is the capital of France?"
    )

    return {
        "success": True,
        "response": response.content,
    }
