"""
Email Agent - One Click Startup Script
Run this with: python start.py
It will:
1. Start the backend (uvicorn)
2. Start ngrok
3. Auto-detect the ngrok URL
4. Update App.jsx with the new URL
5. Push to GitHub
6. Open the dashboard
"""

import subprocess
import time
import requests
import re
import os
import sys
import webbrowser

# ── CONFIG ──────────────────────────────────────────────────────
PROJECT_DIR   = r"C:\Users\ASUS\Projects\email-agent"
BACKEND_DIR   = os.path.join(PROJECT_DIR, "frontend", "src", "App.jsx")
APP_JSX_PATH  = os.path.join(PROJECT_DIR, "frontend", "src", "App.jsx")
VERCEL_URL    = "https://email-agent-xi-drab.vercel.app"
BACKEND_PORT  = 8000
# ────────────────────────────────────────────────────────────────

def print_step(n, text):
    print(f"\n[{n}] {text}...")

def start_backend():
    print_step(1, "Starting backend server")
    backend_path = os.path.join(PROJECT_DIR, "backend")
    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "server:app", "--reload", "--port", str(BACKEND_PORT)],
        cwd=backend_path,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(4)
    print("   ✓ Backend running on port", BACKEND_PORT)
    return proc

def start_ngrok():
    print_step(2, "Starting ngrok tunnel")
    proc = subprocess.Popen(
        ["ngrok", "http", str(BACKEND_PORT)],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(4)
    print("   ✓ ngrok started")
    return proc

def get_ngrok_url():
    print_step(3, "Detecting ngrok URL")
    for attempt in range(10):
        try:
            res = requests.get("http://localhost:4040/api/tunnels", timeout=3)
            tunnels = res.json().get("tunnels", [])
            for t in tunnels:
                url = t.get("public_url", "")
                if url.startswith("https://"):
                    print(f"   ✓ Got URL: {url}")
                    return url
        except Exception:
            pass
        print(f"   Waiting... ({attempt+1}/10)")
        time.sleep(2)
    print("   ✗ Could not detect ngrok URL")
    sys.exit(1)

def update_app_jsx(ngrok_url):
    print_step(4, f"Updating App.jsx with new URL")
    with open(APP_JSX_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace any existing API URL line
    new_content = re.sub(
        r'const API\s*=\s*["\']https?://[^"\']+["\'];',
        f'const API = "{ngrok_url}";',
        content
    )

    if new_content == content:
        print("   ✓ URL unchanged (same as last time)")
        return False

    with open(APP_JSX_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("   ✓ App.jsx updated")
    return True

def push_to_github():
    print_step(5, "Pushing to GitHub (Vercel will auto-redeploy)")
    os.chdir(PROJECT_DIR)
    subprocess.run(["git", "add", "frontend/src/App.jsx"], check=True)
    subprocess.run(["git", "commit", "-m", "Auto-update ngrok URL"], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    print("   ✓ Pushed! Vercel is rebuilding (~60 seconds)")

def open_dashboard():
    print_step(6, "Opening dashboard")
    time.sleep(60)  # Wait for Vercel to redeploy
    webbrowser.open(VERCEL_URL)
    print("   ✓ Dashboard opened!")

def main():
    print("=" * 45)
    print("   AI Email Agent — Starting Up")
    print("=" * 45)

    start_backend()
    start_ngrok()
    ngrok_url = get_ngrok_url()
    changed = update_app_jsx(ngrok_url)

    if changed:
        push_to_github()
        print("\n   Waiting 60 seconds for Vercel to redeploy...")
        open_dashboard()
    else:
        print_step(6, "Opening dashboard (no redeploy needed)")
        webbrowser.open(VERCEL_URL)
        print("   ✓ Done!")

    print("\n" + "=" * 45)
    print("   Everything is running!")
    print(f"   Dashboard: {VERCEL_URL}")
    print("   Close this window when done.")
    print("=" * 45)
    input("\n   Press Enter to exit...\n")

if __name__ == "__main__":
    main()
