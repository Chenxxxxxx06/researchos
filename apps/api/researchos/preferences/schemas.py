"""Preference DTOs and validation."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from researchos.figures.presets import PRESETS

Theme = Literal["system", "light", "dark"]
Language = Literal["en", "zh-CN"]

MAX_EXTRA_BYTES = 8192

ExtraValue = str | int | float | bool


class PreferencesPayload(BaseModel):
    """One scope's stored row (PUT body and scope echo). ``None`` = no opinion."""

    theme: Theme | None = None
    language: Language | None = None
    figure_style_slug: str | None = None
    # Flat forward-compatible bucket for frontend-only settings.
    extra: dict[str, ExtraValue] = Field(default_factory=dict)

    @field_validator("figure_style_slug")
    @classmethod
    def _known_slug(cls, value: str | None) -> str | None:
        if value is not None and value not in PRESETS:
            raise ValueError("unknown figure style preset")
        return value

    @field_validator("extra")
    @classmethod
    def _extra_within_cap(cls, value: dict[str, ExtraValue]) -> dict[str, ExtraValue]:
        if len(json.dumps(value)) > MAX_EXTRA_BYTES:
            raise ValueError("extra exceeds the 8 KB cap")
        return value


class EffectivePreferences(BaseModel):
    theme: Theme
    language: Language
    figure_style_slug: str
    extra: dict[str, ExtraValue]


class UserPreferencesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    effective: EffectivePreferences
    # "global" is a Python keyword; serialized under the contract name.
    global_: PreferencesPayload | None = Field(default=None, serialization_alias="global")


class ProjectPreferencesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    effective: EffectivePreferences
    project: PreferencesPayload | None = None
    global_: PreferencesPayload | None = Field(default=None, serialization_alias="global")
