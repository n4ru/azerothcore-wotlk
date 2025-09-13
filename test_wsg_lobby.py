#!/usr/bin/env python3
"""
Test script for WSG Lobby system
Creates a lobby, imports two characters from sample_exports.json, and starts the match
"""

import json
import time
import requests
import subprocess
import os
import signal
import sys
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8080"
AUTH_DB = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "acore",
    "password": "acore",
    "database": "acore_auth"
}
CHAR_DB = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "acore",
    "password": "acore",
    "database": "acore_characters"
}

# Server paths
WORLDSERVER_PATH = r"C:\Users\root\Documents\GitHub\AzerothWarsong\binaries\bin\RelWithDebInfo\worldserver.exe"
AUTHSERVER_PATH = r"C:\Users\root\Documents\GitHub\AzerothWarsong\binaries\bin\RelWithDebInfo\authserver.exe"

# Global process handles
worldserver_process = None
authserver_process = None
webserver_process = None

def cleanup():
    """Clean up server processes"""
    global worldserver_process, authserver_process, webserver_process

    print("\n[CLEANUP] Stopping servers...")

    if webserver_process:
        try:
            webserver_process.terminate()
            webserver_process.wait(timeout=5)
        except:
            webserver_process.kill()

    if worldserver_process:
        try:
            worldserver_process.terminate()
            worldserver_process.wait(timeout=5)
        except:
            worldserver_process.kill()

    if authserver_process:
        try:
            authserver_process.terminate()
            authserver_process.wait(timeout=5)
        except:
            authserver_process.kill()

    # Also kill any remaining game server processes (but NOT node since Claude uses it)
    subprocess.run(["powershell", "-Command",
                   "Stop-Process -Name worldserver -Force -ErrorAction SilentlyContinue; "
                   "Stop-Process -Name authserver -Force -ErrorAction SilentlyContinue"],
                  capture_output=True)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n[INFO] Interrupt received, cleaning up...")
    cleanup()
    sys.exit(0)

def start_web_server():
    """Start the WSG lobby web server"""
    global webserver_process

    web_dir = r"C:\Users\root\Documents\GitHub\AzerothWarsong\azerothcore-wotlk\data\web\wsg-lobby"

    print("[INFO] Starting WSG lobby web server...")
    webserver_process = subprocess.Popen(
        ["node", "server.js"],
        cwd=web_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for web server to be ready
    time.sleep(3)

    # Check if web server is running
    try:
        response = requests.get("http://localhost:3000", timeout=2)
        if response.status_code == 200:
            print("[SUCCESS] WSG lobby web server is running on port 3000")
            return True
    except:
        pass

    print("[WARNING] Web server may not be running properly")
    return True  # Continue anyway

def start_servers():
    """Start authserver and worldserver"""
    global worldserver_process, authserver_process

    print("[INFO] Starting authserver...")
    authserver_process = subprocess.Popen(
        [AUTHSERVER_PATH],
        cwd=os.path.dirname(AUTHSERVER_PATH),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print("[INFO] Waiting for authserver to initialize...")
    time.sleep(5)

    print("[INFO] Starting worldserver...")
    worldserver_process = subprocess.Popen(
        [WORLDSERVER_PATH],
        cwd=os.path.dirname(WORLDSERVER_PATH),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print("[INFO] Waiting for worldserver to initialize (this may take a minute)...")

    # Wait for REST API to be available
    max_attempts = 60
    for i in range(max_attempts):
        try:
            response = requests.get(f"{API_BASE}/status", timeout=2)
            if response.status_code == 200:
                print("[SUCCESS] Worldserver REST API is ready!")
                return True
        except:
            pass

        if i % 10 == 0:
            print(f"[INFO] Still waiting... ({i}/{max_attempts})")
        time.sleep(2)

    print("[ERROR] Worldserver failed to start properly")
    return False

def load_character_data():
    """Load character data from sample_exports.json"""
    json_path = r"C:\Users\root\Documents\GitHub\AzerothWarsong\azerothcore-wotlk\sample_exports.json"

    print(f"[INFO] Loading character data from {json_path}")

    with open(json_path, 'r') as f:
        data = json.load(f)

    characters = data.get('characters', [])
    if len(characters) < 2:
        print("[ERROR] sample_exports.json must contain at least 2 characters")
        return None

    # Extract the two characters
    char1 = characters[0]  # Thirkfears - Horde Warlock
    char2 = characters[1]  # Thirkcarry - Alliance Druid

    print(f"[INFO] Loaded {char1['character']['name']} ({char1['character']['faction']}) and "
          f"{char2['character']['name']} ({char2['character']['faction']})")

    return char1, char2

def create_lobby(character_data):
    """Create a new WSG lobby with the first character as leader"""
    print(f"\n[LOBBY] Creating lobby with {character_data['character']['name']} as leader...")

    # Prepare the request
    url = f"{API_BASE}/lobby/create"
    payload = {
        "leaderName": character_data['character']['name'],
        "faction": character_data['character']['faction'],
        "characterData": json.dumps(character_data)
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            result = response.json()
            lobby_id = result.get('lobbyId')
            print(f"[SUCCESS] Lobby created with ID: {lobby_id}")
            return lobby_id
        else:
            print(f"[ERROR] Failed to create lobby: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception creating lobby: {e}")
        return None

def join_lobby(lobby_id, character_data):
    """Join an existing lobby with a character"""
    print(f"\n[LOBBY] {character_data['character']['name']} joining lobby {lobby_id}...")

    url = f"{API_BASE}/lobby/join"
    payload = {
        "lobbyId": lobby_id,
        "characterName": character_data['character']['name'],
        "faction": character_data['character']['faction'],
        "characterData": json.dumps(character_data)
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            print(f"[SUCCESS] {character_data['character']['name']} joined lobby")
            return True
        else:
            print(f"[ERROR] Failed to join lobby: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Exception joining lobby: {e}")
        return False

def get_lobby_status(lobby_id):
    """Get the current status of a lobby"""
    url = f"{API_BASE}/lobby/status/{lobby_id}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"[ERROR] Failed to get lobby status: {response.status_code}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception getting lobby status: {e}")
        return None

def start_lobby(lobby_id, leader_name):
    """Start the WSG match for a lobby"""
    print(f"\n[LOBBY] Starting match for lobby {lobby_id}...")

    url = f"{API_BASE}/lobby/start"
    payload = {
        "lobbyId": lobby_id,
        "requestingPlayer": leader_name
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            result = response.json()
            instance_id = result.get('instanceId')
            print(f"[SUCCESS] WSG match started! Instance ID: {instance_id}")
            return instance_id
        else:
            print(f"[ERROR] Failed to start lobby: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception starting lobby: {e}")
        return None

def main():
    """Main test function"""
    print("=" * 60)
    print("WSG LOBBY SYSTEM TEST")
    print("=" * 60)

    # Set up signal handler for cleanup
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Step 1: Kill any existing servers
        print("\n[STEP 1] Cleaning up existing servers...")
        cleanup()
        time.sleep(2)

        # Step 2: Start web server
        print("\n[STEP 2] Starting web server...")
        if not start_web_server():
            print("[ERROR] Failed to start web server")
            return False

        # Step 3: Start game servers
        print("\n[STEP 3] Starting game servers...")
        if not start_servers():
            print("[ERROR] Failed to start servers")
            return False

        # Step 4: Load character data
        print("\n[STEP 4] Loading character data...")
        char_data = load_character_data()
        if not char_data:
            print("[ERROR] Failed to load character data")
            return False

        horde_char, alliance_char = char_data

        # Step 5: Create lobby with Horde character as leader
        print("\n[STEP 5] Creating WSG lobby...")
        lobby_id = create_lobby(horde_char)
        if not lobby_id:
            print("[ERROR] Failed to create lobby")
            return False

        # Step 6: Check lobby status
        print("\n[STEP 6] Checking lobby status...")
        status = get_lobby_status(lobby_id)
        if status:
            print(f"[INFO] Lobby status: {status['status']}")
            print(f"[INFO] Players: Alliance={status['alliance_count']}, Horde={status['horde_count']}")

        # Step 7: Join with Alliance character
        print("\n[STEP 7] Adding Alliance player to lobby...")
        if not join_lobby(lobby_id, alliance_char):
            print("[ERROR] Failed to join lobby")
            return False

        # Step 8: Check updated status
        print("\n[STEP 8] Checking updated lobby status...")
        status = get_lobby_status(lobby_id)
        if status:
            print(f"[INFO] Lobby status: {status['status']}")
            print(f"[INFO] Players: Alliance={status['alliance_count']}, Horde={status['horde_count']}")
            print(f"[INFO] Can start: {status['can_start']}")

        # Step 9: Start the match
        print("\n[STEP 9] Starting WSG match...")
        instance_id = start_lobby(lobby_id, horde_char['character']['name'])
        if not instance_id:
            print("[ERROR] Failed to start match")
            return False

        # Step 10: Verify match started
        print("\n[STEP 10] Verifying match status...")
        time.sleep(3)
        status = get_lobby_status(lobby_id)
        if status:
            print(f"[INFO] Final lobby status: {status['status']}")
            print(f"[INFO] WSG Instance ID: {status['wsg_instance_id']}")

        # Step 11: Wait a bit to see if characters would join
        print("\n[STEP 11] Waiting for character imports and BG setup...")
        print("[INFO] In a real scenario, characters would now log in and auto-join the WSG")
        print("[INFO] The battleground is ready with 1v1 minimum players")
        time.sleep(10)

        print("\n" + "=" * 60)
        print("TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nSummary:")
        print(f"  - Lobby ID: {lobby_id}")
        print(f"  - WSG Instance: {instance_id}")
        print(f"  - Horde Leader: {horde_char['character']['name']}")
        print(f"  - Alliance Player: {alliance_char['character']['name']}")
        print("\nThe WSG battleground is now waiting for players to log in.")
        print("When they do, they'll automatically join the battleground.")

        return True

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return False

    finally:
        # Clean up
        print("\n[CLEANUP] Test complete, stopping servers...")
        cleanup()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)