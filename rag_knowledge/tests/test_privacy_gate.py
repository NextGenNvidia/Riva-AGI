"""Unit tests for the fail-closed Privacy Gate in PR 1a."""

import pytest

from rag_knowledge.ingestion.privacy import (
    PrivacyGateError,
    assert_no_privacy_leaks,
    redact_private_text,
    scan_for_privacy_leaks,
)


def test_unanchored_privacy_gate_detection():
    text_with_phone = "Contact the student coordinator at +91 9876543210 for registration."
    leaks = scan_for_privacy_leaks(text_with_phone)
    assert len(leaks["phones"]) == 1
    assert "9876543210" in leaks["phones"][0]

    text_with_email = "Send notes to student.help@university.edu before noon."
    leaks = scan_for_privacy_leaks(text_with_email)
    assert len(leaks["emails"]) == 1
    assert leaks["emails"][0] == "student.help@university.edu"

    doc = {
        "id": "doc_leak",
        "title": "Admissions",
        "content": "Call 9876543210 immediately",
    }
    with pytest.raises(PrivacyGateError):
        assert_no_privacy_leaks([doc])


def test_safe_identifier_whitelist():
    safe_roll = "2025R0111101103"
    text_with_roll = f"Student with Roll Number {safe_roll} has completed registration."
    leaks = scan_for_privacy_leaks(text_with_roll, safe_identifiers={safe_roll})
    assert len(leaks["phones"]) == 0

    doc = {
        "id": "doc_safe",
        "title": "Student Record",
        "content": f"Roll number is {safe_roll}.",
    }
    assert_no_privacy_leaks([doc], safe_identifiers={safe_roll})


def test_opt_in_redaction():
    text = "Contact 9876543210 or email test@example.com for info."
    redacted = redact_private_text(text)
    assert "9876543210" not in redacted
    assert "test@example.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted


def test_known_private_value_leak_detection():
    private_names = {"Sanjeev Dutt", "Bhanu Pratap Rai"}
    doc = {
        "id": "doc_test_father",
        "title": "Nominal Roll Record",
        "content": "Student record with guardian Sanjeev Dutt listed.",
    }
    with pytest.raises(PrivacyGateError):
        assert_no_privacy_leaks([doc], known_private_values=private_names)


def test_full_field_redaction():
    doc = {
        "id": "doc_leak_all",
        "title": "Meeting with test@example.com",
        "summary": "Notes for +91 9876543210 coordinator",
        "content": "Secret note: contact 9876543210 or email test@example.com",
        "aliases": ["test@example.com"],
        "keywords": ["9876543210"],
    }
    assert_no_privacy_leaks([doc], opt_in_redact=True)
    assert "[REDACTED_EMAIL]" in doc["title"]
    assert "[REDACTED_PHONE]" in doc["summary"]
    assert "[REDACTED_EMAIL]" in doc["aliases"][0]
    assert "[REDACTED_PHONE]" in doc["keywords"][0]


def test_father_name_in_content_flagged_and_redacted():
    doc = {
        "id": "doc_eval",
        "title": "Nominal Roll Summary",
        "content": "Candidate: Rohan Gupta, Father Name: Ramesh Gupta, Branch: IT",
    }
    with pytest.raises(PrivacyGateError):
        assert_no_privacy_leaks([dict(doc)], known_private_values={"Ramesh Gupta"})

    cloned = dict(doc)
    assert_no_privacy_leaks([cloned], known_private_values={"Ramesh Gupta"}, opt_in_redact=True)
    assert "Ramesh Gupta" not in cloned["content"]
    assert "[REDACTED]" in cloned["content"]
