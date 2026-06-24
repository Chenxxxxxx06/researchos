"""Skill manifest schema and validation.

A skill is more than a prompt: it declares modules, a prompt template, a
workflow, explicit tool permissions, and a config schema. Tool permissions must
be drawn from a fixed allowlist; arbitrary code is never part of a manifest
(PHASE6 security).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .enums import SkillModule

# Tools a skill may *declare* it needs. The platform tool broker still enforces
# these at runtime; declaring a tool never grants execution by itself.
ALLOWED_TOOLS: tuple[str, ...] = (
    "paper.search",
    "library.list",
    "workspace.tree",
    "memory.read",
    "experiment.read",
)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class SkillManifest(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    version: str = "1.0.0"
    description: str = Field(default="", max_length=4000)
    author: str = Field(default="custom", max_length=120)
    category: str = Field(default="general", max_length=60)
    modules: list[SkillModule] = Field(default_factory=list)
    prompt_template: str = Field(default="", max_length=20_000)
    workflow: list[str] = Field(default_factory=list)
    tool_permissions: list[str] = Field(default_factory=list)
    config_schema: dict = Field(default_factory=dict)


def validate_manifest(manifest: SkillManifest) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid)."""

    errors: list[str] = []
    if not _SLUG_RE.match(manifest.slug):
        errors.append("slug must be lowercase letters, digits and dashes (2-80 chars).")
    if not _VERSION_RE.match(manifest.version):
        errors.append("version must be semver, e.g. 1.0.0.")
    if not manifest.modules:
        errors.append("at least one applicable module is required.")
    if not manifest.prompt_template.strip():
        errors.append("prompt_template must not be empty.")
    unknown = [t for t in manifest.tool_permissions if t not in ALLOWED_TOOLS]
    if unknown:
        errors.append(f"unknown tool permissions: {', '.join(unknown)}")
    return errors
