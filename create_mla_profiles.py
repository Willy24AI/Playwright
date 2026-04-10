import os
import hashlib
import asyncio
import time
import httpx
from dotenv import load_dotenv
from supabase import create_client

# Load Environment Variables
load_dotenv()
SUPABASE_URL     = os.getenv("SUPABASE_URL")
SUPABASE_KEY     = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
MLX_EMAIL        = os.getenv("MLX_EMAIL")
MLX_PASSWORD     = os.getenv("MLX_PASSWORD")
MLX_FOLDER_ID    = os.getenv("MLX_FOLDER_ID")
MLX_WORKSPACE_ID = os.getenv("MLX_WORKSPACE_ID")

MLX_CLOUD_API = "https://api.multilogin.com"
TOKEN_REFRESH_INTERVAL = 15
MAX_RETRIES = 15
RETRY_DELAY = 1.0

if not all([SUPABASE_URL, SUPABASE_KEY, MLX_EMAIL, MLX_PASSWORD, MLX_FOLDER_ID]):
    raise ValueError("Missing credentials in .env - check SUPABASE and MLX variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def curl_post(url: str, payload: dict, token: str = None) -> dict | None:
    """POST via httpx with retry logic and SSL bypass."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(verify=False, timeout=30, trust_env=False) as client:
                response = client.post(url, json=payload, headers=headers)

            if response.status_code in (200, 201):
                return response.json()

            if response.status_code in (400, 401):
                print(f"⚠️ API returned {response.status_code}: {response.text[:200]}")
                return None

            print(f"⚠️ API returned {response.status_code}: {response.text[:200]}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            return None

        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            print(f"  Network hiccup (attempt {attempt}/{MAX_RETRIES}): {str(e)[:50]}... retrying")
            time.sleep(RETRY_DELAY)
            continue

        except Exception as e:
            err = str(e)
            retry_keywords = ["BAD_RECORD_MAC", "SSL", "disconnected", "RemoteProtocolError", "Connection reset"]
            if any(k in err for k in retry_keywords):
                print(f"  Network hiccup (attempt {attempt}/{MAX_RETRIES}): {err[:50]}... retrying")
                time.sleep(RETRY_DELAY)
                continue
            print(f"❌ Unexpected error: {e}")
            return None

    return None


def get_mlx_token() -> tuple[str | None, str | None]:
    """Authenticate and return (token, workspace_id)."""
    print("🔑 Authenticating with Multilogin X Cloud API...")
    hashed = hashlib.md5(MLX_PASSWORD.strip().encode()).hexdigest()
    data = curl_post(f"{MLX_CLOUD_API}/user/signin", {"email": MLX_EMAIL.strip(), "password": hashed})

    if not data or 'data' not in data:
        print(f"❌ Auth failed. Response: {data}")
        return None, None

    inner = data.get('data', {})
    token = inner.get('token')
    workspace_id = inner.get('workspace_id') or MLX_WORKSPACE_ID

    print(f"✅ Authenticated! Workspace: {workspace_id}")
    return token, workspace_id


def sanitize_proxy_field(value) -> str:
    """Strip HTML/whitespace from proxy fields."""
    if not value: return ""
    return str(value).strip().replace("<", "").replace(">", "").replace("&", "")


def create_mlx_profile(persona, token, workspace_id):
    """Creates a profile via the MLX Cloud API with full fingerprint settings."""
    network = persona.get('network', {})

    proxy_ip = network.get('proxy_ip')
    print(f"DEBUG: Preparing [{persona['profile_id']}] | Proxy IP: {proxy_ip}")

    if not proxy_ip:
        print(f"❌ ERROR: Profile {persona['profile_id']} has NO proxy data in Supabase. Skipping.")
        return None

    try:
        proxy_port = int(str(network.get('proxy_port', 0)).strip())
    except ValueError:
        print(f"⚠️ Invalid port for {persona['profile_id']}")
        return None

    # Get proxy credentials
    proxy_user = sanitize_proxy_field(network.get('proxy_user', ''))
    proxy_pass = sanitize_proxy_field(network.get('proxy_pass', ''))

    # ✅ FULL ENHANCED PAYLOAD with all fingerprint masking settings
    # Based on official Multilogin X support template
    payload = {
        "name": persona['profile_id'],
        "workspace_id": workspace_id,
        "folder_id": MLX_FOLDER_ID,
        "browser_type": "mimic",
        "os_type": "windows",
        "parameters": {
            # Proxy Configuration
            "proxy": {
                "host": proxy_ip,
                "port": proxy_port,
                "type": "http",
                "username": proxy_user,
                "password": proxy_pass
            },
            # Full Fingerprint Masking Flags
            "flags": {
                # Proxy & Location - Auto-match to proxy IP
                "proxy_masking": "custom",
                "timezone_masking": "mask",          # Auto-detect timezone from proxy
                "geolocation_masking": "mask",       # Match geolocation to proxy
                "geolocation_popup": "prompt",       # Ask before sharing location
                "localization_masking": "mask",      # Language matches proxy country
                
                # Browser Identity
                "navigator_masking": "mask",         # Randomize navigator properties
                "webrtc_masking": "mask",            # Prevent WebRTC IP leak
                
                # Hardware Fingerprinting
                "screen_masking": "natural",         # Natural screen resolution
                "graphics_masking": "mask",          # Mask WebGL vendor/renderer
                "graphics_noise": "natural",         # Natural canvas/WebGL noise
                "audio_masking": "mask",             # Mask AudioContext fingerprint
                "media_devices_masking": "natural",  # Natural media devices
                
                # Other Protections
                "fonts_masking": "mask",             # Mask installed fonts
                "ports_masking": "mask",             # Mask port scan protection
                
                # Behavior
"startup_behavior": "recover"            },
            # Storage Settings
            "storage": {
                "is_local": False,                   # Use cloud storage
                "save_service_worker": True          # Save service workers for sessions
            }
        }
    }

    data = curl_post(f"{MLX_CLOUD_API}/profile/create", payload, token=token)
    
    if not data:
        return None

    print(f"   API Response: {data.get('status', {}).get('message', 'OK')}")

    inner_data = data.get("data", {})
    ids = inner_data.get("ids", [])
    if ids:
        return ids[0]

    return inner_data.get("id") or inner_data.get("uuid")


async def main():
    # Load Google Accounts
    accounts = []
    try:
        with open("google_accounts.txt", 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 2:
                    accounts.append({
                        'email': parts[0],
                        'password': parts[1],
                        'recovery': parts[2] if len(parts) > 2 else ""
                    })
    except FileNotFoundError:
        print("❌ Error: google_accounts.txt not found.")
        return

    token, workspace_id = get_mlx_token()
    if not token or not workspace_id:
        return

    print("🚀 Fetching profiles from Supabase where mla_uuid is null...")
    response = supabase.table('profiles').select('*').is_('mla_uuid', 'null').execute()
    personas = response.data

    if not personas:
        print("✅ All profiles already have a Multilogin UUID!")
        return

    print(f"Found {len(personas)} profiles to build.\n")

    success_count = 0
    for i, persona in enumerate(personas):
        if i >= len(accounts):
            print("⚠️ Ran out of Google Accounts.")
            break

        # Periodic Re-auth
        if i > 0 and i % TOKEN_REFRESH_INTERVAL == 0:
            print("🔄 Refreshing Auth Token...")
            new_token, _ = get_mlx_token()
            if new_token:
                token = new_token

        g_acc = accounts[i]
        print(f"[{i+1}/{len(personas)}] Creating {persona['profile_id']}...")

        mla_uuid = create_mlx_profile(persona, token, workspace_id)

        if mla_uuid:
            supabase.table('profiles').update({
                'mla_uuid': mla_uuid,
                'google_email': g_acc['email'],
                'google_password': g_acc['password'],
                'google_recovery': g_acc['recovery'],
                'status': 'available'
            }).eq('id', persona['id']).execute()
            print(f"   ✅ Created: {mla_uuid}")
            success_count += 1
        else:
            print(f"   ❌ FAILED: {persona['profile_id']}")

        await asyncio.sleep(2)

    print(f"\n🏁 Finished! ✅ {success_count} profiles created with enhanced fingerprinting.")


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())