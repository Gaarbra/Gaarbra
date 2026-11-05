"""One-time helper: get a Spotify refresh token for update_minutes.py.

Run locally:
    python scripts/get_refresh_token.py

It asks for your client ID and secret (or reads SPOTIFY_CLIENT_ID and
SPOTIFY_CLIENT_SECRET from the environment), opens the Spotify login in
your browser, catches the redirect on http://127.0.0.1:8888/callback and
prints a refresh token. Uses only the Python standard library.
"""

import base64
import getpass
import http.server
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-read-recently-played"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


def build_auth_url(client_id, state):
    query = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
    })
    return f"{AUTH_URL}?{query}"


def wait_for_callback(expected_state):
    """Serve one request on 127.0.0.1:8888 and return the auth code."""
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            params = urllib.parse.parse_qs(parsed.query)
            if params.get("state", [None])[0] != expected_state:
                result["error"] = "state mismatch (possible CSRF), try again"
            elif "error" in params:
                result["error"] = params["error"][0]
            elif "code" in params:
                result["code"] = params["code"][0]
            else:
                result["error"] = "no code in callback"
            ok = "code" in result
            body = ("Done. You can close this tab." if ok
                    else f"Error: {result['error']}").encode()
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    with http.server.HTTPServer(("127.0.0.1", 8888), Handler) as server:
        while not result:
            server.handle_request()
    if "error" in result:
        sys.exit(f"Login failed: {result['error']}")
    return result["code"]


def exchange_code(client_id, client_secret, code):
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID") or input("Client ID: ").strip()
    client_secret = (os.environ.get("SPOTIFY_CLIENT_SECRET")
                     or getpass.getpass("Client secret: ").strip())
    state = secrets.token_urlsafe(16)
    url = build_auth_url(client_id, state)
    print("Opening the Spotify login. If no browser opens, visit:\n" + url)
    webbrowser.open(url)
    code = wait_for_callback(state)
    tokens = exchange_code(client_id, client_secret, code)
    print("\nRefresh token (save it as the SPOTIFY_REFRESH_TOKEN repo secret):\n")
    print(tokens["refresh_token"])


if __name__ == "__main__":
    main()
