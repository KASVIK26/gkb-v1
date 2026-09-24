"""Extract structured resistance knowledge from paper text via Groq (legacy v1 extractor)."""

from __future__ import annotations

import json
import os
import time
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("gene", "disease", "confidence", "source")
OPTIONAL_FIELDS = ("pathogen", "resistance_type", "varieties", "iot_trigger", "treatment")
CONFIDENCE_VALUES = ("Very High", "High", "Medium")

SYSTEM_PROMPT = """You are a plant genomics expert. Extract crop disease resistance knowledge
from the provided text and return it as a JSON array -- no prose, no markdown fences, only raw JSON.

Each element must have exactly these fields:
  gene            - resistance gene or QTL name (e.g. "Sr33", "Fhb1")
  disease         - common disease name (e.g. "Stem Rust")
  pathogen        - pathogen species or null
  resistance_type - one of: "race-specific", "durable", "QTL", "unknown"
  varieties       - JSON array of variety names; empty array if not mentioned
  confidence      - exactly one of: "Very High", "High", "Medium"
  iot_trigger     - sensor trigger for treatment (e.g. "humidity > 80%") or null
  treatment       - recommended management action or null
  source          - brief citation e.g. "Singh2011" or dataset name

Rules:
- Only include genes/QTLs explicitly mentioned. Do NOT invent entries.
- confidence must be one of the three values above.
- Return [] if no resistance genes are mentioned.
- Output must be parseable by Python json.loads() -- no trailing commas, no comments.
"""

_MAX_RETRIES = 5
_BASE_WAIT = 2
_MAX_WAIT = 60
# Groq free tier — very fast inference, generous daily limits.
# Llama 3.3 70B has 128K context, strong JSON instruction following.
# Other Groq models if this hits limits:
#   llama-3.1-70b-versatile   — slightly older, same size
#   llama3-8b-8192            — lightweight fallback (8K ctx only)
#   mixtral-8x7b-32768        — 32K ctx alternative
_MODEL_NAME = "llama-3.3-70b-versatile"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _call_groq_with_backoff(prompt: str, api_key: str, model: str = _MODEL_NAME) -> str:
    """Call Groq chat completions with exponential back-off on 429 errors.

    Groq is OpenAI-API-compatible: POST /openai/v1/chat/completions with Bearer auth.
    Key env var: GROQ_API_KEY
    """
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.1,
    }).encode("utf-8")

    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(
                _GROQ_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(api_key),
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]

        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = min(_BASE_WAIT ** (attempt + 1), _MAX_WAIT)
                logger.warning(
                    "Groq rate-limited (429). Waiting %ds before retry %d/%d ...",
                    wait, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            body_text = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise RuntimeError("Groq API error {}: {}".format(exc.code, body_text)) from exc

        except Exception as exc:
            raise RuntimeError("Groq call failed: {}".format(exc)) from exc

    raise RuntimeError(
        "Groq returned 429 after {} retries. "
        "Wait a minute and retry, or switch model with --model llama3-8b-8192.".format(_MAX_RETRIES)
    )


def _validate_record(record: Any, index: int) -> dict:
    """Validate a single extracted record. Raises ValueError on failure."""
    if not isinstance(record, dict):
        raise ValueError("Record #{} is not a dict: {!r}".format(index, record))

    missing = [f for f in REQUIRED_FIELDS if not record.get(f)]
    if missing:
        raise ValueError("Record #{} missing required fields: {}".format(index, ", ".join(missing)))

    confidence = record.get("confidence", "")
    if confidence not in CONFIDENCE_VALUES:
        raise ValueError(
            "Record #{} has invalid confidence '{}'. Must be one of: {}".format(
                index, confidence, ", ".join(CONFIDENCE_VALUES)
            )
        )

    record.setdefault("pathogen", None)
    record.setdefault("resistance_type", "unknown")
    record.setdefault("varieties", [])
    record.setdefault("iot_trigger", None)
    record.setdefault("treatment", None)

    if isinstance(record["varieties"], str):
        record["varieties"] = [record["varieties"]]

    return record


def extract_paper_text(text: str, api_key: str, model: str = _MODEL_NAME) -> list:
    """Extract structured resistance records from paper text using Groq.

    Args:
        text:    Raw paper text (abstract or excerpt).
        api_key: Groq API key (GROQ_API_KEY from .env).
        model:   Groq model slug (default: llama-3.3-70b-versatile).

    Returns:
        List of validated record dicts (may be empty).
    """
    if not text or not text.strip():
        raise ValueError("text must be non-empty")
    if not api_key or not api_key.strip():
        raise ValueError("api_key must be non-empty")

    raw_text = _call_groq_with_backoff(text, api_key, model)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "LLM returned invalid JSON: {}\n\nRaw response:\n{}".format(exc, raw_text[:500])
        ) from exc

    if not isinstance(parsed, list):
        raise ValueError(
            "LLM returned a {} instead of a JSON array. Raw: {}".format(
                type(parsed).__name__, raw_text[:500]
            )
        )

    valid_records: list = []
    for i, record in enumerate(parsed):
        try:
            valid_records.append(_validate_record(record, i))
        except ValueError as exc:
            logger.warning("Skipping invalid record: %s", exc)

    return valid_records


def main() -> None:
    """CLI: extract from a plain-text file, append to data/review_queue.json."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract resistance records from a paper text file via Groq."
    )
    parser.add_argument("text_file", help="Path to a plain-text file")
    parser.add_argument("--api-key", default=os.environ.get("GROQ_API_KEY", ""),
                        help="Groq API key (default: GROQ_API_KEY env var)")
    parser.add_argument("--model", default=_MODEL_NAME)
    parser.add_argument("--out",
                        default=str(Path(__file__).resolve().parents[2] / "data" / "review_queue.json"))
    args = parser.parse_args()

    text_path = Path(args.text_file)
    if not text_path.exists():
        raise SystemExit("File not found: {}".format(text_path))

    text = text_path.read_text(encoding="utf-8")
    print("[Extractor] Sending {} characters to Groq ({}) ...".format(len(text), args.model))

    records = extract_paper_text(text, api_key=args.api_key, model=args.model)
    print("\n[Extractor] Extracted {} record(s):".format(len(records)))
    for rec in records:
        print("  * {} -> {} (confidence: {})".format(rec["gene"], rec["disease"], rec["confidence"]))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing: list = []
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []

    new_entries = [
        {"status": "pending", "source_file": str(text_path), "record": r}
        for r in records
    ]
    existing.extend(new_entries)
    out_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n[Extractor] Appended {} record(s) to {}".format(len(new_entries), out_path))
    print("Run: python curator/approve_extractions.py to review before loading.")


if __name__ == "__main__":
    main()
