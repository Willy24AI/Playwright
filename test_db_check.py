# test_db_check.py - Run this to see what's in the network column

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Fetch a few profiles that don't have mla_uuid yet
response = supabase.table('profiles').select('id, profile_id, network, mla_uuid').is_('mla_uuid', 'null').limit(3).execute()

for p in response.data:
    print(f"\nProfile: {p['profile_id']}")
    print(f"  mla_uuid: {p['mla_uuid']}")
    print(f"  network: {p['network']}")
    print(f"  network type: {type(p['network'])}")