from __future__ import annotations

import argparse
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from fyers_apiv3 import fyersModel

from app.core.security import TokenStore
from app.core.settings import TraderConfig, get_settings, load_traders


@dataclass
class CallbackResult:
    auth_code: str | None = None
    error: str | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    result: CallbackResult
    expected_path: str
    done_event: threading.Event

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != self.expected_path:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        params = parse_qs(parsed.query)
        auth_code = (params.get("auth_code") or params.get("code") or [None])[0]
        error = (params.get("error") or [None])[0]

        self.result.auth_code = auth_code
        self.result.error = error

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h3>FYERS login received. You can close this tab and return to terminal.</h3></body></html>"
        )
        self.done_event.set()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def _extract_auth_code(user_input: str) -> str | None:
    text = user_input.strip()
    if not text:
        return None

    if "auth_code=" in text or "code=" in text:
        parsed = urlparse(text)
        params = parse_qs(parsed.query)
        return (params.get("auth_code") or params.get("code") or [None])[0]

    return text


def _pick_trader(traders: list[TraderConfig], alias: str | None, trader_id: int | None) -> TraderConfig:
    if trader_id is not None:
        for t in traders:
            if t.id == trader_id:
                return t
        raise ValueError(f"Trader id {trader_id} not found")

    if alias is not None:
        for t in traders:
            if t.token_alias == alias:
                return t
        raise ValueError(f"Trader alias '{alias}' not found")

    if len(traders) == 1:
        return traders[0]

    joined = ", ".join(f"{t.id}:{t.token_alias}" for t in traders)
    raise ValueError(f"Multiple traders configured. Use --alias or --trader-id. Available: {joined}")


def _start_callback_server(redirect_uri: str) -> tuple[ThreadingHTTPServer, CallbackResult, threading.Event]:
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
        raise ValueError("Auto callback requires redirect_uri with http://localhost:<port>/path or http://127.0.0.1:<port>/path")

    result = CallbackResult()
    done_event = threading.Event()
    expected_path = parsed.path or "/"

    class _Handler(CallbackHandler):
        pass

    _Handler.result = result
    _Handler.expected_path = expected_path
    _Handler.done_event = done_event

    server = ThreadingHTTPServer((parsed.hostname, parsed.port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, result, done_event


def run_auth_flow(
    trader: TraderConfig, open_browser: bool, timeout_sec: int, manual_only: bool
) -> tuple[str, str | None]:
    if not trader.secret_key or not trader.redirect_uri:
        raise ValueError(
            f"Trader '{trader.name}' is missing secret_key/redirect_uri in config/traders.json"
        )

    session = fyersModel.SessionModel(
        client_id=trader.client_id,
        secret_key=trader.secret_key,
        redirect_uri=trader.redirect_uri,
        response_type="code",
        grant_type="authorization_code",
        state=secrets.token_urlsafe(12),
    )

    login_url = session.generate_authcode()
    print(f"\nLogin URL for {trader.name}:\n{login_url}\n")

    callback_server = None
    callback_result = None
    callback_done = None

    if not manual_only:
        try:
            callback_server, callback_result, callback_done = _start_callback_server(trader.redirect_uri)
            print("Waiting for callback on redirect URI...")
        except Exception as exc:
            print(f"Auto callback disabled: {exc}")

    if open_browser:
        webbrowser.open(login_url, new=1)

    auth_code = None

    if callback_done is not None:
        completed = callback_done.wait(timeout=timeout_sec)
        if completed and callback_result is not None:
            if callback_result.error:
                raise RuntimeError(f"FYERS returned error during auth: {callback_result.error}")
            auth_code = callback_result.auth_code
        else:
            print("Callback timeout reached. Falling back to manual auth code input.")

    if callback_server is not None:
        callback_server.shutdown()
        callback_server.server_close()

    if not auth_code:
        raw = input("Paste redirected URL or auth_code: ").strip()
        auth_code = _extract_auth_code(raw)

    if not auth_code:
        raise RuntimeError("Could not parse auth_code")

    session.set_token(auth_code)
    response = session.generate_token()
    if "access_token" not in response:
        raise RuntimeError(f"Token generation failed: {response}")

    access_token = str(response["access_token"])
    refresh_token = str(response["refresh_token"]) if response.get("refresh_token") else None
    return access_token, refresh_token


def main() -> None:
    parser = argparse.ArgumentParser(description="Automate FYERS auth-code login and store encrypted access token")
    parser.add_argument("--alias", help="token alias from config/traders.json (e.g., trader1)")
    parser.add_argument("--trader-id", type=int, help="trader id from config/traders.json")
    parser.add_argument("--no-browser", action="store_true", help="do not auto-open browser")
    parser.add_argument("--timeout", type=int, default=180, help="callback wait timeout in seconds")
    parser.add_argument("--manual", action="store_true", help="skip callback capture and always paste auth_code manually")
    args = parser.parse_args()

    settings = get_settings()
    traders = load_traders(settings.traders_file)
    trader = _pick_trader(traders, alias=args.alias, trader_id=args.trader_id)

    access_token, refresh_token = run_auth_flow(
        trader=trader,
        open_browser=not args.no_browser,
        timeout_sec=max(30, args.timeout),
        manual_only=args.manual,
    )

    store = TokenStore(settings.secret_key_path, settings.token_store_path)
    store.set_token(trader.token_alias, access_token)
    if refresh_token:
        store.set_token(f"{trader.token_alias}:refresh", refresh_token)
    print(f"Stored access token for alias '{trader.token_alias}'")


if __name__ == "__main__":
    main()
