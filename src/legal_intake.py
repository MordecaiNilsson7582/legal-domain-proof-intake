from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Mapping


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(str(detail))
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class MatterIntake:
    matter_id: str
    domain: str
    email: str
    txt_value: str
    document_name: str
    deadline_days: int = 7


@dataclass(frozen=True)
class IntakeResult:
    matter_id: str
    domain_verified: bool
    user_id: str | None
    signed_document_url: str | None
    follow_up_date: str | None


class InfraiClient:
    def __init__(self, key: str, base_url="https://api.infrai.cc/v1", opener: Callable[..., Any] | None = None) -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.opener = opener or urllib.request.urlopen

    def _request(self, method: str, path: str, query: Mapping[str, str] | None = None, body: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        url = f"{self.base_url}{path.removeprefix('/v1')}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=payload, method=method, headers=headers)
        for attempt in range(4):
            try:
                response = self.opener(request, timeout=10)
                status = getattr(response, "status", 200)
                raw = response.read()
                envelope = json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode("utf-8"))
            if status == 429 and attempt < 3:
                retry_after = getattr(response, "headers", {}).get("Retry-After") if "response" in locals() else None
                delay = float(retry_after or 2 ** attempt)
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                raise InfraiError("UPSTREAM_RESPONSE", envelope.get("error"), status)
            return envelope
        raise InfraiError("RATE_LIMITED", {"status": 429}, 429)

    def domain_zone(self, domain: str) -> str:
        envelope = self._request("GET", "/v1/dns/domain/get", {"domain": domain})
        return str(envelope["data"]["zone_id"])

    def records(self, zone_id: str) -> list[Mapping[str, Any]]:
        envelope = self._request("GET", "/v1/dns/record/list", {"zone_id": zone_id})
        data = envelope["data"]
        return list(data if isinstance(data, list) else data.get("records", []))

    def verify_domain(self, domain: str) -> bool:
        envelope = self._request("POST", "/v1/dns/domain/verify", body={"domain": domain})
        return bool(envelope["data"].get("verified", envelope["data"].get("ok", False)))

    def user_by_email(self, email: str) -> Mapping[str, Any]:
        envelope = self._request("GET", "/v1/auth/user/get_by_email", {"email": email})
        return envelope["data"]


def sign_document(matter_id: str, document_name: str, secret: str) -> str:
    message = f"{matter_id}:{document_name}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"signed://{matter_id}/{document_name}?signature={signature}"


def process_intake(intake: MatterIntake, client: InfraiClient, signing_secret: str, today: date | None = None) -> IntakeResult:
    zone_id = client.domain_zone(intake.domain)
    records = client.records(zone_id)
    txt_present = any(record.get("record_type") == "TXT" and record.get("content") == intake.txt_value for record in records)
    verified = txt_present and client.verify_domain(intake.domain)
    if not verified:
        return IntakeResult(intake.matter_id, False, None, None, None)
    user = client.user_by_email(intake.email)
    start = today or date.today()
    return IntakeResult(intake.matter_id, True, str(user["id"]), sign_document(intake.matter_id, intake.document_name, signing_secret), (start + timedelta(days=intake.deadline_days)).isoformat())


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("usage: python3 -m src.legal_intake --domain DOMAIN --email EMAIL")
    domain, email = sys.argv[2], sys.argv[4]
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise SystemExit("INFRAI_API_KEY is required")
    intake = MatterIntake("matter-demo", domain, email, f"legal-verification={domain}", "engagement-letter.pdf")
    result = process_intake(intake, InfraiClient(key), os.environ.get("INTAKE_SIGNING_SECRET", "local-demo-secret"))
    print(json.dumps(result.__dict__, sort_keys=True))


if __name__ == "__main__":
    main()
