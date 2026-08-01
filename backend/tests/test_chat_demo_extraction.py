import unittest
from uuid import uuid4

from app.services.chat.chat_worker import (
    AssistantOutcome,
    ClaimedChatRun,
    attach_demo_extraction,
)
from app.services.chat.demo_extraction import (
    add_demo_chat_extraction,
    build_demo_chat_extraction,
)
from app.services.chat.followup_policy import ClarificationExchange


class ChatDemoExtractionTests(unittest.TestCase):
    def test_extracts_reported_evidence_and_timeline_candidates(self) -> None:
        extraction = build_demo_chat_extraction(
            """
            A phishing alert was raised after a suspicious sign-in.
            Available Evidence:
            - Exchange alert and endpoint log
            At 09:32 the attacker downloaded a file.
            Then at 09:45 the analyst disabled the account.
            """
        )

        self.assertEqual(extraction["mode"], "deterministic_demo")
        self.assertEqual(extraction["status"], "candidate")
        self.assertGreaterEqual(len(extraction["evidence"]), 2)
        self.assertEqual(extraction["evidence"][0]["evidence_id"], "E-001")
        timestamps = [
            item["timestamp"]
            for item in extraction["timeline"]
            if item["timestamp"] is not None
        ]
        self.assertEqual(timestamps, ["09:32", "09:45"])

    def test_metadata_extension_preserves_existing_chat_metadata(self) -> None:
        metadata = add_demo_chat_extraction(
            {"mitre_table": [{"technique_id": "T1059"}]},
            "PowerShell process created an endpoint log at 11:05.",
        )

        self.assertEqual(metadata["mitre_table"], [{"technique_id": "T1059"}])
        self.assertIn("chat_extraction", metadata)

    def test_followup_answers_are_included_only_for_terminal_outcomes(self) -> None:
        claimed_run = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="initial",
            rag_query="initial",
            original_user_content="A suspicious login occurred.",
            clarification_exchanges=(
                ClarificationExchange(
                    question="When?",
                    answer="At 12:30 the endpoint log showed a new process.",
                ),
            ),
            followup_root_ordinal=1,
        )
        terminal = AssistantOutcome(
            content="Done",
            retrieval_context_id=None,
            metadata_json={},
            thread_status="idle",
            active_rag_session_id=None,
        )
        followup = AssistantOutcome(
            content="When did this happen?",
            retrieval_context_id=None,
            metadata_json={"chat_followup": {"round": 1}},
            thread_status="awaiting_followup",
            active_rag_session_id=None,
        )

        enriched = attach_demo_extraction(terminal, claimed_run)

        timestamps = [
            item["timestamp"]
            for item in enriched.metadata_json["chat_extraction"]["timeline"]
            if item["timestamp"] is not None
        ]
        self.assertEqual(timestamps, ["12:30"])
        self.assertEqual(attach_demo_extraction(followup, claimed_run), followup)
