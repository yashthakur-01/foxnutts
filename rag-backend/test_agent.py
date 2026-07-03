import os
import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from agent_engine import get_chatbot_agent

# Load environment variables
load_dotenv()

def main():
    # 1. Get and compile the LangGraph agent
    graph_builder = get_chatbot_agent()
    app = graph_builder.compile()
    
    # 2. Setup your configuration (must match the tenantId/workspaceId used in embedding pipeline)
    config = {
        "configurable": {
            "customerId": "user1",
            "workspaceId": "workspace1"
        }
    }
    
    print("\nAgent Engine is ready! Type 'quit' or 'exit' to stop.")
    print("-" * 50)
    
    # Track conversation history and last known state
    messages = []
    last_state = None
    state = {
            "messages": messages,
            "query": [], # Pass query as a list because of operator.add
            "system_prompt": "You are a helpful and polite RAG assistant.",
            "max_iter": 0,
            "model": {
                "provider": "groq",
                "model_name": "llama-3.3-70b-versatile", # Using Groq's super fast Llama3 model
                "temperature": 0.4,
                "max_tokens": 1024
            },
            "search_enabled": False
        }
        
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["quit", "exit"]:
            print("Goodbye!")
            if last_state:
                # Custom serializer to handle Langchain objects (like HumanMessage/AIMessage)
                def custom_serializer(obj):
                    if hasattr(obj, "model_dump"):
                        return obj.model_dump()
                    elif hasattr(obj, "dict"):
                        return obj.dict()
                    return str(obj)
                
                with open("output.json", "w", encoding="utf-8") as f:
                    json.dump(last_state, f, indent=4, default=custom_serializer)
                print("📝 Final agent state (including trajectory and errors) saved to output.json!")
            break
            
        if last_state:
            last_state["messages"].append(HumanMessage(content=user_input))
            last_state["query"].append(user_input)
            state_to_run = last_state
        else:
            state["messages"].append(HumanMessage(content=user_input))
            state["query"].append(user_input)        
            state_to_run = state
            
        print("\n⏳ Processing...")
        
        # 4. Stream the execution so you can see exactly which nodes the engine is routing through
        try:
            final_state = None
            # The last yielded value is the complete final state!
            for state_update in app.stream(state_to_run, config=config, stream_mode="values"):
                final_state = state_update
                last_state = final_state
            
            final_message = final_state["messages"][-1].content
            
            print(f"\nBot: {final_message}")
            print("-" * 50)
            
            messages.append(final_state["messages"][-1])
            
        except Exception as e:
            print(f"\n❌ An error occurred during execution: {e}")

if __name__ == "__main__":
    main()
