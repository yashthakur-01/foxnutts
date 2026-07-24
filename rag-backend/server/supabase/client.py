from supabase import CreateClient
from dotenv import load_dotenv
import os
load_dotenv()

SupabaseUrl=os.getenv("SUPABASE_URL")
SupabaseKey=os.getenv("SUPABASE_KEY")

supabase = CreateClient(
    url=os.environ.get(SupabaseUrl),
    key=os.environ.get(SupabaseKey),
)
