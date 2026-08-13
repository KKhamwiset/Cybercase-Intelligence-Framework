import json
import unittest

from app.services.chat.case_state_retrieval import (
    project_case_state_to_retrieval_query,
)


_SOURCE_ID = "11111111-1111-1111-1111-111111111111"


def _complete_case_state() -> dict[str, object]:
    return {
        "version": "baseline_extraction_v1",
        "mode": "single_pass_llm",
        "status": "candidate",
        "case_summary": "PowerShell executed an encoded command on finance-host-1.",
        "entities": [
            {
                "entity_id": "host-1",
                "name": "finance-host-1",
                "entity_type": "hostname",
                "reported_role": "affected host",
                "confidence": "high",
                "source_message_ids": [_SOURCE_ID],
            },
            {
                "entity_id": "actor-1",
                "name": "Alice",
                "entity_type": "person",
                "reported_role": "reported actor",
                "confidence": "medium",
                "source_message_ids": [_SOURCE_ID],
            },
        ],
        "relationships": [
            {
                "relationship_id": "rel-1",
                "subject_entity_id": "actor-1",
                "predicate": "executed_command_on",
                "object_entity_id": "host-1",
                "statement": "Alice reportedly executed the command on the host.",
                "status": "reported",
                "confidence": "medium",
                "source_message_ids": [_SOURCE_ID],
            }
        ],
        "evidence": [
            {
                "evidence_id": "artifact-1",
                "title": "PowerShell event",
                "description": "An encoded PowerShell command was reported.",
                "artifact_type": "event_log",
                "status": "reported",
                "confidence": "high",
                "source_type": "user_reported",
                "source_message_ids": [_SOURCE_ID],
            }
        ],
        "timeline": [
            {
                "event_id": "event-1",
                "timestamp": "2026-08-13T01:02:03Z",
                "timestamp_text": "2026-08-13 01:02:03 UTC",
                "event": "Encoded PowerShell execution was reported.",
                "actors": ["actor-1"],
                "evidence_ids": ["artifact-1"],
                "status": "reported",
                "confidence": "high",
                "source_message_ids": [_SOURCE_ID],
            }
        ],
        "missing_information": [
            {
                "missing_id": "missing-1",
                "description": "Command origin remains unresolved.",
                "importance": "material",
                "source_message_ids": [_SOURCE_ID],
            }
        ],
        "warnings": ["provider audit metadata is intentionally not retrieval data"],
    }


def _payload_from_query(query: str) -> dict[str, object]:
    serialized = query.split("<case_state_retrieval_json>\n", 1)[1].split(
        "\n</case_state_retrieval_json>",
        1,
    )[0]
    payload = json.loads(serialized)
    assert isinstance(payload, dict)
    return payload


class CaseStateRetrievalProjectionTests(unittest.TestCase):
    def test_projection_is_deterministic_complete_and_metadata_free(self) -> None:
        state = _complete_case_state()

        first = project_case_state_to_retrieval_query(state)
        second = project_case_state_to_retrieval_query(state)

        self.assertEqual(first, second)
        payload = _payload_from_query(first)
        self.assertEqual(
            set(payload),
            {
                "case_summary",
                "entities",
                "relationships",
                "evidence",
                "timeline",
                "missing_information",
            },
        )
        self.assertIn("PowerShell", payload["case_summary"])
        self.assertEqual(payload["entities"][0]["confidence"], "high")
        self.assertEqual(payload["relationships"][0]["status"], "reported")
        self.assertEqual(payload["evidence"][0]["confidence"], "high")
        self.assertEqual(payload["timeline"][0]["status"], "reported")
        self.assertNotIn(_SOURCE_ID, first)
        self.assertNotIn("single_pass_llm", first)
        self.assertNotIn("candidate", first)
        self.assertNotIn("provider audit metadata", first)

    def test_projection_defensively_rejects_non_baseline_state(self) -> None:
        invalid = _complete_case_state()
        invalid["analysis_metadata"] = {"answer": "model output"}

        with self.assertRaises(ValueError):
            project_case_state_to_retrieval_query(invalid)


if __name__ == "__main__":
    unittest.main()
