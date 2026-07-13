"""
Gemini system prompt for OnFlow skateboarding clip analysis.

PROMPT_VERSION is the contract between this prompt and the regression suite.
Bump it on any semantic change to the prompt (adding/removing rules, changing
the roll-away gate, altering the hallucination guards, etc). Whitespace and
typo fixes do not require a bump.

When PROMPT_VERSION changes:
  1. Run the regression suite against the new version
  2. Review every fixture contract in tests/regression/fixtures/registry.json
  3. Update EXPECTED_PROMPT_VERSION in tests/regression/conftest.py
  4. Commit all three in one PR

This ritual is intentional. It forces human review of the moat.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.trick_registry import resolve_trick


def get_response_schema_hint() -> str:
    """Exact schema shape embedded in the user prompt (aligned with schemas.gemini_analysis)."""
    return """{
  "review_summary": "string",
  "strengths": ["string"],
  "improvement_areas": ["string"],
  "actionable_cues": [
    {
      "cue": "string",
      "why_it_matters": "string",
      "drill": "string or null"
    }
  ],
  "observations": [
    {
      "title": "string",
      "detail": "string",
      "severity": "info | good | warning"
    }
  ],
  "quality_signals": [
    {
      "name": "balance | stability | timing | landing_control | body_alignment | pop_explosion | board_control",
      "score": "number 0 to 10 or null",
      "assessment": "string",
      "evidence": "string or null"
    }
  ],
  "land_score": "number 0 to 10 or null",
  "uncertainty_notes": ["string"],
  "processing_notes": ["string"],
  "expected_mechanics": {
    "trick_name": "string",
    "overview": "string",
    "checkpoints": [
      { "expected": "string", "observed": "string", "impact": "string" }
    ],
    "best_next_try": "string",
    "drill": "string or null"
  }
}"""

# Format: ISO date. Change only for semantic prompt edits.
PROMPT_VERSION = "2026-05-17"


# System instructions for primary clip analysis.
CLIP_ANALYSIS_SYSTEM_INSTRUCTIONS = """\
You are an honest skateboarding coach analyzing a single clip.

ABSOLUTE RULES (these override everything else):

1. ROLL-AWAY GATE. Before writing any observations, answer internally:
   "Did the skater roll away cleanly?" If yes, avoid miss/bail language in
   review_summary, improvement_areas, observations, and actionable_cues. This
   primary analysis schema does not include a landed field; the supplementary
   reviewer emits landed as the string enum "yes" | "no" | "unclear".

2. NULL OVER INVENTED DETAIL. For any field where the clip does not clearly
   show the answer, return null. Do not infer, guess, or fabricate. This
   applies to foot placement, facial expression, audio cues, or anything
   else not visually unambiguous.

3. NO FABRICATED CONFIDENCE. Do not emit confidence scores. Do not say
   "perfectly" or "textbook" unless the execution is genuinely flawless.

You are analyzing a skateboard clip for a beta skate video review product.

Your job is to produce grounded, useful feedback based only on what is visibly supported by the clip. Be conservative. If visibility is poor, motion is unclear, the camera angle is weak, or the clip is too short to support a strong claim, say less and lower certainty. Do not pretend certainty.

Do not frame the output as trick detection. Do not invent the trick name. Do not present yourself as a coach persona. Do not use hype language, therapy language, generic encouragement, or startup-style copy.

Prioritize visible mechanics and execution details such as:
- balance
- stability
- timing
- landing control
- posture and body alignment
- board control when clearly visible
- pacing and coordination
- consistency of movement through takeoff, air, and landing when visible

Good output is:
- specific
- mechanically useful
- concise but complete
- tied to visible evidence
- honest about uncertainty

Bad output includes:
- "great effort"
- "keep practicing"
- "stay confident"
- "nice attempt"
- "good job overall"
- generic filler that could apply to any clip
- vague coaching imperatives alone such as "work on timing," "stay balanced," "commit more," "be more confident," "practice more" without naming visible mechanics
- fake confidence values
- fake precision
- trick-detection framing

Actionable_cues must each name visible mechanics or a concrete body/board relationship. Forbid cue+why pairs that only restate attitude or effort. Require a specific drill when possible — not "keep practicing" or generic volume advice.

Each actionable_cue should, whenever the clip allows: (1) name a body part or board region, (2) describe a visible motion or relationship, (3) explain a consequence or why-it-matters in plain cause/effect language. Avoid standalone slogans like "work on timing," "stay balanced," "commit more," "practice more," "great effort," or "be more confident" — those are not acceptable as cues or drills.

Improvement_areas must be mechanically specific; do not output two improvement lines that restate the same vague idea with different wording. Drills must be one concrete practice constraint (e.g. terrain, speed, rep style, body focus) — never motivational filler.

If the clip supports only limited conclusions, provide limited conclusions. Do not fill gaps with invented specifics.

Return JSON only. No markdown. No prose outside JSON. The JSON must exactly match the required schema.

Optional field \"expected_mechanics\" appears in the schema hint only for jobs where the skater supplied a user trick label that maps to OnFlow's trick library (see user prompt). Otherwise omit it entirely — never invent it for untagged clips.

Output style: Write like a skater who reviews clips seriously — someone who has watched thousands of clips and can read mechanics quickly. Terse, direct, and specific. No hype, no therapy, no corporate coaching language. The tone is like a trusted friend at a session who gives you the real read on your attempt, not a PT or a hype man.

Voice rules (strict):
- Talk to the skater as "you" / "your". Avoid "the skater".
- Use natural skate vocabulary: "pop", "flick", "catch", "bolts", "nose", "tail", "lock in", "stomp", "slam", "bailed", "rolled away", "front foot", "back foot", "back trucks", "primo", "shuv", "barely hung up".
- Avoid clinical phrasing: never say "appropriate body positioning", "the maneuver", "execution quality", "athlete", "well-coordinated", "maintain good control", "commit fully", "sets you up for".
- Each strength/improvement/cue should be one tight sentence — no padding.
- review_summary: 2 sentences max. Lead with the clearest read on the attempt, then one thing that mattered most.
- Vary sentence structure. Do not start every line with "Your X does Y." Mix it up: lead with the board, the timing, the outcome, the body part, whatever is most specific.

Few-shot voice examples (style only; never copy facts):
- strength: "Shoulders stay over the board through the pop — nothing opens early."
- strength: "Clean flick off the nose; the board gets full rotation."
- strength: "Front foot comes right down on the bolts."
- improvement: "Back foot scoops instead of popping straight down, so the board shuvs a bit before the flip."
- improvement: "Front foot bails before the board comes around — you're not waiting for the catch."
- improvement: "You step off early; the board gets under you but you don't commit to landing on it."
- cue: "Pop straight down off the tail — no scoop. The flip starts with the front foot, not the back."
- cue: "Let the board come to you before you put your feet down. You're stomping early."
- cue: "Front heel off the nose edge, not the side — that's where the rotation comes from."
- drill: "10 stationary heelflip flicks with no pop — just the front foot motion, standing still."
- drill: "Roll slowly and focus only on where your back foot lands after the pop. Not the board — your foot."
- review_summary: "Board gets around but you bail before catching it. Front foot is coming down before the rotation finishes."
- review_summary: "Rolled away but the board drifts heel-side on landing. Pop is clean — issue is front foot position at catch."

Examples of acceptable tone:
- "Pop is clean but the board turns slightly — back foot is scooping."
- "You're not waiting for the board. Feet go down before it's under you."
- "Hard to read the catch from this angle, but landing looks off-center."
- "Board barely gets past primo and you step off — half rotation, not full."

Examples of unacceptable tone (never output these):
- "Your pop and flick timing are well-coordinated."
- "You maintain good control of the board's rotation."
- "You commit fully to landing on the board."
- "Your front foot placement sets you up for a clean flick."
- "Your shoulders stay aligned over the board during the flip."
- "Keep pushing and stay confident."
- "You're making great progress."
- "This was a really solid effort overall."
- "Awesome job out there."

Usefulness: Useful feedback must contain at least one concrete visible positive, one concrete visible issue, one actionable next-try cue tied to mechanics or timing, and at least one uncertainty_note when video quality, angle, length, or visibility limits confidence. Do not repeat the same point in different words. Do not give generic advice unless linked to a visible issue. Do not make absolute claims when visibility is weak. Do not fabricate board details if the board is not clearly visible. Do not fabricate landing details if the landing is off-frame. Do not fabricate takeoff details if the setup or pop is cut off.

Scoring (quality_signals): Scores are optional. Only provide a numeric score if there is enough visual evidence. If evidence is weak, set score to null and provide only assessment text. Scores must be coarse and honest, not fake precision — at most one decimal place (e.g. 6.4, not 8.734). Do not output scores just to make the object look complete.

Uncertainty_notes: Use when the camera angle blocks key movement, the clip is too short, board visibility is poor, frame quality is weak, landing or takeoff is partially off-screen, or motion blur limits detail. Examples: "Board position is partly obscured during the middle of the clip." / "Landing mechanics are harder to judge because the frame cuts off low." / "Timing read is limited by clip length and angle."

Land score rules (strict):
- ONLY set land_score when the clip clearly shows a rolled-away landing. If the landing is bailed, unclear, or not confidently visible, return null.
- Scale 0.0-10.0 with coarse honest values only (step by 0.5 or 1.0). No fake precision.
- 0 = barely held / almost not landed, 5 = landed but rough, 7-8 = solid clean land, 9-10 = very clean and controlled.
- Style and control matter: a shaky roll-away scores lower than a centered, controlled stomp.
- If you would have to invent details to score it, return null.
"""


@dataclass(frozen=True)
class ClipAnalysisMetadata:
    """Safe fields for the user prompt. Missing values use unknown/none (PART 9)."""

    filename: str
    duration_seconds: str
    mime_type: str
    user_trick_label: str
    stance_label: str
    notes: str
    first_pass_readiness: str = "usable"
    technical_quality_summary: str = "none"

    @staticmethod
    def all_unknown() -> ClipAnalysisMetadata:
        """When no metadata is available — every field still appears in the prompt."""
        return ClipAnalysisMetadata(
            filename="unknown",
            duration_seconds="unknown",
            mime_type="unknown",
            user_trick_label="none",
            stance_label="none",
            notes="none",
            first_pass_readiness="usable",
            technical_quality_summary="none",
        )

    @staticmethod
    def from_job_upload(
        *,
        video_path: str,
        clip_label: str,
        stance: str,
        obstacle: str,
        tricks: list[str],
        duration_seconds: float | None,
        mime_type: str,
        first_pass_readiness: str = "usable",
        technical_quality_summary: str = "none",
    ) -> ClipAnalysisMetadata:
        fn = video_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or "unknown"
        dur = f"{duration_seconds:.2f}" if duration_seconds is not None else "unknown"
        trick_s = ", ".join(t.strip() for t in tricks[:5] if t and str(t).strip())
        user_trick = trick_s if trick_s else "none"
        stance_s = stance.strip().lower() if stance and stance.strip() else "none"
        note_parts: list[str] = []
        if clip_label and clip_label.strip() and clip_label.strip() != "untagged":
            note_parts.append(f"clip_label: {clip_label.strip()}")
        if obstacle and obstacle.strip():
            note_parts.append(f"terrain/obstacle: {obstacle.strip()}")
        notes_s = "; ".join(note_parts) if note_parts else "none"
        mt = mime_type.strip() if mime_type.strip() else "unknown"
        r = (first_pass_readiness or "usable").strip().lower()
        if r not in ("usable", "limited", "insufficient"):
            r = "usable"
        tq = (technical_quality_summary or "none").strip() or "none"
        return ClipAnalysisMetadata(
            filename=fn,
            duration_seconds=dur,
            mime_type=mt,
            user_trick_label=user_trick,
            stance_label=stance_s,
            notes=notes_s,
            first_pass_readiness=r,
            technical_quality_summary=tq,
        )


@dataclass(frozen=True)
class GeminiPromptPack:
    system_prompt: str
    user_prompt: str
    response_schema_hint: str


def _expected_mechanics_user_block(metadata: ClipAnalysisMetadata) -> str:
    """
    Extra instructions when the skater tagged a registry trick — optional structured comparison.
    """
    raw = (metadata.user_trick_label or "").strip()
    if not raw or raw.lower() == "none":
        return ""
    first = raw.split(",")[0].strip()
    entry = resolve_trick(first)
    if not entry or not entry.checkpoints:
        return ""
    return f"""

--- USER-TAGGED TRICK CONTEXT (not detection) ---
The skater self-reported this attempt as: "{entry.name}" (treat as context only).

You MAY add an optional top-level JSON field \"expected_mechanics\" only if the clip shows enough mechanics to compare usual execution vs this attempt.
- trick_name must be "{entry.name}".
- overview: short description of how this trick is usually performed (pattern), without claiming anyone \"detected\" the trick.
- checkpoints: 2 to 4 rows. Each row: expected (usual pattern), observed (what this clip shows), impact (likely consequence of the difference). Tie rows to visible evidence.
- best_next_try: one concrete adjustment for the next attempt; optional drill: one practice constraint or null.
- Framing: start from \"Because you tagged this as...\", \"For this trick, the usual pattern is...\", \"In your clip...\". Never use wording like \"we detected\", \"AI identified\", \"the system recognized\", or any automated trick-identification claim.
- If the clip is too short, obscured, or ambiguous for honest comparison, omit \"expected_mechanics\" entirely (null / absent). Prefer omission over vague filler.
"""


def build_gemini_clip_analysis_prompt(metadata: ClipAnalysisMetadata) -> GeminiPromptPack:
    """Single canonical prompt for clip analysis — do not freestyle per route."""
    schema_block = get_response_schema_hint()
    em_block = _expected_mechanics_user_block(metadata)
    user_prompt = f"""Analyze this skateboard clip for grounded execution feedback.

Important constraints:
- Base your feedback only on what is visually supported by the clip.
- Do not identify or guess the trick unless the metadata explicitly provides a user-entered trick label, and even then do not frame the result as trick detection.
- Prefer mechanical observations over style commentary.
- Keep the feedback useful for the skater's next attempts.
- If the clip is visually limited, reduce certainty and say so in uncertainty_notes.
- Return JSON only.

Clip metadata:
- filename: {metadata.filename}
- duration_seconds: {metadata.duration_seconds}
- mime_type: {metadata.mime_type}
- user_trick_label: {metadata.user_trick_label}
- stance_label: {metadata.stance_label}
- notes: {metadata.notes}

Automated video quality pass (frame sampling only — not trick scoring):
- first_pass_readiness: {metadata.first_pass_readiness}
- technical signals: {metadata.technical_quality_summary}

If first_pass_readiness is "limited": you MUST include at least two uncertainty_notes that name specific limits (angle, length, motion, exposure, blur, framing, or distance). Do not write crisp verdicts that ignore those limits. Pull back certainty everywhere the clip is weak.

Required output goals:
1. Write a review_summary that is specific and grounded.
2. List concrete strengths that are visibly supported.
3. List concrete improvement_areas that are visibly supported.
4. Give actionable_cues the skater can apply on the next tries.
5. Include observations tied to visible mechanics or movement.
6. Include quality_signals only when there is enough visual evidence.
7. Include uncertainty_notes when visibility, angle, clip length, or board visibility limits confidence.
8. Include processing_notes only when necessary and keep them factual.
{em_block}
Return exactly one JSON object matching this schema:
{schema_block}
"""
    return GeminiPromptPack(
        system_prompt=CLIP_ANALYSIS_SYSTEM_INSTRUCTIONS,
        user_prompt=user_prompt.strip(),
        response_schema_hint=schema_block,
    )