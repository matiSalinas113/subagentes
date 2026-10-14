"""Black-box and storage-security tests for the local login service."""

from __future__ import annotations

import contextlib
import http.client
import io
import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import gc
from pathlib import Path
from unittest.mock import patch


APP_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIRECTORY))
import app  # noqa: E402


ORIGIN = "http://login.test.invalid"
USER = "test-user"
PASSWORD = "Test-password-2026!"
ADMIN = "test-admin"
ADMIN_PASSWORD = "Admin-password-2026!"


class LoginServiceTests(unittest.TestCase):
    """Exercise the HTTP contract using a disposable SQLite database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.database = Path(cls.temporary_directory.name) / "login.sqlite3"
        cls.static_dir = Path(cls.temporary_directory.name) / "static"
        cls.static_dir.mkdir()
        app.initialize_database(cls.database)
        app.create_user(cls.database, USER, PASSWORD)
        app.create_user(cls.database, ADMIN, ADMIN_PASSWORD, is_admin=True)
        config = app.Config(cls.database, cls.static_dir, ORIGIN)
        cls.server = app.LoginServer(("127.0.0.1", 0), config)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        # The implementation opens SQLite connections per request; collect their
        # now-unreachable instances before Windows removes the temporary DB.
        gc.collect()
        cls.temporary_directory.cleanup()

    def setUp(self) -> None:
        with app.connect(self.database) as connection:
            connection.execute("DELETE FROM sessions")
        with self.server._login_attempts_lock:
            self.server._login_attempts.clear()

    def request(self, method: str, path: str, body: object | None = None, *, origin: str | None = ORIGIN,
                cookie: str | None = None, content_type: str = "application/json") -> tuple[int, dict[str, str], bytes]:
        headers: dict[str, str] = {}
        if origin is not None:
            headers["Origin"] = origin
        if cookie:
            headers["Cookie"] = cookie
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(len(data))
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def login(self, username: str = USER, password: str = PASSWORD) -> str:
        status, headers, response = self.request("POST", "/api/auth/login", {"username": username, "password": password})
        self.assertEqual((status, response), (204, b""))
        cookie = headers.get("Set-Cookie")
        self.assertIsNotNone(cookie)
        return cookie.split(";", 1)[0]

    def test_bootstrap_creates_an_admin_without_exposing_plaintext(self) -> None:
        database = Path(self.temporary_directory.name) / "bootstrap.sqlite3"
        with patch("builtins.input", return_value="bootstrap-admin"), patch.object(
            app, "getpass", side_effect=["Bootstrap-password-2026!", "Bootstrap-password-2026!"]
        ):
            app.bootstrap(database)
        with app.connect(database) as connection:
            row = connection.execute("SELECT username, is_admin, password_salt, password_hash FROM users").fetchone()
        self.assertEqual(row[:2], ("bootstrap-admin", 1))
        self.assertNotEqual(row[2], b"Bootstrap-password-2026!")
        self.assertNotEqual(row[3], b"Bootstrap-password-2026!")

    def test_login_success_sets_hardened_session_cookie_and_me_authenticates(self) -> None:
        status, login_headers, response = self.request(
            "POST", "/api/auth/login", {"username": USER, "password": PASSWORD}
        )
        self.assertEqual((status, response), (204, b""))
        set_cookie = login_headers["Set-Cookie"]
        self.assertIn("Path=/; HttpOnly; SameSite=Lax; Max-Age=28800", set_cookie)
        cookie = set_cookie.split(";", 1)[0]
        self.assertRegex(cookie, r"^session=[A-Za-z0-9_-]{32,}$")
        status, headers, body = self.request("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"username": USER, "is_admin": False})
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_unknown_user_and_wrong_password_have_identical_generic_response(self) -> None:
        wrong = self.request("POST", "/api/auth/login", {"username": USER, "password": "wrong-password-2026!"})
        missing = self.request("POST", "/api/auth/login", {"username": "no-such-user", "password": PASSWORD})
        self.assertEqual(wrong[0], 401)
        self.assertEqual(missing[0], 401)
        self.assertEqual(wrong[2], missing[2])
        self.assertEqual(json.loads(wrong[2]), {"error": "Credenciales inválidas."})

    def test_empty_and_malformed_login_entries_are_rejected(self) -> None:
        for payload in ({"username": "", "password": ""}, {"username": 4, "password": []}):
            status, _, body = self.request("POST", "/api/auth/login", payload)
            self.assertEqual((status, json.loads(body)), (401, {"error": "Credenciales inválidas."}))
        status, _, body = self.request("POST", "/api/auth/login", b"not-json")
        self.assertEqual((status, json.loads(body)), (400, {"error": "Solicitud inválida."}))

    def test_passwords_are_salted_hashed_and_verified_with_compare_digest(self) -> None:
        with app.connect(self.database) as connection:
            first = connection.execute("SELECT password_salt, password_hash FROM users WHERE username = ?", (USER,)).fetchone()
            second = connection.execute("SELECT password_salt, password_hash FROM users WHERE username = ?", (ADMIN,)).fetchone()
        self.assertEqual((len(first[0]), len(first[1])), (app.SALT_BYTES, 32))
        self.assertNotEqual(first[0], second[0])
        self.assertNotIn(PASSWORD.encode(), first)
        with patch.object(app.hmac, "compare_digest", wraps=app.hmac.compare_digest) as compare:
            self.assertIsNotNone(app.authenticate(self.database, USER, PASSWORD))
        compare.assert_called_once()

    def test_me_rejects_missing_expired_and_logged_out_sessions(self) -> None:
        import hashlib

        status, _, body = self.request("GET", "/api/auth/me")
        self.assertEqual((status, json.loads(body)), (401, {"error": "No autenticado."}))
        cookie = self.login()
        session_id = cookie.partition("=")[2]
        session_id_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        with app.connect(self.database) as connection:
            stored_session_id = connection.execute("SELECT id FROM sessions WHERE id = ?", (session_id_hash,)).fetchone()[0]
            self.assertNotEqual(stored_session_id, session_id)
            connection.execute("UPDATE sessions SET expires_at = ? WHERE id = ?", (int(time.time()) - 1, session_id_hash))
        self.assertEqual(self.request("GET", "/api/auth/me", cookie=cookie)[0], 401)
        cookie = self.login()
        status, headers, body = self.request("POST", "/api/auth/logout", {}, cookie=cookie)
        self.assertEqual((status, body), (204, b""))
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertEqual(self.request("GET", "/api/auth/me", cookie=cookie)[0], 401)

    def test_admin_creation_requires_admin_and_creates_no_plaintext_password(self) -> None:
        payload = {"username": "new-user", "password": "New-user-password-2026!", "is_admin": False}
        self.assertEqual(self.request("POST", "/api/admin/users", payload)[0], 401)
        self.assertEqual(self.request("POST", "/api/admin/users", payload, cookie=self.login())[0], 401)
        status, _, body = self.request("POST", "/api/admin/users", payload, cookie=self.login(ADMIN, ADMIN_PASSWORD))
        self.assertEqual((status, json.loads(body)), (201, {"created": True}))
        with app.connect(self.database) as connection:
            stored = connection.execute("SELECT password_salt, password_hash FROM users WHERE username = 'new-user'").fetchone()
        self.assertNotIn(payload["password"].encode(), stored)

    def test_state_changing_requests_require_the_exact_origin(self) -> None:
        payload = {"username": USER, "password": PASSWORD}
        for origin in (None, "https://attacker.invalid", ORIGIN + "/"):
            status, _, body = self.request("POST", "/api/auth/login", payload, origin=origin)
            self.assertEqual((status, json.loads(body)), (403, {"error": "Solicitud no permitida."}))

    def test_admin_flag_rejects_false_like_values_and_structures(self) -> None:
        admin_cookie = self.login(ADMIN, ADMIN_PASSWORD)
        for value in ("false", 0, 1, [], {}, {"value": False}):
            with self.subTest(value=repr(value)):
                payload = {
                    "username": "candidate-" + str(len(repr(value))),
                    "password": "Candidate-password-2026!",
                    "is_admin": value,
                }
                status, _, body = self.request("POST", "/api/admin/users", payload, cookie=admin_cookie)
                self.assertEqual((status, json.loads(body)), (400, {"error": "No se pudo crear el usuario."}))
        for value in ("false", 0, 1, [], {}):
            with self.subTest(create_user_value=repr(value)):
                with self.assertRaises(ValueError):
                    app.create_user(self.database, "direct-" + str(len(repr(value))), "Direct-password-2026!", value)

    def test_https_origin_forces_secure_cookies_and_insecure_cli_fails(self) -> None:
        https_origin = "https://login.test.invalid"
        config = app.Config(self.database, self.static_dir, https_origin, secure_cookies=False)
        self.assertTrue(config.secure_cookies)

        https_server = app.LoginServer(("127.0.0.1", 0), config)
        thread = threading.Thread(target=https_server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", https_server.server_address[1], timeout=10)
            try:
                payload = json.dumps({"username": USER, "password": PASSWORD}).encode("utf-8")
                connection.request("POST", "/api/auth/login", payload, {
                    "Origin": https_origin, "Content-Type": "application/json", "Content-Length": str(len(payload)),
                })
                response = connection.getresponse()
                headers = dict(response.getheaders())
                self.assertEqual(response.status, 204)
                response.read()
                self.assertIn("; Secure", headers["Set-Cookie"])
            finally:
                connection.close()
        finally:
            https_server.shutdown()
            https_server.server_close()
            thread.join()

        stderr = io.StringIO()
        with patch.object(sys, "argv", ["app.py", "serve", "--origin", https_origin]), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as failure:
                app.main()
        self.assertEqual(failure.exception.code, 2)
        self.assertIn("--secure-cookies es obligatorio", stderr.getvalue())

    def test_oversized_body_is_rejected_and_connection_is_closed(self) -> None:
        oversized = b"x" * (app.MAX_BODY_BYTES + 1)
        status, headers, body = self.request("POST", "/api/auth/login", oversized)
        self.assertEqual((status, json.loads(body)), (400, {"error": "Solicitud inválida."}))
        self.assertEqual(headers.get("Connection"), "close")

    def test_early_post_rejection_drains_body_and_preserves_http_protocol(self) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            payload = json.dumps({"username": USER, "password": PASSWORD}).encode("utf-8")
            connection.request("POST", "/api/auth/login", payload, {
                "Origin": "https://attacker.invalid", "Content-Type": "application/json", "Content-Length": str(len(payload)),
            })
            rejected = connection.getresponse()
            self.assertEqual(rejected.status, 403)
            rejected.read()

            connection.request("GET", "/api/auth/me")
            follow_up = connection.getresponse()
            self.assertEqual(follow_up.status, 401)
            self.assertEqual(json.loads(follow_up.read()), {"error": "No autenticado."})
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
