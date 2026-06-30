from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

TEST_FILE = Path(__file__).resolve()
APP_DIR = TEST_FILE.parent
REPO_ROOT = TEST_FILE.parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services import reporting as report_module  # noqa: E402
from backend.app.services.reporting import generator as report_generator_module  # noqa: E402


COMPLETE_QUERY = (
    "On 2026-02-14 at 09:20 a user email account received a phishing link "
    "https://secure-bank-example.com/login from IP 203.0.113.45. Proxy log "
    "and email header evidence are available. The affected online banking account "
    "had an unauthorized transaction and suspected fraud loss."
)


def _fake_rag_result() -> SimpleNamespace:
    vector_result = SimpleNamespace(
        metadata={
            "name": "Phishing",
            "node_label": "Technique",
            "attack_id": "T1566",
            "stix_id": "attack-pattern--phishing",
        },
        document="Phishing is a MITRE ATT&CK technique involving deceptive messages.",
        score=0.97,
        stix_id="attack-pattern--phishing",
    )
    return SimpleNamespace(vector_results=[vector_result], graph_results=[])


class _InvalidFactPackLLM:
    def invoke(self, _messages: object) -> dict[str, object]:
        return {"facts": [], "evidence_registry": [], "completeness_percentage": 60}


def _load_rag_service_report_generator_shim(
    monkeypatch: pytest.MonkeyPatch,
) -> types.ModuleType:
    module_name = "RAG.GraphRAG.pipeline.report_generator"
    module_path = APP_DIR / "RAG" / "GraphRAG" / "pipeline" / "report_generator.py"

    app_service_modules = [
        name
        for name in sys.modules
        if name == "app.services" or name.startswith("app.services.")
    ]
    for name in app_service_modules:
        monkeypatch.delitem(sys.modules, name, raising=False)

    local_app = types.ModuleType("app")
    local_app.__path__ = [str(APP_DIR)]
    monkeypatch.setitem(sys.modules, "app", local_app)

    package_paths = {
        "RAG": APP_DIR / "RAG",
        "RAG.GraphRAG": APP_DIR / "RAG" / "GraphRAG",
        "RAG.GraphRAG.pipeline": APP_DIR / "RAG" / "GraphRAG" / "pipeline",
    }
    for package_name, package_path in package_paths.items():
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_path)]
        monkeypatch.setitem(sys.modules, package_name, package)

    config = types.ModuleType("RAG.GraphRAG.config")
    config.ANTHROPIC_API_KEY = ""
    config.LLM_MAX_TOKENS = 1024
    config.LLM_MODEL = "test-model"
    monkeypatch.setitem(sys.modules, "RAG.GraphRAG.config", config)

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def generator(monkeypatch: pytest.MonkeyPatch) -> report_module.ReportGenerator:
    monkeypatch.setattr(report_generator_module, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(report_generator_module, "ChatAnthropic", None)
    return report_module.ReportGenerator()


def test_rag_service_report_generator_shim_handles_app_package_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shim = _load_rag_service_report_generator_shim(monkeypatch)

    assert shim.ReportGenerator is report_module.ReportGenerator
    assert shim.CyberCaseReport is report_module.CyberCaseReport
    assert shim.LEGAL_DISCLAIMER == report_module.LEGAL_DISCLAIMER


def test_completeness_calculation_is_transparent(
    generator: report_module.ReportGenerator,
) -> None:
    pack = generator.preview_case_fact_pack(COMPLETE_QUERY)
    assert pack.completeness_percentage >= 80
    assert pack.completeness.status == "Sufficient for preliminary report"
    assert not pack.missing_information


def test_legal_mode_disabled_and_enabled(
    generator: report_module.ReportGenerator,
) -> None:
    report = generator.generate(
        COMPLETE_QUERY,
        context="MITRE context",
        rag_result=_fake_rag_result(),
        legal=False,
        force_generate=True,
    )
    assert report.legal_assessments == []

    legal_report = generator.generate(
        COMPLETE_QUERY,
        context="MITRE context",
        rag_result=_fake_rag_result(),
        legal=True,
        force_generate=True,
    )
    assert legal_report.legal_assessments
    assert (
        report_module.LEGAL_DISCLAIMER
        in legal_report.legal_assessments[0].disclaimer
    )


def test_invalid_llm_fact_pack_falls_back_to_deterministic_pack(
    generator: report_module.ReportGenerator,
) -> None:
    generator.fact_pack_llm = _InvalidFactPackLLM()

    report = generator.generate(
        COMPLETE_QUERY,
        context="MITRE context",
        rag_result=_fake_rag_result(),
        force_generate=True,
    )

    assert report.case_fact_pack.facts
    assert (
        "Structured LLM case fact extraction failed validation; "
        "deterministic evidence extraction was used instead."
        in report.limitations_and_disclaimers
    )


def test_report_validation_rejects_unknown_evidence_id(
    generator: report_module.ReportGenerator,
) -> None:
    report = generator.generate(
        COMPLETE_QUERY,
        context="MITRE context",
        rag_result=_fake_rag_result(),
        force_generate=True,
    )
    report.evidence_and_indicators_table[0].evidence_ids = ["E-999"]

    with pytest.raises(ValueError, match="unknown evidence"):
        generator.validate_report(
            report,
            allowed_techniques=generator.build_evidence_packet(
                COMPLETE_QUERY, "MITRE context", _fake_rag_result()
            ).ttp_candidates,
            legal=False,
        )


def test_mitre_validation_rejects_unknown_technique(
    generator: report_module.ReportGenerator,
) -> None:
    report = generator.generate(
        COMPLETE_QUERY,
        context="MITRE context",
        rag_result=_fake_rag_result(),
        force_generate=True,
    )
    assert report.mitre_attack_assessment
    report.mitre_attack_assessment[0].technique_id = "T9999"

    with pytest.raises(ValueError, match="not present in retrieved MITRE data"):
        generator.validate_report(
            report,
            allowed_techniques=generator.build_evidence_packet(
                COMPLETE_QUERY, "MITRE context", _fake_rag_result()
            ).ttp_candidates,
            legal=False,
        )


def test_incomplete_report_is_labeled(
    generator: report_module.ReportGenerator,
) -> None:
    report = generator.generate(
        "Suspicious activity reported.",
        context="MITRE context",
        rag_result=_fake_rag_result(),
        force_generate=True,
    )
    assert report.title == report_module.INCOMPLETE_TITLE
    assert (
        "Generated at user request despite incomplete case information."
        in report.limitations_and_disclaimers
    )