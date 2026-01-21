from __future__ import annotations

from typing import Literal

from pydantic import field_validator

from pydantic import BaseModel, ConfigDict, Field


Seniority = Literal["intern", "junior", "mid", "senior", "lead", "manager", "director", "unknown"]
QuestionCategory = Literal["behavioral", "technical", "case", "situational", "mixed"]
QuestionDifficulty = Literal["easy", "medium", "hard"]
HintLevel = Literal["none", "light", "strong"]

UNCERTAINTY_DISCLAIMER = "This is probabilistic coaching, not truth."


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


class InterviewQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_text: str
    category: QuestionCategory = "mixed"
    difficulty: QuestionDifficulty = "medium"
    what_good_looks_like: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ScoreCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correctness: int = Field(ge=0, le=5)
    depth: int = Field(ge=0, le=5)
    structure: int = Field(ge=0, le=5)
    communication: int = Field(ge=0, le=5)
    role_relevance: int = Field(ge=0, le=5)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    suggested_rewrite: str | None = None
    followup_question: str = ""


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


class PossibleFallacy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    excerpt: str = ""
    short_explanation: str = ""
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("type")
    @classmethod
    def _type_must_be_known(cls, value: str) -> str:
        if value not in ARISTOTLE_FALLACIES:
            raise ValueError(f"Unknown fallacy type: {value}")
        return value


class FallacyHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hint_level: HintLevel = "none"
    coach_hint_text: str = ""
    possible_fallacies: list[PossibleFallacy] = Field(default_factory=list)
    more_info_text: str = ""
    suggested_rewrite: str | None = None

    @field_validator("more_info_text")
    @classmethod
    def _must_include_uncertainty_disclaimer(cls, value: str) -> str:
        if UNCERTAINTY_DISCLAIMER not in value:
            raise ValueError("more_info_text must include the uncertainty disclaimer")
        return value
