from supabase import Client, create_client
from dotenv import load_dotenv
import os
load_dotenv()

SupabaseUrl=os.getenv("SUPABASE_URL")
SupabaseKey=os.getenv("SUPABASE_KEY")

supabase: Client = create_client(
    SupabaseUrl,
    SupabaseKey,
)
