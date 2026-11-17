from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.auth import limiter
from backend.auth.security import token_hash
from backend.db.base import Base
from backend.db.session import get_db
from backend.main import app
from backend.models.auth import UserSession, utcnow


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        cls.engine = create_engine(f"sqlite:///{Path(cls.temp_dir.name) / 'auth-test.db'}", connect_args={"check_same_thread": False})
        cls.factory = sessionmaker(bind=cls.engine, expire_on_commit=False)

        def override_db():
            db = cls.factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        limiter.reset()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        limiter.reset()

    def csrf_headers(self):
        self.client.get("/auth/csrf")
        return {"X-CSRF-Token": self.client.cookies.get("finops_csrf"), "Origin": "http://localhost:5173"}

    def register(self, **overrides):
        data = {"full_name": "Test User", "username": "test.user", "email": "test@example.com", "password": "correct-horse-battery-4"}
        data.update(overrides)
        return self.client.post("/auth/register", json=data, headers=self.csrf_headers())

    def test_register_and_safe_user_response(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["email"], "test@example.com")
        self.assertNotIn("password_hash", response.text)
        self.assertNotIn("token_hash", response.text)
        self.assertNotIn('"session_token"', response.text)
        self.assertEqual(response.json()["csrf_token"], self.client.cookies.get("finops_csrf"))
        self.assertIn("finops_session", response.cookies)

    def test_csrf_bootstrap_supports_cross_origin_frontend(self):
        response = self.client.get("/auth/csrf", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 200)
        csrf_token = response.json()["csrf_token"]
        self.assertTrue(csrf_token)
        self.assertEqual(self.client.cookies.get("finops_csrf"), csrf_token)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")
        preflight = self.client.options(
            "/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        self.assertEqual(preflight.status_code, 200)

    def test_hosted_auth_cookies_use_secure_cross_site_attributes(self):
        from unittest.mock import patch

        with patch("backend.api.auth.is_hosted_deployment", return_value=True):
            response = self.client.get("/auth/csrf")
        cookie = response.headers.get("set-cookie", "")
        self.assertIn("finops_csrf=", cookie)
        self.assertIn("secure", cookie.lower())
        self.assertIn("samesite=none", cookie.lower())

    def test_duplicate_email_and_username(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register(username="another").status_code, 409)
        self.assertEqual(self.register(email="another@example.com").status_code, 409)

    def test_accounts_and_logout_all_are_session_scoped(self):
        first = self.register()
        other = TestClient(app)
        try:
            other.get("/auth/csrf")
            second = other.post(
                "/auth/register",
                json={"full_name": "Other User", "username": "other.user", "email": "other@example.com", "password": "another-correct-horse-4"},
                headers={"X-CSRF-Token": other.cookies.get("finops_csrf"), "Origin": "http://localhost:5173"},
            )
            self.assertEqual(second.status_code, 201)
            self.assertNotEqual(first.json()["user"]["id"], second.json()["user"]["id"])
            self.assertEqual(self.client.get("/auth/me").json()["email"], "test@example.com")
            self.assertEqual(other.get("/auth/profile").json()["email"], "other@example.com")
            csrf_token = second.json()["csrf_token"]
            self.assertEqual(other.post("/auth/logout-all", headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:5173"}).status_code, 204)
            self.assertEqual(other.get("/auth/me").status_code, 401)
            self.assertEqual(self.client.get("/auth/me").status_code, 200)
        finally:
            other.close()

    def test_login_and_invalid_credentials(self):
        self.register()
        self.client.cookies.clear()
        bad = self.client.post("/auth/login", json={"email": "test@example.com", "password": "incorrect"}, headers=self.csrf_headers())
        self.assertEqual(bad.status_code, 401)
        good = self.client.post("/auth/login", json={"email": "test@example.com", "password": "correct-horse-battery-4"}, headers=self.csrf_headers())
        self.assertEqual(good.status_code, 200)

    def test_missing_authentication_and_session_restoration(self):
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.register()
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "test.user")

    def test_expired_session(self):
        self.register()
        with self.factory() as db:
            row = db.query(UserSession).one()
            row.expires_at = utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_logout_revokes_session(self):
        registration = self.register()
        csrf_token = registration.json()["csrf_token"]
        response = self.client.post("/auth/logout", headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 204)
        set_cookies = response.headers.get_list("set-cookie")
        self.assertTrue(any("finops_session=" in cookie and "max-age=0" in cookie.lower() for cookie in set_cookies))
        self.assertTrue(any("finops_csrf=" in cookie and "max-age=0" in cookie.lower() for cookie in set_cookies))
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_logout_rejects_stale_csrf_token(self):
        registration = self.register()
        response = self.client.post(
            "/auth/logout",
            headers={"X-CSRF-Token": "stale-token", "Origin": "http://localhost:5173"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/auth/me").status_code, 200)
        self.assertEqual(registration.status_code, 201)

    def test_logout_after_session_restore_rehydrates_session_csrf_token(self):
        self.register()
        # Simulate a page refresh: the HttpOnly cookie survives but the React
        # module's in-memory CSRF token does not, so the client bootstraps again.
        csrf_response = self.client.get("/auth/csrf")
        csrf_token = csrf_response.json()["csrf_token"]
        response = self.client.post(
            "/auth/logout",
            headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:5173"},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_missing_csrf_cookie_rotates_bound_token_before_logout(self):
        self.register()
        self.client.cookies.delete("finops_csrf")
        csrf_response = self.client.get("/auth/csrf")
        csrf_token = csrf_response.json()["csrf_token"]
        self.assertEqual(self.client.cookies.get("finops_csrf"), csrf_token)
        response = self.client.post(
            "/auth/logout",
            headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:5173"},
        )
        self.assertEqual(response.status_code, 204)

    def test_session_csrf_hash_mismatch_is_rejected(self):
        registration = self.register()
        csrf_token = registration.json()["csrf_token"]
        with self.factory() as db:
            row = db.query(UserSession).one()
            row.csrf_token_hash = token_hash("different-token")
            db.commit()
        response = self.client.post(
            "/auth/logout",
            headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:5173"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/auth/me").status_code, 200)

    def test_password_change_requires_csrf_and_revokes_sessions(self):
        registration = self.register()
        payload = {"current_password": "correct-horse-battery-4", "new_password": "new-correct-horse-5"}
        rejected = self.client.post(
            "/auth/change-password",
            json=payload,
            headers={"X-CSRF-Token": "stale-token", "Origin": "http://localhost:5173"},
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(self.client.get("/auth/me").status_code, 200)

        changed = self.client.post(
            "/auth/change-password",
            json=payload,
            headers={"X-CSRF-Token": registration.json()["csrf_token"], "Origin": "http://localhost:5173"},
        )
        self.assertEqual(changed.status_code, 204)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.client.cookies.clear()
        old_password = self.client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "correct-horse-battery-4"},
            headers=self.csrf_headers(),
        )
        self.assertEqual(old_password.status_code, 401)
        new_password = self.client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "new-correct-horse-5"},
            headers=self.csrf_headers(),
        )
        self.assertEqual(new_password.status_code, 200)

    def test_csrf_required_for_auth_mutations(self):
        response = self.client.post("/auth/register", json={"full_name":"A","username":"abc","email":"a@example.com","password":"long-enough-password"}, headers={"Origin":"http://localhost:5173"})
        self.assertEqual(response.status_code, 403)

    def test_update_profile_and_uniqueness_checks(self):
        registration = self.register()
        csrf_token = registration.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf_token, "Origin": "http://localhost:5173"}

        updated = self.client.patch(
            "/auth/profile",
            json={"full_name": "Updated FinOps Lead", "username": "finops.lead", "email": "lead@example.com"},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["full_name"], "Updated FinOps Lead")
        self.assertEqual(updated.json()["username"], "finops.lead")
        self.assertEqual(updated.json()["email"], "lead@example.com")

        # Register a second user to verify email/username collision rejection
        other = TestClient(app)
        try:
            other.get("/auth/csrf")
            other_reg = other.post(
                "/auth/register",
                json={"full_name": "Other", "username": "taken.user", "email": "taken@example.com", "password": "correct-horse-battery-4"},
                headers={"X-CSRF-Token": other.cookies.get("finops_csrf"), "Origin": "http://localhost:5173"},
            )
            self.assertEqual(other_reg.status_code, 201)
        finally:
            other.close()

        dup_email = self.client.patch("/auth/profile", json={"email": "taken@example.com"}, headers=headers)
        self.assertEqual(dup_email.status_code, 409)
        dup_username = self.client.patch("/auth/profile", json={"username": "taken.user"}, headers=headers)
        self.assertEqual(dup_username.status_code, 409)

    def test_registration_rate_limit(self):
        headers = self.csrf_headers()
        payload = {"full_name": "Test User", "username": "limited.user", "email": "limited@example.com", "password": "correct-horse-battery-4"}
        statuses = []
        for _ in range(5):
            response = self.client.post("/auth/register", json=payload, headers=headers)
            statuses.append(response.status_code)
            if response.status_code == 201:
                headers["X-CSRF-Token"] = response.json()["csrf_token"]
        self.assertEqual(statuses[0], 201)
        self.assertTrue(all(code in {201, 409} for code in statuses))
        self.assertEqual(self.client.post("/auth/register", json=payload, headers=headers).status_code, 429)


if __name__ == "__main__":
    unittest.main()
