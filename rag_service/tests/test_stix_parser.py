"""
Unit Tests for STIX 2.1 Parser
===============================
Validates tombstoning, version overrides, relationship filtering,
latest-file folder parsing defaults, and T1527 regression logic.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add app directory to sys.path
_APP_DIR = Path(__file__).resolve().parent.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import pytest
from RAG.GraphRAG.ingestion.stix_parser import StixParser


def make_mock_bundle(objects):
    return {
        "type": "bundle",
        "id": "bundle--mock",
        "spec_version": "2.1",
        "objects": objects
    }


def test_revoked_tombstone_exclusions():
    """Parser test: older file has active object, newer file marks it revoked -> final entities exclude it."""
    parser = StixParser()

    obj_active = {
        "type": "attack-pattern",
        "id": "attack-pattern--1",
        "name": "Technique 1",
        "description": "An active technique",
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1000"}
        ]
    }
    obj_revoked = {
        "type": "attack-pattern",
        "id": "attack-pattern--1",
        "revoked": True,
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1000"}
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "enterprise-attack-1.0.json"
        file2 = Path(tmpdir) / "enterprise-attack-2.0.json"

        with open(file1, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_active]), f)

        with open(file2, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_revoked]), f)

        # Parse in chronological order (1.0 then 2.0)
        parser.parse_file(file1, finalize=False)
        parser.parse_file(file2, finalize=False)
        parser.finalize_parsing()

    assert not any(e.stix_id == "attack-pattern--1" for e in parser.entities)
    assert "attack-pattern--1" not in parser._id_to_name


def test_newer_version_overrides():
    """Parser test: older active object, newer active object with same STIX ID -> newer active wins."""
    parser = StixParser()

    obj_old = {
        "type": "attack-pattern",
        "id": "attack-pattern--1",
        "name": "Technique 1 Old",
        "description": "Old description",
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1000"}
        ]
    }
    obj_new = {
        "type": "attack-pattern",
        "id": "attack-pattern--1",
        "name": "Technique 1 New",
        "description": "New description",
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1000"}
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "enterprise-attack-1.0.json"
        file2 = Path(tmpdir) / "enterprise-attack-2.0.json"

        with open(file1, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_old]), f)

        with open(file2, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_new]), f)

        parser.parse_file(file1, finalize=False)
        parser.parse_file(file2, finalize=False)
        parser.finalize_parsing()

    entities = [e for e in parser.entities if e.stix_id == "attack-pattern--1"]
    assert len(entities) == 1
    assert entities[0].name == "Technique 1 New"
    assert entities[0].description == "New description"


def test_relationships_referencing_tombstones_removed():
    """Parser test: relationships referencing tombstoned objects are removed."""
    parser = StixParser()

    obj_tech = {
        "type": "attack-pattern",
        "id": "attack-pattern--1",
        "name": "Technique 1",
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1000"}
        ]
    }
    obj_soft = {
        "type": "tool",
        "id": "tool--1",
        "name": "Software 1",
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "S0001"}
        ]
    }
    obj_rel = {
        "type": "relationship",
        "id": "relationship--1",
        "relationship_type": "uses",
        "source_ref": "tool--1",
        "target_ref": "attack-pattern--1",
        "description": "Software uses technique"
    }

    # In newer version, the software remains active, but the technique is revoked
    obj_tech_revoked = {
        "type": "attack-pattern",
        "id": "attack-pattern--1",
        "revoked": True,
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1000"}
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "enterprise-attack-1.0.json"
        file2 = Path(tmpdir) / "enterprise-attack-2.0.json"

        with open(file1, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_tech, obj_soft, obj_rel]), f)

        with open(file2, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_tech_revoked]), f)

        parser.parse_file(file1, finalize=False)
        parser.parse_file(file2, finalize=False)
        parser.finalize_parsing()

    # The technique should be removed, the software should remain
    assert not any(e.stix_id == "attack-pattern--1" for e in parser.entities)
    assert any(e.stix_id == "tool--1" for e in parser.entities)

    # The relationship should be removed because target_ref is tombstoned
    assert not any(r.stix_id == "relationship--1" for r in parser.relationships)


def test_default_folder_parsing_prefers_main_file(monkeypatch):
    """Parser test: default folder parsing prefers enterprise-attack.json when present."""
    # Mock INGEST_HISTORICAL to be False
    import RAG.GraphRAG.config
    monkeypatch.setattr(RAG.GraphRAG.config, "INGEST_HISTORICAL", False)

    obj_hist = {
        "type": "attack-pattern",
        "id": "attack-pattern--hist",
        "name": "Historical Technique",
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1001"}
        ]
    }
    obj_latest = {
        "type": "attack-pattern",
        "id": "attack-pattern--latest",
        "name": "Latest Technique",
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1002"}
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir) / "enterprise-attack"
        folder.mkdir()

        file_hist = folder / "enterprise-attack-7.0.json"
        file_latest = folder / "enterprise-attack.json"

        with open(file_hist, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_hist]), f)

        with open(file_latest, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_latest]), f)

        # Parse folder with default settings (should only parse enterprise-attack.json)
        parser = StixParser()
        parser.parse_folder(folder, domain="enterprise")

        assert any(e.stix_id == "attack-pattern--latest" for e in parser.entities)
        assert not any(e.stix_id == "attack-pattern--hist" for e in parser.entities)

        # Parse folder with INGEST_HISTORICAL = True
        monkeypatch.setattr(RAG.GraphRAG.config, "INGEST_HISTORICAL", True)
        parser_hist = StixParser()
        parser_hist.parse_folder(folder, domain="enterprise")

        assert any(e.stix_id == "attack-pattern--latest" for e in parser_hist.entities)
        assert any(e.stix_id == "attack-pattern--hist" for e in parser_hist.entities)


def test_regression_t1527():
    """Regression test: T1527 is not present in parsed entities."""
    parser = StixParser()

    obj_t1527_active = {
        "type": "attack-pattern",
        "id": "attack-pattern--t1527",
        "name": "Application Access Token",
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1527"}
        ]
    }
    obj_t1527_revoked = {
        "type": "attack-pattern",
        "id": "attack-pattern--t1527",
        "revoked": True,
        "external_references": [
            {"source_name": "mitre-attack", "external_id": "T1527"}
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "enterprise-attack-7.0.json"
        file2 = Path(tmpdir) / "enterprise-attack.json"

        with open(file1, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_t1527_active]), f)

        with open(file2, "w", encoding="utf-8") as f:
            json.dump(make_mock_bundle([obj_t1527_revoked]), f)

        parser.parse_file(file1, finalize=False)
        parser.parse_file(file2, finalize=False)
        parser.finalize_parsing()

    assert not any(e.attack_id == "T1527" for e in parser.entities)
