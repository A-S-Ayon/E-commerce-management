import os
from langchain_fireworks import ChatFireworks
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from app.support.tools import make_tools_for_user
from dotenv import load_dotenv
load_dotenv()


SYSTEM = """
You are a helpful shopping assistant for an authenticated customer.

Use the appropriate tool whenever real customer/store data is needed:
- Orders: get_my_orders, get_order_detail
- Wallet: get_my_wallet_balance
- Cart: view_cart, add_to_cart
- Products: check_product_availability
- Policies: search_documents
- Cancellation: get_order_detail → ask confirmation → cancel_order

Never invent or guess data. Do not ask for identity verification.
Only add items when explicitly requested.
Only cancel after explicit confirmation.
For general conversation, respond normally.
"""




def build_graph_for_user(user_id: str, checkpointer):
    tools = make_tools_for_user(user_id)
    model = llm = ChatFireworks(
    api_key=os.getenv("FIREWORKS_API_KEY"),
    model="accounts/fireworks/models/deepseek-v4-flash",
    timeout=30,
    )
    model_with_tools = model.bind_tools(tools)
    async def call_model(state: MessagesState):
        messages = [SystemMessage(content=SYSTEM), *state["messages"]]
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)