"""Minimal same-origin login service using only the Python standard library."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import socket
import sqlite3
import threading
import time
from dataclasses import dataclass
from getpass import getpass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16
SESSION_BYTES = 32
SESSION_LIFETIME_SECONDS = 8 * 60 * 60
MAX_BODY_BYTES = 16 * 1024
SOCKET_TIMEOUT_SECONDS = 10
LOGIN_FAILURE_THRESHOLD = 5
LOGIN_BACKOFF_MAX_SECONDS = 60
LOGIN_ATTEMPT_CACHE_MAX_ENTRIES = 4_096
LOGIN_MAX_CONCURRENT = 4
USERNAME_MAX_LENGTH = 64
PASSWORD_MAX_LENGTH = 1024
SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK(length(username) BETWEEN 3 AND 64),
    password_salt BLOB NOT NULL CHECK(length(password_salt) = 16),
    password_hash BLOB NOT NULL CHECK(length(password_hash) = 32),
    password_iterations INTEGER NOT NULL CHECK(password_iterations >= 600000),
    is_admin INTEGER NOT NULL DEFAULT 0 CHECK(is_admin IN (0, 1)),
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    -- This is the SHA-256 digest of the bearer token, never the token itself.
    id TEXT PRIMARY KEY CHECK(length(id) = 64),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expires_at ON sessions(expires_at);
"""


@dataclass(frozen=True)
class Config:
    database: Path
    static_dir: Path
    origin: str
    secure_cookies: bool = False

    def __post_init__(self) -> None:
        if urlsplit(self.origin).scheme.lower() == "https":
            object.__setattr__(self, "secure_cookies", True)


class ClosingConnection(sqlite3.Connection):
    """Connection that releases its SQLite handle when its context exits."""

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database, factory=ClosingConnection)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database: Path) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    with connect(database) as connection:
        connection.executescript(SCHEMA)
        # Sessions are bearer credentials.  Earlier local databases stored their
        # values directly, so invalidate them while replacing that schema.
        session_schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'sessions'"
        ).fetchone()[0]
        if "length(id) = 64" not in session_schema:
            connection.executescript(
                """
                DROP TABLE sessions;
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY CHECK(length(id) = 64),
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX sessions_expires_at ON sessions(expires_at);
                """
            )


def valid_username(username: Any) -> bool:
    return (
        isinstance(username, str)
        and 3 <= len(username) <= USERNAME_MAX_LENGTH
        and all(character.isascii() and (character.isalnum() or character in "_.-") for character in username)
    )


def valid_password(password: Any) -> bool:
    return isinstance(password, str) and 12 <= len(password) <= PASSWORD_MAX_LENGTH


def password_digest(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def create_user(database: Path, username: str, password: str, is_admin: bool = False) -> None:
    if not valid_username(username):
        raise ValueError("El nombre de usuario debe tener 3-64 caracteres ASCII: letras, números, _, . o -.")
    if not valid_password(password):
        raise ValueError("La contraseña debe tener entre 12 y 1024 caracteres.")
    if type(is_admin) is not bool:
        raise ValueError("Invalid administrator flag.")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = password_digest(password, salt)
    try:
        with connect(database) as connection:
            connection.execute(
                "INSERT INTO users(username, password_salt, password_hash, password_iterations, is_admin, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (username, salt, digest, PBKDF2_ITERATIONS, int(is_admin), int(time.time())),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("No se pudo crear el usuario.") from error


def authenticate(database: Path, username: str, password: str) -> tuple[int, str, bool] | None:
    # Invalid input deliberately follows the same unauthenticated result.
    if not isinstance(username, str) or not isinstance(password, str):
        return None
    with connect(database) as connection:
        row = connection.execute(
            "SELECT id, username, password_salt, password_hash, password_iterations, is_admin "
            "FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        # Preserve a comparable expensive operation for unknown usernames.
        password_digest(password, b"\0" * SALT_BYTES)
        return None
    calculated = password_digest(password, row[2], row[4])
    if not hmac.compare_digest(calculated, row[3]):
        return None
    return row[0], row[1], bool(row[5])


def create_session(database: Path, user_id: int) -> str:
    now = int(time.time())
    session_id = secrets.token_urlsafe(SESSION_BYTES)
    with connect(database) as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO sessions(id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (session_token_digest(session_id), user_id, now + SESSION_LIFETIME_SECONDS, now),
        )
    return session_id


def session_token_digest(session_id: str) -> str:
    """Return the stable database lookup value for a client bearer token."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def session_user(database: Path, session_id: str | None) -> tuple[int, str, bool] | None:
    if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
        return None
    now = int(time.time())
    with connect(database) as connection:
        row = connection.execute(
            "SELECT users.id, users.username, users.is_admin FROM sessions "
            "JOIN users ON users.id = sessions.user_id WHERE sessions.id = ? AND sessions.expires_at > ?",
            (session_token_digest(session_id), now),
        ).fetchone()
    return (row[0], row[1], bool(row[2])) if row else None


def delete_session(database: Path, session_id: str | None) -> None:
    if isinstance(session_id, str) and session_id:
        with connect(database) as connection:
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_token_digest(session_id),))


class LoginHandler(BaseHTTPRequestHandler):
    server: "LoginServer"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        # Do not log request targets either: callers may accidentally put secrets there.
        return

    def do_POST(self) -> None:
        if not self._same_origin():
            self._reject_post(HTTPStatus.FORBIDDEN, {"error": "Solicitud no permitida."})
            return
        if self.path == "/api/auth/login":
            self._login()
        elif self.path == "/api/auth/logout":
            if not self._drain_body():
                self._json(HTTPStatus.BAD_REQUEST, {"error": "Solicitud inválida."})
                return
            delete_session(self.server.config.database, self._session_id())
            self.send_response(HTTPStatus.NO_CONTENT)
            self._clear_cookie()
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/api/admin/users":
            self._create_admin_user()
        else:
            self._reject_post(HTTPStatus.NOT_FOUND, {"error": "No encontrado."})

    def do_GET(self) -> None:
        if self.path == "/api/auth/me":
            user = session_user(self.server.config.database, self._session_id())
            if user is None:
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "No autenticado."})
            else:
                self._json(HTTPStatus.OK, {"username": user[1], "is_admin": user[2]})
            return
        self._static()

    def _login(self) -> None:
        body = self._body_json()
        if body is None:
            return
        attempt_keys = self.server.login_attempt_keys(self.client_address[0], body.get("username"))
        if self.server.login_backoff_active(attempt_keys):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Credenciales inválidas."})
            return
        # PBKDF2 is intentionally expensive.  Bound parallel derivations so a
        # burst cannot consume all worker threads and CPU.
        if not self.server.login_slots.acquire(blocking=False):
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Servicio no disponible."})
            return
        try:
            authenticated = authenticate(self.server.config.database, body.get("username"), body.get("password"))
        finally:
            self.server.login_slots.release()
        if authenticated is None:
            self.server.record_login_failure(attempt_keys)
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "Credenciales inválidas."})
            return
        self.server.clear_login_failures(attempt_keys[0])
        self.send_response(HTTPStatus.NO_CONTENT)
        self._session_cookie(create_session(self.server.config.database, authenticated[0]))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _create_admin_user(self) -> None:
        user = session_user(self.server.config.database, self._session_id())
        if user is None or not user[2]:
            self._reject_post(HTTPStatus.UNAUTHORIZED, {"error": "No autenticado."})
            return
        body = self._body_json()
        if body is None:
            return
        try:
            is_admin = body.get("is_admin", False)
            if type(is_admin) is not bool:
                raise ValueError("Invalid administrator flag.")
            create_user(self.server.config.database, body.get("username"), body.get("password"), is_admin)
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "No se pudo crear el usuario."})
            return
        self._json(HTTPStatus.CREATED, {"created": True})

    def _same_origin(self) -> bool:
        return self.headers.get("Origin") == self.server.config.origin

    def _body_json(self) -> dict[str, Any] | None:
        if self.headers.get_content_type() != "application/json":
            self._reject_post(HTTPStatus.BAD_REQUEST, {"error": "Solicitud inválida."})
            return None
        try:
            length = self._content_length()
            if length is None or length > MAX_BODY_BYTES:
                raise ValueError
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
            return payload
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            # A malformed or incomplete declared body cannot safely be reused.
            self.close_connection = True
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Solicitud inválida."})
            return None

    def _content_length(self) -> int | None:
        value = self.headers.get("Content-Length")
        if self.headers.get("Transfer-Encoding"):
            return None
        if value is None:
            return 0
        if not value.isascii() or not value.isdecimal():
            return None
        return int(value)

    def _drain_body(self) -> bool:
        """Consume a bounded declared body; otherwise close the connection."""
        length = self._content_length()
        if length is None or length > MAX_BODY_BYTES:
            self.close_connection = True
            return False
        try:
            self.rfile.read(length)
            return True
        except OSError:
            self.close_connection = True
            return False

    def _reject_post(self, status: HTTPStatus, value: dict[str, Any]) -> None:
        self._drain_body()
        self._json(status, value)

    def _session_id(self) -> str | None:
        try:
            cookie = SimpleCookie(self.headers.get("Cookie"))
            return cookie.get("session").value if cookie.get("session") else None
        except Exception:
            return None

    def _session_cookie(self, value: str) -> None:
        attributes = f"session={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_LIFETIME_SECONDS}"
        if self.server.config.secure_cookies:
            attributes += "; Secure"
        self.send_header("Set-Cookie", attributes)

    def _clear_cookie(self) -> None:
        attributes = "session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
        if self.server.config.secure_cookies:
            attributes += "; Secure"
        self.send_header("Set-Cookie", attributes)

    def _json(self, status: HTTPStatus, value: dict[str, Any]) -> None:
        encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)

    def _static(self) -> None:
        requested = unquote(urlsplit(self.path).path)
        relative = "index.html" if requested == "/" else requested.lstrip("/")
        candidate = (self.server.config.static_dir / relative).resolve()
        try:
            candidate.relative_to(self.server.config.static_dir.resolve())
        except ValueError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "No encontrado."})
            return
        if not candidate.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "No encontrado."})
            return
        content = candidate.read_bytes()
        content_type = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}.get(candidate.suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


class LoginServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], config: Config):
        self.config = config
        self._login_attempts: dict[tuple[str, str, str], tuple[int, float, float]] = {}
        self._login_attempts_lock = threading.Lock()
        self.login_slots = threading.BoundedSemaphore(LOGIN_MAX_CONCURRENT)
        super().__init__(address, LoginHandler)

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        request, client_address = super().get_request()
        request.settimeout(SOCKET_TIMEOUT_SECONDS)
        return request, client_address

    @staticmethod
    def login_attempt_keys(ip_address: str, username: Any) -> tuple[tuple[str, str, str], tuple[str, str, str]]:
        # Only retain a bounded identifier, never a password or request payload.
        identifier = username if valid_username(username) else "<invalid>"
        # A distinct aggregate IP key prevents an attacker from bypassing the
        # per-account backoff by cycling through usernames.
        return ("account", ip_address, identifier), ("ip", ip_address, "")

    def login_backoff_active(self, keys: tuple[tuple[str, str, str], tuple[str, str, str]]) -> bool:
        now = time.monotonic()
        with self._login_attempts_lock:
            return any(
                (attempt := self._login_attempts.get(key)) is not None and attempt[1] > now
                for key in keys
            )

    def record_login_failure(self, keys: tuple[tuple[str, str, str], tuple[str, str, str]]) -> None:
        now = time.monotonic()
        with self._login_attempts_lock:
            for key in keys:
                self._record_login_failure(key, now)

    def _record_login_failure(self, key: tuple[str, str, str], now: float) -> None:
        if len(self._login_attempts) >= LOGIN_ATTEMPT_CACHE_MAX_ENTRIES and key not in self._login_attempts:
            expired = [entry for entry, value in self._login_attempts.items() if value[2] <= now]
            for entry in expired:
                del self._login_attempts[entry]
            if len(self._login_attempts) >= LOGIN_ATTEMPT_CACHE_MAX_ENTRIES:
                oldest = min(self._login_attempts, key=lambda entry: self._login_attempts[entry][2])
                del self._login_attempts[oldest]
        failures = self._login_attempts.get(key, (0, 0.0, now))[0] + 1
        delay = 0.0
        if failures >= LOGIN_FAILURE_THRESHOLD:
            delay = min(LOGIN_BACKOFF_MAX_SECONDS, 2.0 ** (failures - LOGIN_FAILURE_THRESHOLD))
        self._login_attempts[key] = (failures, now + delay, now + LOGIN_BACKOFF_MAX_SECONDS)

    def clear_login_failures(self, key: tuple[str, str, str]) -> None:
        with self._login_attempts_lock:
            self._login_attempts.pop(key, None)


def bootstrap(database: Path) -> None:
    initialize_database(database)
    username = input("Nombre del administrador inicial: ").strip()
    password = getpass("Contraseña (12+ caracteres): ")
    confirmation = getpass("Confirma la contraseña: ")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")
    create_user(database, username, password, is_admin=True)
    print("Administrador creado.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "bootstrap"))
    parser.add_argument("--database", type=Path, default=Path("data/login.sqlite3"))
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--origin", default="http://127.0.0.1:8000", help="Exact expected same-origin value.")
    parser.add_argument("--secure-cookies", action="store_true", help="Required when serving over HTTPS in production.")
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap(args.database)
        return
    origin = urlsplit(args.origin)
    if origin.scheme.lower() not in {"http", "https"} or not origin.netloc:
        parser.error("--origin debe ser un origen HTTP(S) absoluto.")
    if origin.scheme.lower() == "https" and not args.secure_cookies:
        parser.error("--secure-cookies es obligatorio para un origen HTTPS.")
    initialize_database(args.database)
    config = Config(args.database, args.static_dir, args.origin.rstrip("/"), args.secure_cookies)
    server = LoginServer((args.host, args.port), config)
    print(f"Serving on {args.origin} (secure cookies: {args.secure_cookies})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
