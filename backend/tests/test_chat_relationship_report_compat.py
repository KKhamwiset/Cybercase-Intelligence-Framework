import unittest
from uuid import uuid4

from app.models.chat import ChatMessage, ChatThread
from app.services.chat.report_service import build_current_report_snapshot


class ChatRelationshipReportCompatibilityTests(unittest.TestCase):
    def test_legacy_v1_prompt_extraction_without_relationships_remains_ready(
        self,
    ) -> None:
        thread = _thread_with_extraction(
            prompt_version="baseline_extraction_prompt_v1",
            include_relationship=False,
        )

        snapshot = build_current_report_snapshot(thread)

        self.assertEqual(snapshot.extraction.relationships, [])
        self.assertEqual(
            snapshot.metadata["extraction_prompt_version"],
            "baseline_extraction_prompt_v1",
        )

    def test_v2_prompt_relationships_are_frozen_in_report_snapshot(self) -> None:
        thread = _thread_with_extraction(
            prompt_version="baseline_extraction_prompt_v2",
            include_relationship=True,
        )

        snapshot = build_current_report_snapshot(thread)

        self.assertEqual(len(snapshot.extraction.relationships), 1)
        relationship = snapshot.extraction.relationships[0]
        self.assertEqual(relationship.relationship_id, "REL-001")
        self.assertEqual(relationship.subject_entity_id, "ENT-001")
        self.assertEqual(relationship.object_entity_id, "ENT-002")


def _thread_with_extraction(
    *,
    prompt_version: str,
    include_relationship: bool,
) -> ChatThread:
    thread_id = uuid4()
    root = ChatMessage(
        id=uuid4(),
        thread_id=thread_id,
        ordinal=1,
        role="user",
        content="The employee account signed in from host-7.",
        metadata_json={},
    )
    extraction: dict[str, object] = {
        "version": "baseline_extraction_v1",
        "mode": "single_pass_llm",
        "status": "candidate",
        "case_summary": "An employee account sign-in from host-7 was reported.",
        "entities": [
            {
                "entity_id": "ENT-001",
                "name": "Employee account",
                "entity_type": "account",
                "reported_role": None,
                "confidence": "high",
                "source_message_ids": [str(root.id)],
            },
            {
                "entity_id": "ENT-002",
                "name": "host-7",
                "entity_type": "host",
                "reported_role": None,
                "confidence": "high",
                "source_message_ids": [str(root.id)],
            },
        ],
        "evidence": [],
        "timeline": [],
        "missing_information": [],
        "warnings": [],
        "prompt_version": prompt_version,
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "validation_status": "validated",
        "source_message_ids": [str(root.id)],
        "raw_response": None,
    }
    if include_relationship:
        extraction["relationships"] = [
            {
                "relationship_id": "REL-001",
                "subject_entity_id": "ENT-001",
                "predicate": "signed_in_from",
                "object_entity_id": "ENT-002",
                "statement": "The employee account signed in from host-7.",
                "status": "reported",
                "confidence": "high",
                "source_message_ids": [str(root.id)],
            }
        ]
    terminal = ChatMessage(
        id=uuid4(),
        thread_id=thread_id,
        ordinal=2,
        role="assistant",
        content="Terminal answer excluded from report input.",
        retrieval_context_id="context-1",
        metadata_json={"chat_extraction": extraction},
    )
    thread = ChatThread(
        id=thread_id,
        title="Relationship compatibility",
        status="idle",
        next_message_ordinal=3,
    )
    thread.messages = [root, terminal]
    return thread


if __name__ == "__main__":
    unittest.main()
