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

# High-signal domain terms typical of operations/admin/project-management
# roles. A job posting that hits several of these (plus a matching title)
# is a good fit; a posting that hits none is not.
DOMAIN_TERMS = [
    "operations",
    "operational",
    "project management",
    "project coordinator",
    "virtual assistant",
    "executive assistant",
    "administrative",
    "admin support",
    "scheduling",
    "calendar management",
    "email management",
    "follow up",
    "follow-up",
    "customer support",
    "customer service",
    "client management",
    "client relationship",
    "reporting",
    "data analytics",
    "coordination",
    "crm",
    "onboarding",
    "documentation",
    "data entry",
    "process improvement",
    "appointment",
    "inventory",
    "logistics",
    "vendor",
    "inbox management",
]

# Single domain words that often appear in a matching job *title*.
TITLE_STEMS = [
    "operations",
    "project",
    "program",
    "assistant",
    "coordinator",
    "administrative",
    "admin",
    "support",
    "management",
    "operations manager",
    "ops",
]


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


def keyword_score(job: dict, profile: str) -> dict:
    """Offline 0-100 fit score.

    Title match (0-50): the job title contains a target role phrase from
    the profile (or a strong role stem). Coverage (0-50): how many
    high-signal domain terms appear in the posting. A genuine
    operations/project/VA role with a real description clears 70.
    """
    _, roles = profile_keywords(profile)
    title = _normalize(job.get("title") or "")
    fulltext = _normalize(
        " ".join(
            str(job.get(k, "")) for k in ("title", "company", "location", "description")
        )
    )

    # --- Title match (0-50) ---
    title_score = 0
    reason = ""
    fragments = _role_fragments(roles)
    if any(frag in title for frag in fragments):
        title_score = 50
        reason = "title matches a target role"
    elif any(stem in title for stem in TITLE_STEMS):
        title_score = 25
        reason = "title looks related to target roles"

    # --- Domain-term coverage (0-50) ---
    hits = [term for term in DOMAIN_TERMS if term in fulltext]
    coverage_steps = [0, 2, 4, 6, 8, 10, 12, 15, 18, 22, 26, 30, 34, 38, 42, 46, 50]
    coverage = coverage_steps[min(len(hits), len(coverage_steps) - 1)]
    # Real postings describe duties; give a genuinely matching title a
    # small floor so short listings are not unfairly skipped.
    desc_len = len(_normalize(job.get("description") or ""))
    if title_score == 50 and desc_len > 80:
        coverage = max(coverage, 20)

    score = min(100, title_score + coverage)
    if title_score == 0 and len(hits) < 2:
        reasons = f"no target-role title match and {len(hits)} domain-term hits"
    else:
        matched_skills_text = ", ".join(hits[:6]) if hits else "none"
        reasons = f"{reason}; domain terms matched ({len(hits)}): {matched_skills_text}"
    return {"score": score, "reasons": reasons[:300]}
