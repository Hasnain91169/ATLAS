from atlas.workflows.email_triage import TriageMessage, generate_triage_report


def test_email_triage_categorizes_and_rationales():
    messages = [
        TriageMessage(
            message_id="1",
            sender="ceo@example.com",
            subject="Urgent: decision needed today",
            body="Please review and decide ASAP.",
        ),
        TriageMessage(
            message_id="2",
            sender="news@example.com",
            subject="Monthly newsletter",
            body="Unsubscribe anytime.",
        ),
        TriageMessage(
            message_id="3",
            sender="legal@example.com",
            subject="Contract breach notice",
            body="Legal review required.",
        ),
    ]

    report = generate_triage_report(messages)
    categories = {item["category"] for item in report.payload["items"]}

    assert "Urgent" in categories
    assert "Ignore" in categories
    assert any(item["rationale"] for item in report.payload["items"])
    assert any(alert.category == "legal" for alert in report.alerts)
