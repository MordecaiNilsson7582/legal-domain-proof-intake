from datetime import date

from src.legal_intake import InfraiClient, MatterIntake, process_intake


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        import json
        return json.dumps(self.payload).encode()


def test_matching_txt_record_allows_onboarding():
    replies = [
        {"ok": True, "data": {"zone_id": "zone-7"}, "error": None, "metadata": {}},
        {"ok": True, "data": [{"record_type": "TXT", "content": "legal-verification=firm.example"}], "error": None, "metadata": {}},
        {"ok": True, "data": {"verified": True}, "error": None, "metadata": {}},
        {"ok": True, "data": {"id": "user-9"}, "error": None, "metadata": {}},
    ]

    def opener(request, timeout):
        return FakeResponse(replies.pop(0))

    intake = MatterIntake("m-1", "firm.example", "counsel@firm.example", "legal-verification=firm.example", "letter.pdf")
    result = process_intake(intake, InfraiClient("test-key", opener=opener), "secret", date(2026, 10, 26))
    assert result.domain_verified is True
    assert result.user_id == "user-9"
    assert result.follow_up_date == "2026-11-02"
    assert result.signed_document_url.startswith("signed://m-1/")
