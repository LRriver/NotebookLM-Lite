from __future__ import annotations

from backend.infrastructure.ppt_adapter import AIPPTAdapter, AIPPTSourceBundle


def test_aippt_adapter_exposes_future_integration_contract():
    bundle = AIPPTSourceBundle(
        title="Notebook deck",
        source_text="Source material for slides.",
        source_ids=["src_1"],
        requirements="Use concise titles.",
    )

    plan = AIPPTAdapter("/Users/lzj/proj/notebook/OpenNotebookLM-AIPPT").integration_plan(bundle)

    assert plan.adapter_status == "coming_soon"
    assert "OpenNotebookLM-AIPPT" in plan.aippt_project_path
    assert "src.generator.PPTGenerator" in plan.expected_modules
    assert plan.request_shape["source_ids"] == ["src_1"]
    assert plan.request_shape["requirements"] == "Use concise titles."
