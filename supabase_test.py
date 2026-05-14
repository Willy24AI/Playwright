import os
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
print("URL:", os.getenv("SUPABASE_URL"))
print("Key present:", bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")))
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
result = sb.table("profiles").select("id", count="exact").limit(1).execute()
print(f"OK - Profiles count: {result.count}")
