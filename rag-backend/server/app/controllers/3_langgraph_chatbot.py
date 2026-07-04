from typing import Literal,TypedDict, Annotated
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from server.controllers.agent_engine import get_chat_model, graph_builder, AgentState, toolnode

import os

def handle_incoming_widget_message(
    tenant_id: str,
    chatbot_id: str,
    session_id: str,
    raw_user_message: str,
    history_from_cache: list,
    system_prompt_from_db: str,
    settings_from_db: dict
) -> AgentState:
    
    # generate message history for the agent state
    formatted_history = []
    
    formatted_history.append(SystemMessage(content=system_prompt_from_db))
    
    for msg in history_from_cache:
        if msg["sender"] == "user":
            formatted_history.append(HumanMessage(content=msg["text"]))
        elif msg["sender"] == "bot":
            formatted_history.append(AIMessage(content=msg["text"]))
            
    # add the new incoming message to the history
    formatted_history.append(HumanMessage(content=raw_user_message))
    
    agent_state = AgentState(messages=formatted_history)
    
    return agent_state
    
    