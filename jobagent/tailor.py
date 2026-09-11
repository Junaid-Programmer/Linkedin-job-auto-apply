"""Tailor the candidate's resume for a specific job and prepare an
application package the user can review before submitting manually.
"""

from __future__ import annotations

import re
from pathlib import Path

from jobagent.llm import LLMClient
from jobagent.scoring import profile_keywords

TAILOR_SYSTEM = (
    "You are a professional resume writer. You take a candidate's base resume "
    "and a specific job posting, and produce a tailored version that maximizes "
    "keyword and requirement alignment WITHOUT fabricating experience, skills, "
    "or credentials. Rephrase and reorder honestly; never invent things."
)

APPLICATION_NOTE_SYSTEM = (
    "You write short, professional cover notes for job applications. Be "
    "specific, enthusiastic, and concise (under 200 words). Never invent "
    "achievements or credentials that are not in the resume."
)


def build_tailor_prompt(job: dict, resume: str, profile: str) -> str:
    return f"""CANDIDATE PROFILE
{profile}

BASE RESUME
{resume}

JOB POSTING
Title: {job.get('title')}
Company: {job.get('company')}
Location: {job.get('location')}

DESCRIPTION:
{job.get('description', '(no description available)')}

Produce the tailored resume as clean Markdown, starting with a header line
containing the candidate's name and contact placeholders. Highlight experience
that matches this job, reorder skills to front-load the ones the job asks for,
and keep every fact faithful to the base resume."""


def build_application_note_prompt(job: dict, resume: str) -> str:
    return f"""Resume:
{resume}

Job:
Title: {job.get('title')}
Company: {job.get('company')}
Location: {job.get('location')}
Description: {job.get('description', '(no description available)')}

Write a short cover note for this specific application, mentioning 2-3
specific relevant strengths and why you are a good fit."""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "job"


def prepare_application_package(
    llm: LLMClient, job: dict, resume: str, profile: str, output_dir: str
) -> str:
    """Tailor resume + write application note, save both to disk.

    Returns the folder path of the generated package.
    """
    tailored = llm.chat(
        TAILOR_SYSTEM,
        build_tailor_prompt(job, resume, profile),
        temperature=0.3,
        max_tokens=2500,
    ).strip()
    note = llm.chat(
        APPLICATION_NOTE_SYSTEM,
        build_application_note_prompt(job, resume),
        temperature=0.4,
        max_tokens=400,
    ).strip()

    folder = Path(output_dir) / f"{slugify(job.get('company') + '-' + job.get('title'))}-{job.get('id')}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "resume_tailored.md").write_text(tailored + "\n", encoding="utf-8")
    (folder / "application_note.md").write_text(note + "\n", encoding="utf-8")
    (folder / "job.txt").write_text(
        f"{job.get('title')} @ {job.get('company')}\n{job.get('url', '')}\n\n"
        f"{job.get('description', '')}",
        encoding="utf-8",
    )
    return str(folder)


def prepare_application_package_fallback(
    job: dict, resume: str, profile: str, output_dir: str
) -> str:
    """Offline fallback (no LLM key): keep the base resume, prepend a
    targeted summary listing the skills that match this job, and write a
    simple application note the user can personalize."""
    skills, _ = profile_keywords(profile)
    text = " ".join(
        str(job.get(k, "")) for k in ("title", "company", "location", "description")
    ).lower()
    matched = [s for s in skills if s.lower() in text]

    title = job.get("title", "the role")
    company = job.get("company", "your company")
    summary = (
        f"# Tailored resume - {title} at {company}\n\n"
        "## Application summary\n"
        f"Applying for {title} at {company}. "
        f"Skills that match this role: {', '.join(matched) if matched else 'see resume'}. "
        "Review the tailored sections below before submitting.\n\n"
        f"---\n\n{resume}\n"
    )
    strengths = ", ".join(matched[:3]) if matched else "the skills in my resume"
    note = (
        f"Dear Hiring Manager,\n\n"
        f"I'm applying for the {title} position at {company}. "
        f"My background in {strengths} matches the requirements of this role. "
        f"Please see my resume for relevant experience.\n\n"
        f"I'd welcome the opportunity to discuss how I can contribute to your team.\n\n"
        f"Best regards,\n[Your name]"
    )

    folder = Path(output_dir) / f"{slugify(company + '-' + title)}-{job.get('id')}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "resume_tailored.md").write_text(summary, encoding="utf-8")
    (folder / "application_note.md").write_text(note + "\n", encoding="utf-8")
    (folder / "job.txt").write_text(
        f"{title} @ {company}\n{job.get('url', '')}\n\n{job.get('description', '')}",
        encoding="utf-8",
    )
    return str(folder)
