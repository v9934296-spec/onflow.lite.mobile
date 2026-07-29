"""Tests for Gemini structured coaching observation parsing."""
from __future__ import annotations

import json

from app.services.gemini_reviewer import _empty_enrichment, _parse_enrichment_json


def test_full_valid_coaching_json() -> None:
    raw = json.dumps(
        {
            "review_addendum": "Clip shows a clean approach.",
            "observation_bullets": ["Good speed", "Shoulders square"],
            "coaching": {
                "body_position": "Shoulders aligned over the board",
                "foot_placement": "Front foot near bolts",
                "timing": "Pop was slightly early",
                "board_control": None,
                "commitment": "Full commitment on the attempt",
                "balance": None,
                "style_notes": "Arms relaxed",
                "improvement_drill": "Practice stationary pop shuvits 10x",
            },
            "landed": "yes",
        }
    )
    result = _parse_enrichment_json(raw)
    assert result["review_addendum"] == "Clip shows a clean approach."
    assert len(result["observation_bullets"]) == 2
    assert result["coaching"]["body_position"] == "Shoulders aligned over the board"
    assert result["coaching"]["board_control"] is None
    assert result["coaching"]["balance"] is None
    assert result["landed"] == "yes"


def test_full_coaching_json_with_all_fields_populated_and_landed_yes() -> None:
    coaching = {
        "body_position": "Shoulders stay stacked over the board.",
        "foot_placement": "Front foot lands near the front bolts.",
        "timing": "Pop and catch happen in a steady rhythm.",
        "board_control": "Board stays under the feet through contact.",
        "commitment": "You stay with the attempt through landing.",
        "balance": "Weight stays centered after contact.",
        "style_notes": "Arms stay quiet through the rollaway.",
        "improvement_drill": "Do 8 land-and-hold reps over the bolts.",
    }
    raw = json.dumps(
        {
            "review_addendum": "Clip shows a stable rollaway.",
            "observation_bullets": ["Board stays underneath you", "Landing is visible"],
            "coaching": coaching,
            "landed": "yes",
        }
    )

    result = _parse_enrichment_json(raw)

    assert result == {
        "review_addendum": "Clip shows a stable rollaway.",
        "observation_bullets": ["Board stays underneath you", "Landing is visible"],
        "coaching": coaching,
        "landed": "yes",
    }


def test_coaching_with_markdown_fences() -> None:
    raw = (
        "```json\n"
        + json.dumps(
            {
                "review_addendum": "test",
                "observation_bullets": [],
                "coaching": {
                    "body_position": "ok",
                    "foot_placement": None,
                    "timing": None,
                    "board_control": None,
                    "commitment": None,
                    "balance": None,
                    "style_notes": None,
                    "improvement_drill": None,
                },
                "landed": "no",
            }
        )
        + "\n```"
    )
    result = _parse_enrichment_json(raw)
    assert result["coaching"]["body_position"] == "ok"
    assert result["landed"] == "no"


def test_coaching_missing_entirely() -> None:
    raw = json.dumps(
        {
            "review_addendum": "Looks good.",
            "observation_bullets": ["Nice ollie"],
        }
    )
    result = _parse_enrichment_json(raw)
    assert result["coaching"]["body_position"] is None
    assert result["coaching"]["improvement_drill"] is None
    assert result["landed"] == "unclear"


def test_coaching_null_string_fields_become_none() -> None:
    raw = json.dumps(
        {
            "review_addendum": "",
            "observation_bullets": [],
            "coaching": {
                "body_position": "null",
                "foot_placement": "NULL",
                "timing": "",
                "board_control": "   ",
                "commitment": "Solid",
                "balance": None,
                "style_notes": "Clean style",
                "improvement_drill": None,
            },
            "landed": "unclear",
        }
    )
    result = _parse_enrichment_json(raw)
    assert result["coaching"]["body_position"] is None
    assert result["coaching"]["foot_placement"] is None
    assert result["coaching"]["timing"] is None
    assert result["coaching"]["board_control"] is None
    assert result["coaching"]["commitment"] == "Solid"
    assert result["coaching"]["style_notes"] == "Clean style"


def test_invalid_json_returns_empty_enrichment() -> None:
    result = _parse_enrichment_json("this is not json at all {{{")
    assert result["review_addendum"] == ""
    assert result["coaching"]["body_position"] is None
    assert result["landed"] == "unclear"


def test_empty_string_returns_empty_enrichment() -> None:
    result = _parse_enrichment_json("")
    assert result == _empty_enrichment()


def test_landed_invalid_value_defaults_unclear() -> None:
    raw = json.dumps(
        {
            "review_addendum": "",
            "observation_bullets": [],
            "coaching": {},
            "landed": "maybe",
        }
    )
    result = _parse_enrichment_json(raw)
    assert result["landed"] == "unclear"


def test_landed_boolean_true_defaults_unclear() -> None:
    """Gemini might return a boolean instead of string — handle gracefully."""
    raw = json.dumps(
        {
            "review_addendum": "",
            "observation_bullets": [],
            "coaching": {},
            "landed": True,
        }
    )
    result = _parse_enrichment_json(raw)
    assert result["landed"] == "unclear"
