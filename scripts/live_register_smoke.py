from __future__ import annotations

import secrets
import sys
import uuid

import httpx


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18080"
    email = f"user-test-{uuid.uuid4().hex}@example.com"
    password = f"T!{secrets.token_urlsafe(18)}a9"

    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "display_name": "User Test"},
        )
        registered.raise_for_status()
        payload = registered.json()
        csrf_token = payload["csrf_token"]

        current = client.get("/api/v1/auth/me")
        current.raise_for_status()
        if current.json()["user"]["email"] != email:
            raise RuntimeError("Registered session did not resolve to the new test account")

        removed = client.request(
            "DELETE",
            "/api/v1/me/account",
            headers={"X-CSRF-Token": csrf_token},
            json={"confirmation": "DELETE", "password": password},
        )
        removed.raise_for_status()

    print("Registration, session cookie, CSRF, current-user lookup, and test-account cleanup passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
