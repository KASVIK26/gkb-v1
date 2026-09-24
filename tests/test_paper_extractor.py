"""Unit tests for curator/extractors/paper_extractor.py.

All tests mock the Groq (OpenAI-compatible) HTTP call — no real API key is required.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from curator.extractors.paper_extractor import (
    extract_paper_text,
    _validate_record,
    _call_groq_with_backoff,
    CONFIDENCE_VALUES,
)
from curator.validator import ValidationError


# ---------------------------------------------------------------------------
# Helpers to build mock urllib responses
# ---------------------------------------------------------------------------

def _mock_http_response(body: object, status: int = 200):
    """Return a mock that behaves like urllib.request.urlopen()'s context manager."""
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(body).encode("utf-8")
    mock_resp.status = status
    return mock_resp


def _chat_envelope(text: str) -> dict:
    """Wrap *text* in the OpenAI-compatible chat completions response envelope."""
    return {
        "choices": [
            {"message": {"role": "assistant", "content": text}}
        ]
    }


VALID_RECORDS_JSON = json.dumps([
    {
        "gene": "Sr33",
        "disease": "Stem Rust",
        "pathogen": "Puccinia graminis f.sp. tritici",
        "resistance_type": "race-specific",
        "varieties": ["Gatcher"],
        "confidence": "High",
        "iot_trigger": "humidity > 80%",
        "treatment": "Apply fungicide",
        "source": "Singh2011",
    }
])


# ---------------------------------------------------------------------------
# _validate_record
# ---------------------------------------------------------------------------

class TestValidateRecord:
    def test_valid_record_passes(self):
        rec = {
            "gene": "Sr33",
            "disease": "Stem Rust",
            "confidence": "High",
            "source": "Singh2011",
        }
        result = _validate_record(rec, 0)
        assert result["gene"] == "Sr33"

    def test_missing_required_field_raises(self):
        rec = {"gene": "Sr33", "disease": "Stem Rust", "confidence": "High"}  # missing source
        with pytest.raises(ValueError, match="source"):
            _validate_record(rec, 0)

    def test_invalid_confidence_raises(self):
        rec = {
            "gene": "Sr33",
            "disease": "Stem Rust",
            "confidence": "Very Low",   # not in CONFIDENCE_VALUES
            "source": "Singh2011",
        }
        with pytest.raises(ValueError, match="Very Low"):
            _validate_record(rec, 0)

    def test_non_dict_record_raises(self):
        with pytest.raises(ValueError, match="not a dict"):
            _validate_record("string", 0)

    def test_varieties_string_normalised_to_list(self):
        rec = {
            "gene": "Lr34",
            "disease": "Leaf Rust",
            "confidence": "Very High",
            "source": "Krattinger2009",
            "varieties": "Thatcher",  # string instead of list
        }
        result = _validate_record(rec, 0)
        assert result["varieties"] == ["Thatcher"]

    def test_optional_fields_get_defaults(self):
        rec = {
            "gene": "Yr18",
            "disease": "Stripe Rust",
            "confidence": "Medium",
            "source": "Lagudah2006",
        }
        result = _validate_record(rec, 0)
        assert result["pathogen"] is None
        assert result["resistance_type"] == "unknown"
        assert result["varieties"] == []
        assert result["iot_trigger"] is None
        assert result["treatment"] is None

    @pytest.mark.parametrize("conf", CONFIDENCE_VALUES)
    def test_all_valid_confidence_values_accepted(self, conf):
        rec = {"gene": "Sr33", "disease": "Stem Rust", "confidence": conf, "source": "s"}
        result = _validate_record(rec, 0)
        assert result["confidence"] == conf


# ---------------------------------------------------------------------------
# extract_paper_text — happy path
# ---------------------------------------------------------------------------

class TestExtractPaperText:
    def test_returns_validated_records_on_success(self):
        envelope = _chat_envelope(VALID_RECORDS_JSON)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_http_response(envelope)
            records = extract_paper_text("Some paper abstract.", api_key="test-key")

        assert len(records) == 1
        assert records[0]["gene"] == "Sr33"
        assert records[0]["confidence"] == "High"

    def test_empty_array_response_returns_empty_list(self):
        envelope = _chat_envelope("[]")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_http_response(envelope)
            records = extract_paper_text("No resistance genes here.", api_key="test-key")

        assert records == []

    def test_raises_on_empty_text(self):
        with pytest.raises(ValueError, match="non-empty"):
            extract_paper_text("", api_key="test-key")

    def test_raises_on_empty_api_key(self):
        with pytest.raises(ValueError, match="api_key"):
            extract_paper_text("Some text.", api_key="")

    def test_raises_on_invalid_json_response(self):
        envelope = _chat_envelope("This is not JSON at all")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_http_response(envelope)
            with pytest.raises(ValueError, match="invalid JSON"):
                extract_paper_text("Some text.", api_key="test-key")

    def test_raises_when_response_is_not_array(self):
        envelope = _chat_envelope(json.dumps({"gene": "Sr33"}))  # object, not array

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_http_response(envelope)
            with pytest.raises(ValueError, match="JSON array"):
                extract_paper_text("Some text.", api_key="test-key")

    def test_invalid_confidence_record_is_skipped_not_raised(self):
        """A single bad record in a batch should be skipped; others returned."""
        records_json = json.dumps([
            {"gene": "Sr33", "disease": "Stem Rust", "confidence": "High",    "source": "A"},
            {"gene": "Yr18", "disease": "Stripe Rust", "confidence": "Invalid!", "source": "B"},
        ])
        envelope = _chat_envelope(records_json)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_http_response(envelope)
            records = extract_paper_text("Some text.", api_key="test-key")

        # Only the valid record should be returned
        assert len(records) == 1
        assert records[0]["gene"] == "Sr33"


# ---------------------------------------------------------------------------
# _call_groq_with_backoff — retry behaviour
# ---------------------------------------------------------------------------

class TestCallGroqWithBackoff:
    def test_retries_on_429_and_succeeds(self):
        """Should sleep and retry after a 429, then return text on success."""
        import urllib.error

        # Build a fake 429 HTTPError
        http_429 = urllib.error.HTTPError(
            url="https://fake", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )
        # First call raises 429; second call succeeds
        success_resp = _mock_http_response(_chat_envelope("[]"))

        with patch("urllib.request.urlopen", side_effect=[http_429, success_resp]):
            with patch("time.sleep") as mock_sleep:
                result = _call_groq_with_backoff("text", "key")

        # time.sleep must have been called once (for the 429 wait)
        mock_sleep.assert_called_once()
        assert result == "[]"

    def test_raises_after_max_retries(self):
        """Should raise RuntimeError after exhausting all retries."""
        import urllib.error

        http_429 = urllib.error.HTTPError(
            url="https://fake", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )

        with patch("urllib.request.urlopen", side_effect=http_429):
            with patch("time.sleep"):
                with pytest.raises(RuntimeError, match="429 after"):
                    _call_groq_with_backoff("text", "key")

    def test_non_429_http_error_not_retried(self):
        """A 500 error should not be retried — raise immediately."""
        import urllib.error

        http_500 = urllib.error.HTTPError(
            url="https://fake", code=500, msg="Internal Server Error", hdrs=None, fp=None
        )
        http_500.fp = None

        with patch("urllib.request.urlopen", side_effect=http_500):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(RuntimeError, match="500"):
                    _call_groq_with_backoff("text", "key")

        # Must NOT have slept (no retry for non-429)
        mock_sleep.assert_not_called()

    def test_backoff_wait_increases_exponentially(self):
        """Each successive 429 should trigger a longer sleep than the previous one."""
        import urllib.error

        http_429 = urllib.error.HTTPError(
            url="https://fake", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )
        success_resp = _mock_http_response(_chat_envelope("[]"))

        # Three 429s, then success
        side_effects = [http_429, http_429, http_429, success_resp]

        with patch("urllib.request.urlopen", side_effect=side_effects):
            with patch("time.sleep") as mock_sleep:
                _call_groq_with_backoff("text", "key")

        waits = [c.args[0] for c in mock_sleep.call_args_list]
        assert len(waits) == 3
        # Each wait should be strictly longer than the previous
        assert waits[0] < waits[1] < waits[2]
