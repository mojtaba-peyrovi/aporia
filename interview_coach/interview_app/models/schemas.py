from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Seniority = Literal["intern", "junior", "mid", "senior", "lead", "manager", "director", "unknown"]


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    target_role: str | None = None
    seniority: Seniority = "unknown"
    industries: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    key_projects: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    gaps_or_risks: list[str] = Field(default_factory=list)
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)


ARISTOTLE_FALLACIES: tuple[str, ...] = (
    "equivocation",
    "amphiboly",
    "composition",
    "division",
    "accent",
    "form_of_expression",
    "accident",
    "converse_accident",
    "false_cause",
    "begging_the_question",
    "ignorance_of_refutation",
    "affirming_the_consequent",
    "many_questions",
)

ARISTOTLE_FALLACY_EXPLANATIONS: dict[str, str] = {
    "equivocation": "A key word/phrase shifts meaning mid-argument.",
    "amphiboly": "Ambiguity from grammar/syntax drives a mistaken conclusion.",
    "composition": "Attributes of parts are assumed for the whole.",
    "division": "Attributes of the whole are assumed for the parts.",
    "accent": "Meaning changes due to emphasis, quoting, or formatting.",
    "form_of_expression": "Misleading inference from a similarity in wording/grammar.",
    "accident": "A general rule is misapplied to an exceptional case.",
    "converse_accident": "A rule is inferred from an exceptional case.",
    "false_cause": "Causation is asserted without sufficient basis.",
    "begging_the_question": "The conclusion is assumed in the premises (circularity).",
    "ignorance_of_refutation": "A response misses the point being argued.",
    "affirming_the_consequent": "If P then Q; Q; therefore P.",
    "many_questions": "A loaded question presupposes disputed claims.",
}

