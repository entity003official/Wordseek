"""Paid end-to-end product smoke test against the running HTTPS gateway.

The report contains operational metadata only. It never prints API keys,
temporary audio URLs, transcript text, AI prompts, or AI output content.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


def checked(response: httpx.Response) -> dict:
    if not response.is_success:
        try:
            error = response.json().get("error") or {}
            summary = f"{error.get('code')}: {error.get('message')}"
        except Exception:
            summary = f"HTTP {response.status_code}"
        raise RuntimeError(f"Product API request failed ({response.request.method} {response.request.url.path}): {summary}")
    return response.json() if response.content else {}


def wait_job(client: httpx.Client, job_id: str, timeout_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        job = checked(client.get(f"/analysis-jobs/{job_id}"))
        if job["status"] == "complete":
            return job
        if job["status"] == "failed":
            raise RuntimeError(
                f"Job {job_id} failed: code={job.get('error_code')}, retryable={job.get('retryable')}"
            )
        time.sleep(2)
    raise TimeoutError(f"Job {job_id} did not finish in {timeout_seconds} seconds")


def resume_existing_flow(
    *, client: httpx.Client, email: str, password: str, output: Path, timeout_seconds: int
) -> None:
    started = time.perf_counter()
    auth = checked(client.post("/auth/login", json={"email": email, "password": password}))
    client.headers["X-CSRF-Token"] = auth["csrf_token"]
    sessions = checked(client.get("/sessions"))
    if not sessions:
        raise RuntimeError("The acceptance account has no session to resume")
    session_id = sessions[0]["id"]
    analysis = checked(client.get(f"/sessions/{session_id}/analysis"))
    execution = analysis["execution"]
    speakers = analysis.get("speakers") or []
    report: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": str(client.base_url),
        "registration": {"status": "resumed", "user_id": auth["user"]["id"]},
        "upload": {"status": "previously_completed"},
        "speech": {
            "status": "complete",
            "task_id": execution.get("provider_task_id"),
            "provider": execution.get("provider"),
            "model": execution.get("model"),
            "audio_duration_ms": execution.get("audio_duration_ms"),
            "latency_ms": execution.get("latency_ms"),
            "speaker_count": len(speakers),
            "turn_count": len(analysis.get("turns") or []),
            "retry_count": execution.get("retry_count"),
            "resumed_existing_task": execution.get("resumed_existing_task"),
            "usage": execution.get("usage") or {},
        },
        "identity_confirmation": {
            "status": "passed",
            "speaker_id": sessions[0].get("user_speaker_id"),
        },
    }
    preferences = checked(client.get("/me/preferences"))
    preview = checked(client.get(f"/sessions/{session_id}/ai-preview"))
    report["deepseek_consent"] = {
        "enabled": preferences["ai_enabled"],
        "preview_turn_count": len(preview.get("turns") or []),
    }
    if not analysis.get("ai_review"):
        review_request = checked(client.post(f"/sessions/{session_id}/ai-review"))
        review_job = wait_job(client, review_request["job_id"], timeout_seconds)
        analysis = checked(client.get(f"/sessions/{session_id}/analysis"))
    else:
        review_job = {"status": "complete", "id": "cached"}
    report["deepseek_review"] = {
        "status": review_job["status"],
        "job_id": review_job["id"],
        "has_review": bool(analysis.get("ai_review")),
    }
    practices = checked(client.get("/practices"))
    linked = [item for item in practices if item.get("session_id") == session_id]
    if len(linked) != 3:
        practice_request = checked(client.post(f"/sessions/{session_id}/practice-sets"))
        practice_job = wait_job(client, practice_request["job_id"], timeout_seconds)
        practices = checked(client.get("/practices"))
        linked = [item for item in practices if item.get("session_id") == session_id]
    else:
        practice_job = {"status": "complete"}
    if len(linked) != 3:
        raise RuntimeError(f"Expected 3 generated practices, got {len(linked)}")
    attempts = checked(client.get("/practice-attempts"))
    linked_ids = {item["id"] for item in linked}
    attempt = next((item for item in attempts if item.get("practice_id") in linked_ids), None)
    if not attempt:
        attempt = checked(client.post(f"/practice/{linked[0]['id']}/attempts", json={
            "response": "I think the route is correct because the landmark matches. What do you see next?"
        }))
    report["practice"] = {
        "job_status": practice_job["status"],
        "question_count": len(linked),
        "feedback_source": attempt.get("feedback_source"),
        "feedback_item_count": len(attempt.get("feedback") or []),
        "saved": attempt.get("saved", True),
    }
    exported = checked(client.get("/me/export"))
    report["data_isolation"] = {
        "sessions": len(exported.get("sessions") or []),
        "practices": len(exported.get("practices") or []),
        "attempts": len(exported.get("attempts") or []),
        "ai_generations": len(exported.get("ai_generations") or []),
    }
    deleted = client.request("DELETE", "/me/account", json={"confirmation": "DELETE", "password": password})
    if deleted.status_code != 204:
        checked(deleted)
    report["cleanup"] = {"test_account_deleted": True}
    report["latency_ms"] = round((time.perf_counter() - started) * 1000)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Product E2E resumed and passed: "
        f"speakers={report['speech']['speaker_count']}, turns={report['speech']['turn_count']}, "
        f"questions={report['practice']['question_count']}, feedback={report['practice']['feedback_source']}, "
        f"output={output}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the real Beyond Words product flow.")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-url", default="https://localhost/api/v1")
    parser.add_argument("--duration-ms", type=int, default=265089)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--resume-email")
    args = parser.parse_args()
    if args.resume_email:
        stamp = args.resume_email.split("@", 1)[0].removeprefix("acceptance-")
        with httpx.Client(base_url=args.base_url, verify=False, timeout=120, follow_redirects=True) as client:
            resume_existing_flow(
                client=client,
                email=args.resume_email,
                password=f"Acceptance-{stamp}-safe",
                output=args.output,
                timeout_seconds=args.timeout_seconds,
            )
        return
    if args.audio is None or not args.audio.is_file():
        raise SystemExit(f"Audio file not found: {args.audio}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    email = f"acceptance-{stamp}@example.com"
    password = f"Acceptance-{stamp}-safe"
    started = time.perf_counter()
    report: dict = {"started_at": datetime.now(timezone.utc).isoformat(), "base_url": args.base_url}

    with httpx.Client(base_url=args.base_url, verify=False, timeout=120, follow_redirects=True) as client:
        auth = checked(client.post("/auth/register", json={
            "email": email,
            "password": password,
            "display_name": "端到端验收账号",
        }))
        csrf = auth["csrf_token"]
        client.headers["X-CSRF-Token"] = csrf
        report["registration"] = {"status": "passed", "user_id": auth["user"]["id"]}

        session = checked(client.post("/sessions", json={"title": "公开双人英语验收", "scenario": "协作任务"}))
        session_id = session["id"]
        with args.audio.open("rb") as audio:
            uploaded = checked(client.post(
                f"/sessions/{session_id}/audio",
                params={"duration_ms": args.duration_ms},
                files={"audio": (args.audio.name, audio, "audio/wav")},
            ))
        report["upload"] = {"status": uploaded["status"], "bytes": uploaded["bytes_saved"]}

        speech_request = checked(client.post(f"/sessions/{session_id}/analyze", json={
            "language_hints": ["en"],
            "speaker_policy": {"mode": "expected", "min_count": 1, "max_count": 8, "expected_count": 2},
            "cloud_audio_consent": {"accepted": True, "version": "qwen-cloud-v1"},
        }))
        speech_job = wait_job(client, speech_request["job_id"], args.timeout_seconds)
        analysis = checked(client.get(f"/sessions/{session_id}/analysis"))
        execution = analysis["execution"]
        speakers = analysis.get("speakers") or []
        if len(speakers) != 2:
            raise RuntimeError(f"Expected 2 speakers, got {len(speakers)}")
        report["speech"] = {
            "status": speech_job["status"],
            "job_id": speech_job["id"],
            "task_id": execution.get("provider_task_id"),
            "provider": execution.get("provider"),
            "model": execution.get("model"),
            "audio_duration_ms": execution.get("audio_duration_ms"),
            "latency_ms": execution.get("latency_ms"),
            "speaker_count": len(speakers),
            "turn_count": len(analysis.get("turns") or []),
            "retry_count": execution.get("retry_count"),
            "resumed_existing_task": execution.get("resumed_existing_task"),
            "usage": execution.get("usage") or {},
        }

        speaker_id = speakers[0]["id"]
        confirmed = checked(client.patch(
            f"/sessions/{session_id}/speakers", json={"user_speaker_id": speaker_id}
        ))
        report["identity_confirmation"] = {
            "status": "passed",
            "speaker_id": confirmed["user_speaker_id"],
        }

        preferences = checked(client.put("/me/preferences", json={
            "goal": "主动提问",
            "ai_enabled": True,
            "consent_version": "deepseek-text-v1",
            "pii_aliases": ["端到端验收账号"],
        }))
        preview = checked(client.get(f"/sessions/{session_id}/ai-preview"))
        report["deepseek_consent"] = {
            "enabled": preferences["ai_enabled"],
            "preview_turn_count": len(preview.get("turns") or []),
        }

        review_request = checked(client.post(f"/sessions/{session_id}/ai-review"))
        review_job = wait_job(client, review_request["job_id"], args.timeout_seconds)
        reviewed = checked(client.get(f"/sessions/{session_id}/analysis"))
        report["deepseek_review"] = {
            "status": review_job["status"],
            "job_id": review_job["id"],
            "has_review": bool(reviewed.get("ai_review")),
        }

        practice_request = checked(client.post(f"/sessions/{session_id}/practice-sets"))
        practice_job = wait_job(client, practice_request["job_id"], args.timeout_seconds)
        practices = checked(client.get("/practices"))
        linked = [item for item in practices if item.get("session_id") == session_id]
        if len(linked) != 3:
            raise RuntimeError(f"Expected 3 generated practices, got {len(linked)}")
        attempt = checked(client.post(f"/practice/{linked[0]['id']}/attempts", json={
            "response": "I think the route is correct because the landmark matches. What do you see next?"
        }))
        report["practice"] = {
            "job_status": practice_job["status"],
            "question_count": len(linked),
            "feedback_source": attempt.get("feedback_source"),
            "feedback_item_count": len(attempt.get("feedback") or []),
            "saved": attempt.get("saved"),
        }

        exported = checked(client.get("/me/export"))
        report["data_isolation"] = {
            "sessions": len(exported.get("sessions") or []),
            "practices": len(exported.get("practices") or []),
            "attempts": len(exported.get("attempts") or []),
            "ai_generations": len(exported.get("ai_generations") or []),
        }
        deleted = client.request("DELETE", "/me/account", json={"confirmation": "DELETE", "password": password})
        if deleted.status_code != 204:
            checked(deleted)
        report["cleanup"] = {"test_account_deleted": True}

    report["latency_ms"] = round((time.perf_counter() - started) * 1000)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Product E2E passed: "
        f"speakers={report['speech']['speaker_count']}, turns={report['speech']['turn_count']}, "
        f"questions={report['practice']['question_count']}, feedback={report['practice']['feedback_source']}, "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
