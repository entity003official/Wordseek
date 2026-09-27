import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

TEST_DIR = tempfile.TemporaryDirectory()
os.environ["BEYOND_WORDS_DATA_DIR"] = TEST_DIR.name
os.environ["BEYOND_WORDS_DATABASE_URL"] = f"sqlite:///{TEST_DIR.name}/test.db"
os.environ["BEYOND_WORDS_AUTO_CREATE_SCHEMA"] = "true"

from backend.app.ai.deepseek import DeepSeekResult
from backend.app.speech.tts import TtsResult


class ApiFlowTest(unittest.TestCase):
    @staticmethod
    def qwen_result() -> dict:
        return {
            "engine": "qwen",
            "model": "qwen-audio-3.1-asr-flash-filetrans",
            "language": "en",
            "turns": [
                {"id": "turn_001", "speaker_id": "SPEAKER_00", "start_ms": 0, "end_ms": 2100, "text": "What do you think about joining the study group?"},
                {"id": "turn_002", "speaker_id": "SPEAKER_01", "start_ms": 2200, "end_ms": 4300, "text": "I like the idea because we can practise together."},
            ],
            "words": [],
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
            "diarization": {"status": "complete", "speaker_count": 2, "model": "qwen-audio-3.1-asr-flash-filetrans"},
            "audio_duration_ms": 5000,
            "provider_usage": {"input_tokens": 12, "output_tokens": 4, "estimated_cost_cny": None},
            "provider_retry_count": 0,
            "resumed_existing_task": False,
        }

    def run_qwen_analysis(self, session_id: str, *, legacy_backend: str | None = None):
        payload = {
            "language_hints": ["en"],
            "speaker_policy": {"mode": "auto", "min_count": 1, "max_count": 8},
            "cloud_audio_consent": {"accepted": True, "version": "test"},
        }
        if legacy_backend:
            payload["speech_backend"] = legacy_backend
        with patch("backend.app.services.speech.prepare_cloud_audio", side_effect=lambda path: path), patch(
            "backend.app.services.speech.QwenSpeechProvider"
        ) as provider_class:
            provider = provider_class.return_value
            provider.available = True
            provider.name = "qwen"
            provider.model = "qwen-audio-3.1-asr-flash-filetrans"
            provider.analyze.return_value = self.qwen_result()
            return self.request("POST", f"/api/v1/sessions/{session_id}/analyze", json=payload)

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TEST_DIR
        module = importlib.import_module("backend.app.main")
        cls.module = module
        cls.client_context = TestClient(module.app)
        cls.client = cls.client_context.__enter__()
        registered = cls.client.post("/api/v1/auth/register", json={"email": "owner@example.com", "password": "strong-test-password", "display_name": "测试用户"})
        assert registered.status_code == 201, registered.text

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)
        cls.module.engine.dispose()
        cls.temp_dir.cleanup()

    def request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            headers["X-CSRF-Token"] = self.client.cookies.get("bw_csrf")
        return self.client.request(method, path, headers=headers, **kwargs)

    def test_admin_console_permissions_privacy_and_retry(self) -> None:
        from backend.app.db import SessionLocal
        from backend.app.models import AnalysisJob, AuditLog, ConversationSession, User

        denied = self.client.get("/api/v1/admin/overview")
        self.assertEqual(denied.status_code, 403)
        with TestClient(self.module.app) as anonymous:
            self.assertEqual(anonymous.get("/api/v1/admin/overview").status_code, 401)

        with SessionLocal() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            owner.role = "admin"
            owner.preference.ai_enabled = True
            conversation = ConversationSession(owner_id=owner.id, title="Admin privacy", scenario="Test")
            db.add(conversation)
            db.flush()
            failed = AnalysisJob(
                owner_id=owner.id,
                session_id=conversation.id,
                kind="ai_review",
                status="failed",
                payload_json={"force": False, "private_prompt": "must-not-leak"},
                result_json={"retryable": True, "private_output": "must-not-leak"},
                error_code="AI_PROVIDER_OVERLOADED",
                error_message="internal provider detail must-not-leak",
                provider="deepseek",
                provider_model="deepseek-flash",
            )
            db.add(failed)
            db.commit()
            failed_id = failed.id

        overview = self.client.get("/api/v1/admin/overview?range=7d")
        self.assertEqual(overview.status_code, 200)
        self.assertIn("providers", overview.json())
        users = self.client.get("/api/v1/admin/users?page=1&page_size=10&role=admin")
        self.assertEqual(users.status_code, 200)
        self.assertGreaterEqual(users.json()["total"], 1)
        jobs = self.client.get("/api/v1/admin/jobs?status=failed")
        self.assertEqual(jobs.status_code, 200)
        serialized = next(item for item in jobs.json()["items"] if item["id"] == failed_id)
        self.assertTrue(serialized["retryable"])
        dated_jobs = self.client.get("/api/v1/admin/jobs?date_from=2099-01-01&date_to=2099-01-02")
        self.assertEqual(dated_jobs.status_code, 200)
        self.assertEqual(dated_jobs.json()["total"], 0)
        self.assertEqual(self.client.get("/api/v1/admin/jobs?date_from=2099-01-02&date_to=2099-01-01").status_code, 422)
        for private_field in ("payload_json", "result_json", "analysis_json", "audio_object_key", "private_prompt", "private_output", "internal provider detail"):
            self.assertNotIn(private_field, jobs.text)

        with patch("backend.app.api.admin.process_ai_job_now", return_value={"status": "complete"}) as processor:
            retried = self.request("POST", f"/api/v1/admin/jobs/{failed_id}/retry")
        self.assertEqual(retried.status_code, 202)
        self.assertNotEqual(retried.json()["job_id"], failed_id)
        processor.assert_called_once()
        with SessionLocal() as db:
            original = db.get(AnalysisJob, failed_id)
            replacement = db.get(AnalysisJob, retried.json()["job_id"])
            self.assertEqual(original.status, "failed")
            self.assertEqual(replacement.retry_of_job_id, failed_id)
            self.assertTrue(db.scalar(select(AuditLog).where(AuditLog.action == "admin.job_retried")))
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            owner.role = "user"
            owner.preference.ai_enabled = False
            db.commit()

    def test_validation_errors_use_the_public_error_contract(self) -> None:
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "short", "display_name": ""},
        )
        self.assertEqual(response.status_code, 422)
        payload = response.json()["error"]
        self.assertEqual(payload["code"], "VALIDATION_FAILED")
        self.assertFalse(payload["retryable"])
        self.assertIn("email", payload["fields"])
        self.assertNotIn("not-an-email", response.text)

    def test_ai_review_requires_consent_and_persists_validated_result(self) -> None:
        created = self.request("POST", "/api/v1/sessions", json={"title": "AI review", "scenario": "日常交流"})
        session_id = created.json()["id"]
        self.request("POST", f"/api/v1/sessions/{session_id}/audio?duration_ms=5000", files={"audio": ("sample.webm", b"audio", "audio/webm")})
        self.run_qwen_analysis(session_id)
        self.request("PATCH", f"/api/v1/sessions/{session_id}/speakers", json={"user_speaker_id": "SPEAKER_01"})
        denied = self.request("POST", f"/api/v1/sessions/{session_id}/ai-review")
        self.assertEqual(denied.status_code, 409)
        self.request("PUT", "/api/v1/me/preferences", json={"ai_enabled": True, "consent_version": "test"})
        payload = {
            "summary": {"title": "学习小组", "summary": "双方讨论学习小组。", "topics": ["study group"], "evidence_turn_ids": ["turn_001", "turn_002"], "limitations": []},
            "scene": {"scene_type": "casual_chat", "communication_goal": "讨论活动", "context_notes": [], "evidence_turn_ids": ["turn_001"], "confidence": 0.8},
            "events": [{"type": "TOPIC_DEVELOPMENT", "observation": "回应较短。", "context": "对方随后继续提问。", "suggestion": "补充理由。", "example": "I like it because we can practise.", "evidence_turn_ids": ["turn_001", "turn_002"], "confidence": 0.7}],
            "learning_points": [],
        }
        with patch("backend.app.ai.service.DeepSeekClient.complete_json", return_value=DeepSeekResult(payload, {"prompt_tokens": 10}, 20, "stop")):
            queued = self.request("POST", f"/api/v1/sessions/{session_id}/ai-review")
        self.assertEqual(queued.status_code, 202)
        job = self.client.get(f"/api/v1/analysis-jobs/{queued.json()['job_id']}").json()
        self.assertEqual(job["status"], "complete", job)
        analysis = self.client.get(f"/api/v1/sessions/{session_id}/analysis").json()
        self.assertEqual(analysis["semantic_provider"], "deepseek")
        self.assertEqual(analysis["ai_review"]["scene"]["scene_type"], "casual_chat")
        self.request("PUT", "/api/v1/me/preferences", json={"ai_enabled": False})

    def test_session_audio_marker_and_qwen_analysis_flow(self) -> None:
        created = self.request(
            "POST", "/api/v1/sessions",
            json={"title": "Test conversation", "scenario": "Casual Conversation"},
        )
        self.assertEqual(created.status_code, 201)
        session_id = created.json()["id"]
        self.assertNotIn("audio_path", created.json())
        self.assertFalse(created.json()["has_audio"])

        marker = self.request(
            "POST", f"/api/v1/sessions/{session_id}/markers",
            json={"id": "marker-test", "timestamp_ms": 8900},
        )
        self.assertEqual(marker.status_code, 201)
        duplicate = self.request(
            "POST", f"/api/v1/sessions/{session_id}/markers",
            json={"id": "marker-test", "timestamp_ms": 8900},
        )
        self.assertEqual(duplicate.status_code, 201)
        self.assertEqual(len(self.client.get(f"/api/v1/sessions/{session_id}").json()["markers"]), 1)

        upload = self.request(
            "POST", f"/api/v1/sessions/{session_id}/audio?duration_ms=24500",
            files={"audio": ("recording.webm", b"test-audio", "audio/webm")},
        )
        self.assertEqual(upload.status_code, 200)
        audio = self.client.get(f"/api/v1/sessions/{session_id}/audio")
        self.assertEqual(audio.status_code, 200)
        self.assertEqual(audio.content, b"test-audio")

        analyzed = self.run_qwen_analysis(session_id, legacy_backend="local")
        self.assertEqual(analyzed.status_code, 202)
        self.assertEqual(analyzed.json()["requested_backend"], "qwen")
        self.assertTrue(analyzed.json()["job_id"])
        job_status = self.client.get(f"/api/v1/sessions/{session_id}/status").json()["job"]
        self.assertEqual(job_status["status"], "complete")
        self.assertEqual(job_status["progress"], 1)

        analysis = self.client.get(f"/api/v1/sessions/{session_id}/analysis").json()
        self.assertEqual(analysis["mode"], "real")
        self.assertEqual(analysis["schema_version"], "speech-analysis.v2")
        self.assertEqual(analysis["execution"]["provider"], "qwen")
        self.assertEqual(analysis["execution"]["retry_count"], 0)
        self.assertEqual(analysis["events"], [])

        confirmed = self.request(
            "PATCH", f"/api/v1/sessions/{session_id}/speakers",
            json={"user_speaker_id": "SPEAKER_01"},
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.json()["confirmed"])
        restored = self.client.get(f"/api/v1/sessions/{session_id}").json()
        self.assertEqual(restored["user_speaker_id"], "SPEAKER_01")
        self.assertTrue(restored["analysis"]["speakers"][1]["user_confirmed_identity"])

        renamed = self.request(
            "PATCH", f"/api/v1/sessions/{session_id}", json={"title": "Renamed conversation"}
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["title"], "Renamed conversation")

        corrected = self.request(
            "PATCH", f"/api/v1/sessions/{session_id}/turns/turn_002",
            json={"text": "Yes, that sounds useful."},
        )
        self.assertEqual(corrected.status_code, 200)
        self.assertEqual(corrected.json()["turn"]["text"], "Yes, that sounds useful.")
        self.assertEqual(
            self.client.get(f"/api/v1/sessions/{session_id}/analysis").json()["turns"][1]["text"],
            "Yes, that sounds useful.",
        )

        practice = self.request(
            "POST", "/api/v1/practices",
            json={
                "session_id": session_id,
                "event_id": "event_001",
                "title": "Continue the topic",
                "prompt": "What do you think?",
                "hint": "Add a reason and ask a follow-up question.",
            },
        )
        self.assertEqual(practice.status_code, 201)
        attempt = self.request(
            "POST", f"/api/v1/practice/{practice.json()['id']}/attempts",
            json={"response": "I think it could work because everyone can join. How about you?"},
        )
        self.assertEqual(attempt.status_code, 201)
        self.assertEqual(len(attempt.json()["feedback"]), 3)
        attempt_id = attempt.json()["id"]
        attempts = self.client.get("/api/v1/practice-attempts").json()
        self.assertTrue(any(item["id"] == attempt_id for item in attempts))

        settings = self.request("PUT", "/api/v1/me/preferences", json={"goal": "主动提问"})
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/me/preferences").json()["goal"], "主动提问")
        exported = self.client.get("/api/v1/me/export").json()
        self.assertGreaterEqual(len(exported["sessions"]), 1)
        self.assertTrue(any(item["id"] == attempt_id for item in exported["attempts"]))

    def test_csrf_and_owner_isolation(self) -> None:
        without_csrf = self.client.post("/api/v1/sessions", json={"title": "Blocked", "scenario": "Test"})
        self.assertEqual(without_csrf.status_code, 403)
        protected = self.request("POST", "/api/v1/sessions", json={"title": "Owner only", "scenario": "Test"})
        self.assertEqual(protected.status_code, 201)
        protected_id = protected.json()["id"]
        with TestClient(self.module.app) as other:
            created = other.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "another-strong-password", "display_name": "其他用户"})
            self.assertEqual(created.status_code, 201)
            self.assertEqual(other.get("/api/v1/sessions").json(), [])
            self.assertEqual(other.get(f"/api/v1/sessions/{protected_id}").status_code, 404)

    def test_user_data_deletion_clears_content_and_resets_preferences(self) -> None:
        self.request(
            "PUT",
            "/api/v1/me/preferences",
            json={"goal": "主动提问", "ai_enabled": True, "consent_version": "test", "pii_aliases": ["Alice"]},
        )
        deleted = self.request("DELETE", "/api/v1/me/data")
        self.assertEqual(deleted.status_code, 204)
        exported = self.client.get("/api/v1/me/export").json()
        self.assertEqual(exported["sessions"], [])
        self.assertEqual(exported["practices"], [])
        self.assertEqual(exported["attempts"], [])
        self.assertEqual(exported["ai_generations"], [])
        preferences = self.client.get("/api/v1/me/preferences").json()
        self.assertEqual(preferences["goal"], "延续话题")
        self.assertFalse(preferences["ai_enabled"])
        self.assertEqual(preferences["pii_aliases"], [])

    def test_qwen_requires_explicit_per_recording_consent(self) -> None:
        created = self.request("POST", "/api/v1/sessions", json={"title": "Consent", "scenario": "Test"})
        session_id = created.json()["id"]
        self.request(
            "POST",
            f"/api/v1/sessions/{session_id}/audio?duration_ms=1000",
            files={"audio": ("sample.webm", b"audio", "audio/webm")},
        )
        denied = self.request(
            "POST",
            f"/api/v1/sessions/{session_id}/analyze",
            json={
                "speech_backend": "qwen",
                "language_hints": ["en"],
                "speaker_policy": {"mode": "auto", "min_count": 1, "max_count": 8},
                "cloud_audio_consent": {"accepted": False, "version": "test"},
            },
        )
        self.assertEqual(denied.status_code, 409)

    def test_short_practice_audio_requires_qwen_consent(self) -> None:
        denied = self.request(
            "POST",
            "/api/v1/practice/transcribe?cloud_audio_consent=false",
            files={"audio": ("practice.webm", b"audio", "audio/webm")},
        )
        self.assertEqual(denied.status_code, 409)
        self.assertIn("千问", denied.json()["error"]["message"])

    def test_scene_conversation_is_persisted_and_counted_once(self) -> None:
        empty = self.client.get("/api/v1/practice/conversations/scene-persist-test?target_language=en")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json(), {"messages": [], "version": 0, "saved": False})

        first_payload = {
            "scene_id": "scene-persist-test",
            "title": "Coffee order",
            "prompt": "You are a barista.",
            "target_language": "en",
            "version": 0,
            "consent": True,
            "messages": [
                {"role": "assistant", "content": "What would you like?"},
                {"role": "user", "content": "A latte, please."},
            ],
        }
        with patch("backend.app.ai.service.DeepSeekClient.complete_json", return_value=DeepSeekResult({"reply": "What size would you like?"}, {"prompt_tokens": 8}, 12, "stop")):
            first = self.request("POST", "/api/v1/practice/conversation", json=first_payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["version"], 1)
        self.assertTrue(first.json()["saved"])
        self.assertIsNotNone(first.json()["attempt"])

        restored = self.client.get("/api/v1/practice/conversations/scene-persist-test?target_language=en")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["version"], 1)
        self.assertEqual(len(restored.json()["messages"]), 3)

        stale = dict(first_payload)
        stale["messages"] = [{"role": "user", "content": "Medium."}]
        with patch("backend.app.ai.service.DeepSeekClient.complete_json") as provider:
            conflict = self.request("POST", "/api/v1/practice/conversation", json=stale)
        self.assertEqual(conflict.status_code, 409)
        provider.assert_not_called()

        attempts = self.client.get("/api/v1/practice-attempts").json()
        self.assertEqual(len([item for item in attempts if item["event_id"] == "scene-persist-test"]), 1)

    def test_taskmaster_library_and_tts_cache(self) -> None:
        library = self.client.get("/api/v1/practice-library")
        self.assertEqual(library.status_code, 200)
        payload = library.json()
        self.assertEqual(payload["total"], 10)
        self.assertEqual(len(payload["categories"]), 5)
        self.assertTrue(all(category["item_count"] == 2 for category in payload["categories"]))
        self.assertTrue(all(len(category["scenes"]) == 2 for category in payload["categories"]))
        self.assertTrue(all(item["source"]["license"] == "CC BY 4.0" for item in payload["items"]))

        selected = payload["items"][0]
        canonical = self.request("POST", "/api/v1/practices", json={
            "event_id": selected["id"],
            "title": "tampered title",
            "prompt": "tampered prompt",
            "hint": "tampered hint",
        })
        self.assertEqual(canonical.status_code, 201)
        self.assertEqual(canonical.json()["title"], selected["title"])
        self.assertEqual(canonical.json()["prompt"], selected["prompt"])
        self.assertEqual(canonical.json()["source"], "taskmaster")

        with patch("backend.app.services.tts.QwenTtsProvider") as provider_class:
            provider_class.return_value.synthesize.return_value = TtsResult(
                audio=b"RIFF-api-test",
                content_type="audio/wav",
                usage={"input_tokens": 6},
                latency_ms=25,
                retry_count=0,
            )
            first = self.request("POST", "/api/v1/practice/tts", json={"text": selected["prompt"]})
            second = self.request("POST", "/api/v1/practice/tts", json={"text": selected["prompt"]})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.content, b"RIFF-api-test")
        self.assertEqual(first.headers["X-Beyond-Words-TTS-Model"], "qwen3-tts-flash")
        self.assertEqual(first.headers["X-Beyond-Words-TTS-Cache"], "miss")
        self.assertEqual(second.headers["X-Beyond-Words-TTS-Cache"], "hit")
        provider_class.return_value.synthesize.assert_called_once_with(selected["prompt"], "English")

    def test_japanese_practice_catalog_filters_pagination_and_safety(self) -> None:
        library = self.client.get(
            "/api/v1/practice-library?target_language=ja&native_language=zh&page=1&page_size=12"
        )
        self.assertEqual(library.status_code, 200)
        payload = library.json()
        self.assertEqual(payload["total"], 624)
        self.assertEqual(len(payload["categories"]), 8)
        self.assertEqual(len(payload["items"]), 12)
        self.assertEqual(payload["attributions"][0]["dataset"], "RealPersonaChat")
        self.assertEqual(payload["attributions"][0]["license"], "CC BY-SA 4.0")
        self.assertTrue(all(item["source"]["dataset"] == "RealPersonaChat" for item in payload["items"]))
        self.assertNotIn("JMultiWOZ", str(payload))
        self.assertTrue(all(item["opening_line"] for item in payload["items"]))
        self.assertTrue(all("speaker_1" not in item["hidden_context"] for item in payload["items"]))
        for native_language in ("zh", "en", "ja"):
            localized = self.client.get(
                "/api/v1/practice-library",
                params={"target_language": "ja", "native_language": native_language, "page_size": 1},
            )
            self.assertEqual(localized.status_code, 200)
            self.assertTrue(localized.json()["categories"][0]["label"])
        for target_language in ("en", "zh"):
            taskmaster = self.client.get(
                "/api/v1/practice-library",
                params={"target_language": target_language, "native_language": "ja"},
            )
            self.assertEqual(taskmaster.status_code, 200)
            self.assertEqual(taskmaster.json()["total"], 10)

        category = payload["categories"][0]
        scene = category["scenes"][0]
        filtered = self.client.get(
            "/api/v1/practice-library",
            params={
                "target_language": "ja", "native_language": "en",
                "category": category["code"], "scene": scene["code"],
                "page": 1, "page_size": 1,
            },
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(len(filtered.json()["items"]), 1)
        self.assertEqual(filtered.json()["items"][0]["category_code"], category["code"])
        self.assertEqual(filtered.json()["items"][0]["scene_code"], scene["code"])

        invalid = self.client.get(
            "/api/v1/practice-library?target_language=ja&category=not-a-category"
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["error"]["code"], "INVALID_PRACTICE_CATEGORY")

        with patch(
            "backend.app.services.dialogue_practice_catalog.CATALOG_PATH",
            Path(TEST_DIR.name) / "missing-practice-catalog.sqlite3",
        ):
            unavailable = self.client.get("/api/v1/practice-library?target_language=ja")
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.json()["error"]["code"], "PRACTICE_CATALOG_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
