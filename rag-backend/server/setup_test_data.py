import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def setup_test_data():
    print("Signing up test user...")
    # 1. Create a user in Supabase Auth (this should trigger your public.users trigger)
    auth_response = supabase.auth.sign_up({
        "email": "yashthakurr001@gmail.com",
        "password": "SecurePassword123!",
        "options": {
            "data": {
                "name": "Test User 1"
            }
        }
    })
    
    if not auth_response.user:
        print("Failed to create user. Perhaps the user already exists?")
        return
        
    user_id = auth_response.user.id
    print(f"✅ User created successfully! ID: {user_id}")
    
    # 2. Create a workspace for this user
    print("Creating workspace for user...")
    workspace_response = supabase.table("workspace").insert({
        "cust_id": user_id,
        "temperature": 0.7,
        "model_name": "llama-3.3-70b-versatile",
        "provider": "groq",
        "system_prompt": "You are a helpful assistant.",
        "search_enabled": False
    }).execute()
    
    workspace_id = workspace_response.data[0]["id"]
    print(f"✅ Workspace created successfully! ID: {workspace_id}")
    
    print("\n" + "="*50)
    print("🎉 TEST DATA READY FOR POSTMAN 🎉")
    print("="*50)
    print(f'"customer_id": "{user_id}"')
    print(f'"workspace_id": "{workspace_id}"')
    print("="*50)

if __name__ == "__main__":
    setup_test_data()
