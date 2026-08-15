#!/usr/bin/env python3
"""One-shot Spotify OAuth flow — run this once to get a refresh token."""

import os
import sys
import urllib.parse
import urllib.request
import base64
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = "https://involvement-fed-him-must.trycloudflare.com/callback"
PORT          = 8888

SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
])

auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "error" in params:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization denied.")
            return

        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>OK! Ban co the dong tab nay lai.</h2>")

    def log_message(self, *args):
        pass  # suppress request logs


def get_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    }
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)


def exchange_code(code):
    credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env first")
        sys.exit(1)

    print(f"\nBuoc 1 — Mo URL nay trong trinh duyet:")
    print(f"\n  {get_auth_url()}\n")
    print("Buoc 2 — Dang nhap Spotify, cho phep quyen truy cap.")
    print("Buoc 3 — Sau khi redirect, script nay tu dong lay token.\n")

    server = HTTPServer(("0.0.0.0", PORT), CallbackHandler)
    server.timeout = 120
    while auth_code is None:
        server.handle_request()

    print("Nhan duoc auth code, dang doi token...")
    tokens = exchange_code(auth_code)

    refresh_token = tokens.get('refresh_token', '')
    print("\n=== TOKEN ===")
    print(f"Access token  : {tokens.get('access_token', '')}")
    print(f"Refresh token : {refresh_token}")
    print(f"Expires in    : {tokens.get('expires_in')} giay")

    # Save refresh token to file so it's not lost
    with open("spotify_refresh_token.txt", "w") as f:
        f.write(refresh_token)
    print(f"\nDa luu refresh token vao spotify_refresh_token.txt")
