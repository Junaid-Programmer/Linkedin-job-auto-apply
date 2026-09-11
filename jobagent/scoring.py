"""Score jobs against the user's profile.

Primary path uses the LLM; `keyword_score` is an offline fallback that
runs with zero dependencies when no API key is configured.
"""

from __future__ import annotations

import re

from jobagent.llm import LLMClient, LLMError

SCORING_SYSTEM = (
    "You are a hiring expert and career coach. Given a candidate profile and a "
    "job posting, you judge how good a fit the job is for the candidate. "
    "Be strict and realistic: a 90+ means an almost perfect fit, 70-89 is a "
    "strong fit worth applying to, 40-69 is a possible but not great fit, "
    "below 40 is a poor fit. "
    "Return ONLY a JSON object with exactly two keys: "
    '"score" (integer 0-100) and "reasons" (a short, 1-3 sentence explanation '
    'in plain text of the strongest signals for and against).'
)


def build_score_prompt(job: dict, profile: str) -> str:
    return f"""CANDIDATE PROFILE
{profile}

JOB POSTING
Title: {job.get('title')}
Company: {job.get('company')}
Location: {job.get('location')}
Posted: {job.get('posted')}

DESCRIPTION:
{job.get('description', '(no description available)')}

Evaluate the fit of this job for the candidate and return the JSON object."""


def score_job(llm: LLMClient, job: dict, profile: str) -> dict:
    """Score a single job. Returns {"score": int, "reasons": str}."""
    result = llm.chat_json(
        SCORING_SYSTEM,
        build_score_prompt(job, profile),
        temperature=0.1,
        max_tokens=500,
    )
    try:
        score = int(result.get("score"))
    except (TypeError, ValueError):
        raise LLMError(f"LLM returned a non-integer score: {result}")
    score = max(0, min(100, score))
    reasons = str(result.get("reasons", "")).strip()
    return {"score": score, "reasons": reasons}


# ----------------------------------------------------------------------
# Offline fallback (no LLM key required)
# ----------------------------------------------------------------------


def _normalize(value: str) -> str:
    """Lowercase and collapse non-alphanumeric runs to single spaces."""
    return re.sub(r"[^a-z0-9 ]+", " ", value.lower()).strip()


def profile_keywords(profile: str) -> tuple[list[str], list[str]]:
    """Extract (skill names, role phrases) from profile.md.

    Skills are parsed from the `## Skills` section; role phrases come
    from the `Roles:` line under `## Preferences` (split on commas so
    phrases such as "Operations Manager / Partner" stay together).
    """
    skills: list[str] = []
    roles: list[str] = []
    in_skills = False
    for line in profile.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Skills"):
            in_skills = True
            continue
        if stripped.startswith("## ") and in_skills:
            in_skills = False
        if in_skills and stripped.startswith("- "):
            name = stripped[2:].split("(")[0].strip().rstrip(",")
            if name:
                skills.append(name)
        if stripped.lower().startswith("- roles:") or stripped.lower().startswith("roles:"):
            roles_part = stripped.split(":", 1)[1]
            roles = [r.strip() for r in roles_part.split(",") if r.strip()]
    return skills, roles


def _role_fragments(roles: list[str]) -> list[str]:
    """Turn role phrases into matchable fragments (whole phrase + bigrams).

    "Admin & Operations Support" -> {"admin operations support",
    "admin operations", "operations support", ...} so a title like
    "Operations Support Associate" still matches.
    """
    fragments: set[str] = set()
    for role in roles:
        base = _normalize(role)
        if not base:
            continue
        fragments.add(base)
        words = base.split()
        for i in range(len(words) - 1):
            fragments.add(" ".join(words[i : i + 2]))
    return sorted(fragments)


def keyword_score(
    job: dict,
    profile: str,
    preferred_keywords: list[str] | None = None,
) -> dict:
    skills, roles = profile_keywords(profile)
    title = _normalize(job.get("title") or "")
    fulltext = _normalize(
        " ".join(
            str(job.get(k, "")) for k in ("title", "company", "location", "description")
        )
    )
    preferred = [
        _normalize(str(k)) for k in (preferred_keywords or []) if str(k).strip()
    ]

    title_score = 0
    reason = "no target-role title match"
    fragments = _role_fragments(roles)
    if any(frag in title for frag in fragments):
        title_score = 50
        reason = "title matches a target role"

    skill_hits = [s for s in skills if _normalize(s) and _normalize(s) in fulltext]
    preferred_hits = [k for k in preferred if k and k in fulltext]
    hit_count = len(skill_hits) + len(preferred_hits)
    coverage_steps = [0, 10, 20, 28, 34, 40, 44, 47, 50]
    coverage = coverage_steps[min(hit_count, len(coverage_steps) - 1)]
    desc_len = len(_normalize(job.get("description") or ""))
    if title_score == 50 and desc_len > 80:
        coverage = max(coverage, 20)

    score = min(100, title_score + coverage)
    matched = skill_hits[:6] + preferred_hits[:4]
    reasons = (
        f"{reason}; skills/preferred matched ({hit_count}): "
        f"{', '.join(matched) if matched else 'none'}"
    )
    return {"score": score, "reasons": reasons[:300]}
