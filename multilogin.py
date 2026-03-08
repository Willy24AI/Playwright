"multilogin.py"

import requests
import sys
import hashlib
import time
import urllib3
from playwright.sync_api import sync_playwright

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------------------
# YOUR CREDENTIALS
# ----------------------------
ML_EMAIL = "jennifernanyombi1@gmail.com"
ML_PASSWORD = "#Kampala1road2!"
FOLDER_ID = "f06c8892-e0fb-4798-9b84-c6653ca03e27"       # TODO: Add your Folder ID here (see instructions below)
PROFILE_ID = "ba334a7f-5c92-4097-8ce0-7269cb263981"
# ----------------------------
# HOW TO GET YOUR FOLDER ID:
# In the Multilogin desktop app, click the 3 dots (...) next to your profile
# -> Edit -> look at the URL or profile details for the folder UUID
# ----------------------------

MLX_BASE = "https://api.multilogin.com"
LOCAL_AGENT = "https://launcher.mlx.yt:45001"


# --------------------------------------------------
# STEP 1: Get Cloud Token
# --------------------------------------------------
def get_token():
    url = f"{MLX_BASE}/user/signin"

    hashed_password = hashlib.md5(ML_PASSWORD.encode()).hexdigest()

    payload = {
        "email": ML_EMAIL,
        "password": hashed_password
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    print("\n--- Step 1: Signing in ---")
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        print("❌ Login Failed")
        print(response.text)
        sys.exit(1)

    token = response.json()["data"]["token"]
    print("✅ Logged in successfully")
    return token


# --------------------------------------------------
# STEP 2: Start Profile
# --------------------------------------------------
def start_profile(token):
    url = f"{LOCAL_AGENT}/api/v2/profile/f/{FOLDER_ID}/p/{PROFILE_ID}/start?automation_type=playwright&headless_mode=false"

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    print(f"\n--- Step 2: Starting Profile {PROFILE_ID} ---")

    # Stop the profile first in case it is already running
    stop_url = f"{LOCAL_AGENT}/api/v2/profile/f/{FOLDER_ID}/p/{PROFILE_ID}/stop"
    requests.get(stop_url, headers=headers, verify=False)
    print("⏳ Waiting for profile to stop...")
    time.sleep(5)  # Wait 5 seconds for profile to fully stop

    response = requests.get(url, headers=headers, verify=False)

    if response.status_code != 200:
        print("❌ Profile Start Failed:")
        print(response.text)
        return None

    data = response.json()
    profile_data = data.get("data", {})

    # Build WebSocket URL from port returned by Multilogin X
    port = profile_data.get("port")
    if port:
        ws_endpoint = f"http://127.0.0.1:{port}"
    else:
        ws_endpoint = data.get("wsEndpoint") or data.get("value")

    if not ws_endpoint:
        print("❌ No WebSocket endpoint returned.")
        print(data)
        return None

    print("✅ Profile started successfully")
    print(f"✅ Connecting to: {ws_endpoint}")
    return ws_endpoint


# --------------------------------------------------
# STEP 3: Run Playwright
# --------------------------------------------------
def run_browser(ws_endpoint):
    print("\n--- Step 3: Connecting Playwright ---")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(ws_endpoint)

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()

        page.goto("https://youtu.be/lVbw9yA40Hc?si=WDJCUeZg8jcnRzp0")
        print(f"✅ Page Title: {page.title()}")

        page.wait_for_timeout(5000)

        browser.close()
        print("✅ Browser closed successfully")


# --------------------------------------------------
# STEP 4: Stop Profile
# --------------------------------------------------
def stop_profile(token):
    url = f"{LOCAL_AGENT}/api/v2/profile/f/{FOLDER_ID}/p/{PROFILE_ID}/stop"

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    print("\n--- Step 4: Stopping Profile ---")
    requests.get(url, headers=headers, verify=False)
    print("✅ Profile stopped")


# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    if not FOLDER_ID:
        print("❌ FOLDER_ID is empty! Please add your Folder ID to the script.")
        print("   In the Multilogin app: click ... next to your profile -> Edit -> copy the Folder UUID")
        sys.exit(1)

    token = get_token()

    ws_url = start_profile(token)

    if not ws_url:
        print("\n❌ Script stopped because the profile could not be started.")
        sys.exit(1)

    run_browser(ws_url)

    time.sleep(2)

    stop_profile(token)

    print("\n🎉 Automation Completed Successfully")