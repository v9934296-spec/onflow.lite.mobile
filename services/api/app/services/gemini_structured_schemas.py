"""
JSON Schema for Gemini enrichment only (`GenerateContentConfig.response_schema`).

Main clip analysis schema lives inline in `gemini_clip_analyzer.py`.
"""

from __future__ import annotations

from typing import Any

ENRICHMENT_RESPONSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "review_addendum": {"type": "string"},
        "observation_bullets": {
            "type": "array",
            "items": {"type": "string"},
        },
        "coaching": {
            "type": "object",
            "properties": {
                "body_position": {"type": ["string", "null"]},
                "foot_placement": {"type": ["string", "null"]},
                "timing": {"type": ["string", "null"]},
                "board_control": {"type": ["string", "null"]},
                "commitment": {"type": ["string", "null"]},
                "balance": {"type": ["string", "null"]},
                "style_notes": {"type": ["string", "null"]},
                "improvement_drill": {"type": ["string", "null"]},
            },
            "required": [
                "body_position",
                "foot_placement",
                "timing",
                "board_control",
                "commitment",
                "balance",
                "style_notes",
                "improvement_drill",
            ],
        },
        "landed": {
            "type": "string",
            "enum": ["yes", "no", "unclear"],
        },
    },
    "required": ["review_addendum", "landed"],
}
