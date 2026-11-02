"""Official public-client ChatGPT OAuth with protected, per-registration storage."""

import base64
import hashlib
import json
import logging
import os
import secrets
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from laew.cloud_chat import CloudError

ISSUER = "https://auth.openai.com"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
logger = logging.getLogger(__name__)


class CredentialStore:
    """One encrypted keyring item; never fall back to plaintext or a chained backend."""
    def _backend(self):
        try:
            import keyring
            backend = keyring.get_keyring()
            if type(backend).__module__ not in {
                "keyring.backends.Windows", "keyring.backends.macOS",
                "keyring.backends.SecretService", "keyring.backends.kwallet",
            } or backend.priority <= 0:
                raise RuntimeError()
            return backend
        except Exception:
            raise CloudError("SECURE_STORE_UNAVAILABLE", "ChatGPT requires a supported OS credential store. Install laew[cloud] and unlock the system keyring.") from None

    def load(self):
        try:
            backend = self._backend()
            text = backend.get_password("LAEW.ChatGPT", "registrations")
            manifest = json.loads(text) if text else None
            if manifest and "version" in manifest:
                if not 1 <= manifest["chunks"] <= 1024: raise ValueError()
                text = "".join(backend.get_password("LAEW.ChatGPT", f'{manifest["version"]}:{i}')
                               for i in range(manifest["chunks"]))
            data = json.loads(text) if text else {"accounts": {}}
            if not isinstance(data.get("accounts"), dict): raise ValueError()
            return data
        except CloudError:
            raise
        except Exception:
            raise CloudError("SECURE_STORE_UNAVAILABLE", "Cannot read the protected ChatGPT credential record.") from None

    def save(self, data):
        backend = self._backend()
        version = secrets.token_hex(16)
        written = []
        try:
            old = backend.get_password("LAEW.ChatGPT", "registrations")
            encoded = json.dumps(data)
            if len(encoded) > 1024 * 1000: raise ValueError()
            chunks = [encoded[i:i + 1000] for i in range(0, len(encoded), 1000)]
            for i, chunk in enumerate(chunks):
                name = f"{version}:{i}"; backend.set_password("LAEW.ChatGPT", name, chunk); written.append(name)
            # Commit the manifest last so readers never see a partially rotated token set.
            backend.set_password("LAEW.ChatGPT", "registrations", json.dumps({"version": version, "chunks": len(chunks)}))
        except Exception:
            for name in written:
                try: backend.delete_password("LAEW.ChatGPT", name)
                except Exception:
                    logger.warning("Could not remove an uncommitted encrypted OAuth chunk.")
            raise CloudError("SECURE_STORE_UNAVAILABLE", "Cannot save the protected ChatGPT credential record.") from None
        if old:
            try:
                manifest = json.loads(old)
                for i in range(manifest.get("chunks", 0)):
                    backend.delete_password("LAEW.ChatGPT", f'{manifest["version"]}:{i}')
            except Exception:
                logger.warning("Could not remove stale encrypted OAuth chunks; the committed record remains authoritative.")


@contextmanager
def credential_lock():
    """Serialize rotating credentials across local LAEW processes; no secrets on disk."""
    path = Path(tempfile.gettempdir()) / "laew-chatgpt-oauth.lock"
    with path.open("a+b") as handle:
        deadline = time.monotonic() + 15
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise CloudError("AUTH_BUSY", "Another LAEW process is updating the ChatGPT session.") from None
                time.sleep(.05)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ChatGPTAuth:
    def __init__(self, store=None):
        self.store = store or CredentialStore()
        self._lock = threading.RLock()
        self._attempts = {}
        self._metadata_cache = None

    @staticmethod
    def _dependencies():
        try:
            import authlib  # noqa: F401
        except ImportError:
            raise CloudError("AUTH_UNAVAILABLE", "Install laew[cloud] to enable ChatGPT sign-in.") from None

    @staticmethod
    def _official(url):
        if not isinstance(url, str):
            raise CloudError("AUTH_CONFIGURATION", "OpenAI discovery returned an invalid endpoint.")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "auth.openai.com" or parsed.username or parsed.port not in (None, 443):
            raise CloudError("AUTH_CONFIGURATION", "OpenAI discovery returned an unexpected endpoint.")
        return url

    def _json_request(self, method, url, **kwargs):
        try:
            with requests.request(method, url, timeout=(10, 20), allow_redirects=False, **kwargs) as response:
                if response.status_code != 200:
                    raise CloudError("AUTH_FAILED", "ChatGPT authorization failed. Sign in again or check account eligibility.")
                if len(response.content) > 1024 * 1024: raise ValueError()
                data = response.json()
                if not isinstance(data, dict): raise ValueError()
                return data
        except CloudError:
            raise
        except (requests.RequestException, ValueError):
            raise CloudError("AUTH_UNAVAILABLE", "Cannot complete ChatGPT authorization with OpenAI.") from None

    def _metadata(self):
        if self._metadata_cache is None:
            data = self._json_request("GET", ISSUER + "/.well-known/openid-configuration")
            if data.get("issuer") != ISSUER:
                raise CloudError("AUTH_CONFIGURATION", "Unexpected OpenAI identity issuer.")
            for name in ("jwks_uri", "revocation_endpoint"):
                self._official(data.get(name, ""))
            self._metadata_cache = data
        return self._metadata_cache

    def status(self, session_id=None):
        try:
            self._dependencies()
            with self._lock, credential_lock():
                data = self.store.load()
            accounts = [{"id": key, "label": item.get("email", "ChatGPT") + " · " + key[:8],
                         "authenticated": bool(item.get("refresh_token") and item.get("access_token"))}
                        for key, item in data["accounts"].items()]
            result = {"auth_available": True, "accounts": accounts}
        except CloudError as exc:
            result = {"auth_available": False, "accounts": [], "auth_error": str(exc)}
        with self._lock:
            result["attempts"] = [{"id": key, "state": item["status"], "error": item.get("error"),
                                   "account_id": item.get("account_id")}
                                  for key, item in self._attempts.items() if session_id and item["owner"] == session_id]
        return result

    def start(self, session_id, account_id=None):
        self._dependencies()
        if not isinstance(session_id, str) or not 16 <= len(session_id) <= 128:
            raise CloudError("INVALID_REQUEST", "A browser session is required for sign-in.")
        with self._lock, credential_lock():
            data = self.store.load()
            if not data.get("host_id"):
                data["host_id"] = "urn:uuid:" + str(uuid.uuid4()); self.store.save(data)
            saved = data["accounts"].get(account_id) if account_id else None
            if account_id and saved is None:
                raise CloudError("AUTH_REQUIRED", "The selected ChatGPT registration does not exist.")
            self._attempts = {k: v for k, v in self._attempts.items() if v["expires"] > time.monotonic() - 300}
            if len(self._attempts) >= 16:
                raise CloudError("AUTH_BUSY", "Too many pending sign-in attempts.")
            state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
            attempt_id = secrets.token_urlsafe(24)
            attempt = {"owner": session_id, "state": state, "nonce": nonce, "verifier": verifier,
                       "status": "pending", "expires": time.monotonic() + 300,
                       "client_id": saved["client_id"] if saved else None,
                       "subject": saved["subject"] if saved else None, "done": threading.Event()}
            self._attempts[attempt_id] = attempt
        auth = self
        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path != "/auth/callback":
                    self.send_error(404); return
                params = parse_qs(parsed.query, keep_blank_values=True)
                try:
                    if any(len(v) != 1 for v in params.values()):
                        raise CloudError("AUTH_FAILED", "Invalid authorization callback.")
                    auth._complete(attempt_id, {k: v[0] for k, v in params.items()})
                    message = b"ChatGPT connected. You can close this tab and return to LAEW."
                    status = 200
                except CloudError:
                    message = b"Sign-in was not completed. Return to LAEW to see the status."
                    status = 400
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(message)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers(); self.wfile.write(message)
        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), Callback)
        except OSError:
            with self._lock: self._attempts.pop(attempt_id, None)
            raise CloudError("AUTH_UNAVAILABLE", "Cannot start the loopback sign-in callback.") from None
        attempt["server"] = server
        attempt["redirect_uri"] = f"http://127.0.0.1:{server.server_port}/auth/callback"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        def cleanup():
            if not attempt["done"].wait(300):
                with self._lock:
                    if attempt["status"] == "pending":
                        attempt.update(status="expired", error="Sign-in timed out.")
            server.shutdown(); server.server_close()
        threading.Thread(target=cleanup, daemon=True).start()
        params = {"client_id": attempt["client_id"] or "dynamic_agent_client",
                  "ext_agent_host_id": data["host_id"], "response_type": "code",
                  "redirect_uri": attempt["redirect_uri"], "scope": SCOPES, "resource": RESOURCE,
                  "state": state, "nonce": nonce, "code_challenge_method": "S256",
                  "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()}
        if not saved: params["agent_name_hint"] = "LAEW"
        return {"attempt_id": attempt_id, "authorization_url": AUTHORIZE + "?" + urlencode(params)}

    def _validate_identity(self, tokens, attempt, client_id):
        from authlib.jose import JsonWebToken
        from authlib.oidc.core import CodeIDToken
        metadata = self._metadata()
        jwks = self._json_request("GET", metadata["jwks_uri"])
        try:
            claims = JsonWebToken(["RS256"]).decode(tokens["id_token"], jwks, claims_cls=CodeIDToken,
                claims_options={"iss": {"essential": True, "value": ISSUER},
                                "aud": {"essential": True, "value": client_id}, "exp": {"essential": True},
                                "sub": {"essential": True}, "nonce": {"essential": True, "value": attempt["nonce"]}},
                claims_params={"nonce": attempt["nonce"], "client_id": client_id, "access_token": tokens["access_token"]})
            claims.validate(leeway=30)
            if not isinstance(claims.get("sub"), str) or not claims["sub"]: raise ValueError()
            if attempt.get("subject") and claims["sub"] != attempt["subject"]: raise ValueError()
            return claims
        except Exception:
            raise CloudError("INVALID_IDENTITY", "ChatGPT identity validation failed. Start sign-in again.") from None

    @staticmethod
    def _token_fields(tokens):
        try:
            scopes = tokens["scope"].split()
            if not {"resource.invoke", "chatgpt.tokens.use.direct"}.issubset(scopes):
                raise CloudError("PLAN_PERMISSION_REQUIRED", "ChatGPT plan use was not authorized for LAEW.")
            if not all(isinstance(tokens.get(name), str) and tokens[name] for name in ('access_token', 'refresh_token')): raise ValueError()
            if tokens.get("token_type", "").lower() != "bearer": raise ValueError()
            seconds = int(tokens['expires_in'])
            if not 1 <= seconds <= 864000: raise ValueError()
            expiry = time.time() + seconds
            return {"access_token": tokens["access_token"], "refresh_token": tokens["refresh_token"],
                    "id_token": tokens.get("id_token"), "scopes": scopes, "expires_at": expiry}
        except (KeyError, ValueError, TypeError, AttributeError):
            raise CloudError("AUTH_FAILED", "ChatGPT returned an invalid credential record.") from None

    def _complete(self, attempt_id, params):
        with self._lock:
            attempt = self._attempts.get(attempt_id)
            if not attempt or attempt["status"] != "pending" or attempt["expires"] < time.monotonic():
                raise CloudError("AUTH_FAILED", "Authorization attempt expired or was already used.")
            if not secrets.compare_digest(params.get("state", ""), attempt["state"]):
                raise CloudError("AUTH_FAILED", "Invalid authorization state.")
            attempt["status"] = "validating"
        try:
            if params.get("error"):
                raise CloudError("AUTH_DENIED", "ChatGPT sign-in was denied or cancelled.")
            client_id = params.get("client_id") or attempt["client_id"]
            if not client_id or client_id == "dynamic_agent_client" or (attempt["client_id"] and client_id != attempt["client_id"]):
                raise CloudError("AUTH_FAILED", "ChatGPT returned an unexpected registration ID.")
            if not params.get("code"): raise CloudError("AUTH_FAILED", "Missing authorization code.")
            tokens = self._json_request("POST", TOKEN, data={"grant_type": "authorization_code", "client_id": client_id,
                        "code": params["code"], "code_verifier": attempt["verifier"], "redirect_uri": attempt["redirect_uri"], "resource": RESOURCE})
            claims = self._validate_identity(tokens, attempt, client_id)
            record = {"client_id": client_id, "subject": claims["sub"], "email": str(claims.get("email", "ChatGPT")),
                      **self._token_fields(tokens)}
            account_id = hashlib.sha256((client_id + "\0" + claims["sub"]).encode()).hexdigest()[:24]
            with self._lock, credential_lock():
                if attempt["status"] != "validating":
                    raise CloudError("AUTH_DENIED", "Sign-in was cancelled.")
                data = self.store.load(); data["accounts"][account_id] = record; self.store.save(data)
                attempt.update(status="connected", account_id=account_id)
        except CloudError as exc:
            with self._lock: attempt.update(status="failed", error=str(exc))
            raise
        finally:
            attempt.pop("verifier", None); attempt.pop("nonce", None)
            attempt["done"].set()

    def credential(self, account_id):
        self._dependencies()
        with self._lock, credential_lock():
            data = self.store.load()
            record = data["accounts"].get(account_id)
            if not record or not record.get("refresh_token") or not record.get("access_token"):
                raise CloudError("AUTH_REQUIRED", "Sign in with the selected ChatGPT account.")
            if record["expires_at"] < time.time() + 60:
                try:
                    tokens = self._json_request("POST", TOKEN, data={"grant_type": "refresh_token", "client_id": record["client_id"],
                                "refresh_token": record["refresh_token"], "resource": RESOURCE})
                    tokens.setdefault("scope", " ".join(record["scopes"]))
                    tokens.setdefault("refresh_token", record["refresh_token"])
                    fields = self._token_fields(tokens)
                    if not fields["id_token"]: fields["id_token"] = record.get("id_token")
                    record.update(fields); self.store.save(data)
                except CloudError:
                    raise CloudError("AUTH_REQUIRED", "ChatGPT session could not be renewed. Sign in again.") from None
            return record["access_token"]

    def logout(self, account_id):
        confirmed = True
        with self._lock, credential_lock():
            data = self.store.load()
            record = data["accounts"].get(account_id)
            if not record: raise CloudError("AUTH_REQUIRED", "Unknown ChatGPT registration.")
            for attempt in self._attempts.values():
                if attempt.get("client_id") == record["client_id"] and attempt["status"] in {"pending", "validating"}:
                    attempt.update(status="cancelled", error="Signed out."); attempt["done"].set()
            try:
                endpoint = self._metadata()["revocation_endpoint"]
                if record.get("refresh_token"):
                    # The token_type_hint value is a standardized protocol label.
                    revocation = {"token": record["refresh_token"], "token_type_hint": "refresh_token", "client_id": record["client_id"]}  # nosec B105
                    with requests.post(endpoint, data=revocation,
                                       timeout=(10, 20), allow_redirects=False) as response:
                        confirmed = response.status_code == 200
            except (CloudError, requests.RequestException):
                confirmed = False
            for name in ("access_token", "refresh_token", "id_token", "expires_at", "scopes"):
                record.pop(name, None)
            self.store.save(data)
        return {"signed_out": True, "revocation_confirmed": confirmed,
                "message": "Signed out." if confirmed else "Signed out locally. Remote revocation was not confirmed; disconnect LAEW in ChatGPT Settings."}

    def cancel_attempt(self, session_id, attempt_id):
        with self._lock:
            attempt = self._attempts.get(attempt_id)
            if not attempt or attempt["owner"] != session_id: raise CloudError("AUTH_FAILED", "Unknown sign-in attempt.")
            attempt.update(status="cancelled", error="Sign-in cancelled."); attempt["done"].set()
        return {"cancelled": True}

    def close(self):
        with self._lock:
            for attempt in self._attempts.values():
                if attempt["status"] in {"pending", "validating"}: attempt["status"] = "cancelled"
                attempt["done"].set()
