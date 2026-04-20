"""Structured-output schemas for Studio artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MindMapNode(BaseModel):
    id: str
    label: str
    children: list["MindMapNode"] = Field(default_factory=list)


class MindMapArtifactPayload(BaseModel):
    title: str
    root: MindMapNode


class FAQItem(BaseModel):
    question: str
    answer: str


class FAQArtifactPayload(BaseModel):
    title: str
    items: list[FAQItem]


class FlashcardItem(BaseModel):
    front: str
    back: str


class QuizItem(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list)
    answer: str
    explanation: str = ""


class FlashcardsArtifactPayload(BaseModel):
    title: str
    cards: list[FlashcardItem]
    quiz: list[QuizItem] = Field(default_factory=list)


class ReportArtifactPayload(BaseModel):
    title: str
    summary: str
    sections: list[dict[str, str]]
    key_takeaways: list[str] = Field(default_factory=list)


class DataTableArtifactPayload(BaseModel):
    title: str
    columns: list[str]
    rows: list[dict[str, Any]]


class InfographicSection(BaseModel):
    heading: str
    body: str
    stat: str = ""


class InfographicArtifactPayload(BaseModel):
    title: str
    subtitle: str = ""
    sections: list[InfographicSection]
    footer: str = ""
    svg: str = ""


class PodcastScriptArtifactPayload(BaseModel):
    title: str
    speakers: list[str]
    turns: list[dict[str, str]]
    estimated_duration_minutes: float
    transcript: str


class PPTOutlineArtifactPayload(BaseModel):
    title: str
    slides: list[dict[str, Any]]
    adapter_status: str = "placeholder"


class PlaceholderArtifactPayload(BaseModel):
    title: str
    adapter_status: str = "placeholder"
    message: str
    official_capability: str = ""


ARTIFACT_RESPONSE_MODELS = {
    "mind_map": MindMapArtifactPayload,
    "faq": FAQArtifactPayload,
    "flashcards": FlashcardsArtifactPayload,
    "quiz": FlashcardsArtifactPayload,
    "report": ReportArtifactPayload,
    "study_guide": ReportArtifactPayload,
    "data_table": DataTableArtifactPayload,
    "podcast_script": PodcastScriptArtifactPayload,
    "ppt_outline": PPTOutlineArtifactPayload,
    "video_overview": PlaceholderArtifactPayload,
    "infographic": InfographicArtifactPayload,
}


def artifact_payload_to_markdown(artifact_type: str, payload: dict[str, Any]) -> str:
    title = payload.get("title", artifact_type)
    if artifact_type == "faq":
        body = "\n\n".join(
            f"### {item.get('question', '')}\n\n{item.get('answer', '')}"
            for item in payload.get("items", [])
        )
    elif artifact_type in {"flashcards", "quiz"}:
        cards = "\n\n".join(
            f"### {card.get('front', '')}\n\n{card.get('back', '')}"
            for card in payload.get("cards", [])
        )
        quiz_lines = []
        for item in payload.get("quiz", []):
            options = "\n".join(f"- {option}" for option in item.get("options", []))
            quiz_lines.append(
                f"### {item.get('question', '')}\n\n{options}\n\n"
                f"**Answer:** {item.get('answer', '')}\n\n{item.get('explanation', '')}".strip()
            )
        quiz = "\n\n".join(quiz_lines)
        body = f"{cards}\n\n## Quiz\n\n{quiz}".strip() if quiz else cards
    elif artifact_type in {"report", "study_guide"}:
        sections = "\n\n".join(
            f"## {section.get('heading', '')}\n\n{section.get('body', '')}"
            for section in payload.get("sections", [])
        )
        takeaways = "\n".join(f"- {item}" for item in payload.get("key_takeaways", []))
        body = f"{payload.get('summary', '')}\n\n{sections}\n\n{takeaways}".strip()
    elif artifact_type == "data_table":
        columns = payload.get("columns", [])
        rows = payload.get("rows", [])
        header = "| " + " | ".join(columns) + " |"
        sep = "| " + " | ".join(["---"] * len(columns)) + " |"
        lines = [header, sep]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
        body = "\n".join(lines)
    elif artifact_type == "infographic":
        sections = "\n\n".join(
            f"## {section.get('heading', '')}\n\n"
            f"{section.get('stat', '')}\n\n"
            f"{section.get('body', '')}".strip()
            for section in payload.get("sections", [])
        )
        body = f"{payload.get('subtitle', '')}\n\n{sections}\n\n{payload.get('footer', '')}".strip()
    elif artifact_type == "mind_map":
        def render_node(node: dict[str, Any], depth: int = 0) -> list[str]:
            lines = ["  " * depth + f"- {node.get('label', '')}"]
            for child in node.get("children", []):
                lines.extend(render_node(child, depth + 1))
            return lines

        body = "\n".join(render_node(payload.get("root", {})))
    elif artifact_type == "podcast_script":
        body = payload.get("transcript", "")
    else:
        if payload.get("adapter_status") == "placeholder":
            body = payload.get("message", "")
        else:
            body = "\n".join(f"- {slide.get('title', '')}" for slide in payload.get("slides", []))
    return f"# {title}\n\n{body}".strip() + "\n"
