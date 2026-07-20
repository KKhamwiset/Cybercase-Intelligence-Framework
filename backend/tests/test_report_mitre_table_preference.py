from __future__ import annotations

import pytest

from app.services.reporting.generator import ReportGenerator


CASE_QUERY = (
    "On 2026-07-01 at 10:00 UTC, a corporate email account received a phishing "
    "message and a user entered credentials into https://login.example.com. "
    "Proxy log evidence shows the affected account and suspected credential theft impact."
)

EXPECTED_HEADINGS = [
    "## 1. Case Summary",
    "## 2. Found Indicators",
    "## 3. MITRE ATT&CK Mapping",
    "## 4. Mapping Rationale",
    "## 5. Evidence That Should Be Checked",
    "## 6. Preliminary Recommendations",
    "## 7. System Limitations",
]


def _raw_rag_result() -> dict:
    return {
        "vector_results": [
            {
                "metadata": {
                    "name": "Command and Scripting Interpreter",
                    "entity_type": "AttackPattern",
                    "node_label": "AttackPattern",
                    "attack_id": "T1059",
                    "stix_id": "attack-pattern--t1059",
                },
                "document": "Adversaries may abuse command and scripting interpreters.",
                "score": 0.72,
                "stix_id": "attack-pattern--t1059",
            }
        ],
        "graph_results": [],
    }


def _mitre_table_row(
    technique_id: str = "T1566",
    name: str = "Phishing",
    entity_type: str = "AttackPattern",
    score: float = 0.98,
    relevance: str = "cited_in_answer",
) -> dict:
    return {
        "technique_id": technique_id,
        "name": name,
        "entity_type": entity_type,
        "score": score,
        "source": "graph",
        "relevance": relevance,
        "description": f"MITRE description for {technique_id} {name}.",
    }


def _report():
    return ReportGenerator().generate(
        CASE_QUERY,
        "RAG context mentions both command execution and phishing.",
        rag_result=_raw_rag_result(),
        mitre_table=[_mitre_table_row()],
        force_generate=True,
    )


def _technique_ids(report) -> list[str]:
    return [item.technique_id for item in report.mitre_attack_assessment]


def _section(markdown: str, heading: str) -> str:
    start = markdown.index(heading) + len(heading)
    next_heading = markdown.find("\n## ", start)
    if next_heading == -1:
        return markdown[start:].strip()
    return markdown[start:next_heading].strip()


def test_markdown_uses_required_seven_section_structure_without_skipped_numbering() -> None:
    markdown = ReportGenerator().render_report_markdown(_report())

    assert markdown.startswith("# CyberCase Investigation Report\n\n## 1. Case Summary")
    assert [line for line in markdown.splitlines() if line.startswith("## ")] == EXPECTED_HEADINGS


def test_non_legal_builder_title_uses_cyber_incident_wording() -> None:
    report = _report()

    assert report.title == "Evidence-Grounded Preliminary Cyber Incident Report"
    assert "Legal" not in report.title


def test_markdown_renders_empty_list_placeholders() -> None:
    report = _report()
    report.evidence_and_indicators_table = []
    report.evidence_still_required = []
    report.limitations_and_disclaimers = []

    markdown = ReportGenerator().render_report_markdown(report)

    assert (
        "No explicit indicators were extracted from the submitted case information."
        in markdown
    )
    assert (
        "No additional required evidence was identified for this preliminary report. "
        "Analyst review is still recommended."
        in markdown
    )
    assert (
        "This report is AI-assisted preliminary investigation support and requires analyst review."
        in markdown
    )


def test_mitre_mapping_and_rationale_render_as_separate_sections() -> None:
    markdown = ReportGenerator().render_report_markdown(_report())

    mapping_section = _section(markdown, "## 3. MITRE ATT&CK Mapping")
    rationale_section = _section(markdown, "## 4. Mapping Rationale")

    assert "T1566 - Phishing; status: inferred; evidence:" in mapping_section
    assert "filtered MITRE table from the RAG service returned" not in mapping_section
    assert "filtered MITRE table from the RAG service returned" in rationale_section
    assert "Evidence IDs:" in rationale_section
    assert "Analyst verification:" in rationale_section


def test_mitre_table_technique_wins_over_raw_rag_candidate() -> None:
    report = _report()

    assert _technique_ids(report) == ["T1566"]
    assert "T1059" not in _technique_ids(report)
    assert (
        "filtered MITRE table from the RAG service returned T1566 Phishing"
        in report.mitre_attack_assessment[0].justification
    )
    assert "mitre_table:cited_in_answer" in {
        item.source for item in ReportGenerator()._entities_from_mitre_table([_mitre_table_row()])
    }


@pytest.mark.parametrize("mitre_table", [None, []])
def test_missing_or_empty_mitre_table_falls_back_to_raw_rag_result(mitre_table) -> None:
    report = ReportGenerator().generate(
        CASE_QUERY,
        "RAG context mentions command execution.",
        rag_result=_raw_rag_result(),
        mitre_table=mitre_table,
        force_generate=True,
    )

    assert _technique_ids(report) == ["T1059"]
    assert "Hybrid retrieval returned" in report.mitre_attack_assessment[0].justification


def test_mitre_table_cited_rows_are_preferred_before_retrieved_only_rows() -> None:
    entities = ReportGenerator()._entities_from_mitre_table(
        [
            _mitre_table_row("T1059", "Command and Scripting Interpreter", score=0.99, relevance="retrieved_only"),
            _mitre_table_row("T1566", "Phishing", score=0.40, relevance="cited_in_answer"),
        ]
    )

    assert [item.attack_id for item in entities] == ["T1566", "T1059"]


def test_invalid_mitre_table_rows_are_excluded_without_raw_rag_fallback() -> None:
    report = ReportGenerator().generate(
        CASE_QUERY,
        "RAG context mentions command execution.",
        rag_result=_raw_rag_result(),
        mitre_table=[
            _mitre_table_row("TA0001", "Initial Access", entity_type="Technique"),
            _mitre_table_row("T1566", "Phishing", entity_type="Malware"),
        ],
        force_generate=True,
    )

    assert _technique_ids(report) == []


def test_mitre_table_accepts_technique_subtechnique_and_attack_pattern_rows_only() -> None:
    entities = ReportGenerator()._entities_from_mitre_table(
        [
            _mitre_table_row("T1566", "Phishing", entity_type="Technique"),
            _mitre_table_row("T1566.001", "Spearphishing Attachment", entity_type="SubTechnique"),
            _mitre_table_row("T1059", "Command and Scripting Interpreter", entity_type="AttackPattern"),
            _mitre_table_row("T1105", "Ingress Tool Transfer", entity_type="Tool"),
            _mitre_table_row("TA0001", "Initial Access", entity_type="Technique"),
        ]
    )

    assert [item.attack_id for item in entities] == ["T1566", "T1566.001", "T1059"]


def test_mitre_table_candidates_are_capped_to_six_after_cited_first_sorting() -> None:
    entities = ReportGenerator()._entities_from_mitre_table(
        [
            _mitre_table_row("T1001", "Cited Low", score=0.40, relevance="cited_in_answer"),
            _mitre_table_row("T1002", "Cited High", score=0.90, relevance="cited_in_answer"),
            _mitre_table_row("T1003", "Cited Mid", score=0.70, relevance="cited_in_answer"),
            _mitre_table_row("T1004", "Cited Lowest", score=0.10, relevance="cited_in_answer"),
            _mitre_table_row("T2001", "Retrieved High", score=0.99, relevance="retrieved_only"),
            _mitre_table_row("T2002", "Retrieved Mid", score=0.80, relevance="retrieved_only"),
            _mitre_table_row("T2003", "Retrieved Low", score=0.50, relevance="retrieved_only"),
        ]
    )

    assert [item.attack_id for item in entities] == [
        "T1002",
        "T1003",
        "T1001",
        "T1004",
        "T2001",
        "T2002",
    ]
