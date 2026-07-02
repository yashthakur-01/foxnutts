import os
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
            "tenantId": "user1",
            "workspaceId": "workspace1"
        }
    }
    
    print("\n🤖 Agent Engine is ready! Type 'quit' or 'exit' to stop.")
    print("-" * 50)
    
    # Track conversation history
    messages = []
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break
            
        messages.append(HumanMessage(content=user_input))
        
        # 3. Define the initial state required by AgentState
        state = {
            "messages": messages,
            "query": [user_input], # Pass query as a list because of operator.add
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
        
        print("\n⏳ Processing...")
        
        # 4. Stream the execution so you can see exactly which nodes the engine is routing through
        try:
            final_state = None
            # Using stream_mode="values" yields the full state after each node executes.
            # The last yielded value is the complete final state!
            for state_update in app.stream(state, config=config, stream_mode="values"):
                final_state = state_update
            
            final_message = final_state["messages"][-1].content
            
            print(f"\nBot: {final_message}")
            print("-" * 50)
            
            # Update our history with the bot's response for the next loop
            messages.append(final_state["messages"][-1])
            
        except Exception as e:
            print(f"\n❌ An error occurred during execution: {e}")

if __name__ == "__main__":
    main()
