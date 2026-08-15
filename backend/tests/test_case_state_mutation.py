from copy import deepcopy
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from pydantic import ValidationError

from app.models.case_state import CaseStateVersion
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.models.rag_context import RagContext
from app.schemas.chat.rag import QueryResponse
from app.services.chat.case_state_mutation import (
    CASE_STATE_DELTA_PROMPT_VERSION,
    CASE_STATE_DELTA_SYSTEM_PROMPT,
    CASE_STATE_DELTA_VERSION,
    CaseStateDelta,
    CaseStateDeltaChange,
    CaseStateMutationFailure,
    apply_case_state_delta,
)
from app.services.chat.case_state_retrieval import (
    project_case_state_to_retrieval_query,
)
from app.services.llm.structured_output_router import structured_output_schema
from app.services.chat.chat_worker import (
    AssistantOutcome,
    ClaimedChatRun,
    ChatRunWorker,
    process_chat_run,
)
from app.services.extraction.llm_extraction import ExtractionModelResponse


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class _SessionContext:
    def __init__(self, db: Mock):
        self.db = db

    async def __aenter__(self) -> Mock:
        return self.db

    async def __aexit__(self, *_: object) -> None:
        return None


def _parent_state() -> dict[str, object]:
    return {
        "version": "baseline_extraction_v1",
        "mode": "single_pass_llm",
        "status": "candidate",
        "case_summary": "A reported incident.",
        "entities": [
            {
                "entity_id": "host-1",
                "name": "host-1",
                "entity_type": "hostname",
                "reported_role": None,
                "confidence": "medium",
                "source_message_ids": [str(uuid4())],
            }
        ],
        "relationships": [],
        "evidence": [],
        "timeline": [],
        "missing_information": [],
        "warnings": [],
    }


class _DeltaAdapter:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def complete(self, **kwargs: object) -> ExtractionModelResponse:
        import json

        self.calls.append(kwargs)
        return ExtractionModelResponse(text=json.dumps(self.payload))


class CaseStateMutationTests(unittest.IsolatedAsyncioTestCase):
    def test_delta_schema_is_closed_for_supported_providers(self) -> None:
        for provider in ("anthropic", "openrouter"):
            with self.subTest(provider=provider):
                schema = structured_output_schema(CaseStateDelta, provider=provider)

                def walk(value: object) -> None:
                    if isinstance(value, dict):
                        if value.get("type") == "object":
                            self.assertIs(value.get("additionalProperties"), False)
                        self.assertNotEqual(value, {})
                        for child in value.values():
                            walk(child)
                    elif isinstance(value, list):
                        for child in value:
                            walk(child)

                walk(schema)
                self.assertEqual(
                    set(schema["properties"]),
                    {"version", "changes"},
                )
                change_schema = schema["$defs"]["CaseStateDeltaChange"]
                self.assertEqual(
                    set(change_schema["properties"]),
                    {
                        "target_type",
                        "target_id",
                        "field",
                        "old_value",
                        "new_value",
                    },
                )
                self.assertTrue(
                    {"field", "old_value", "new_value"}
                    <= set(change_schema["required"])
                )
                serialized = str(schema)
                self.assertNotIn("source_message_id", serialized)
                self.assertNotIn("mutation_intent", serialized)
                self.assertNotIn("operation", serialized)
                self.assertNotIn("change_type", serialized)
                self.assertNotIn("'value'", serialized)
        raw_change_schema = CaseStateDelta.model_json_schema()["$defs"][
            "CaseStateDeltaChange"
        ]
        self.assertTrue(
            {"field", "old_value", "new_value"} <= set(raw_change_schema["required"])
        )

    def test_empty_changes_is_the_only_no_change_shape(self) -> None:
        self.assertEqual(
            CaseStateDelta(changes=[]).model_dump(mode="json"),
            {"version": "case_state_delta_v2", "changes": []},
        )
        with self.assertRaises(ValidationError):
            CaseStateDelta.model_validate(
                {
                    "version": "case_state_delta_v1",
                    "operation": "no_change",
                    "changes": [],
                }
            )

    def test_change_semantics_reject_remove_both_null_and_same_value(self) -> None:
        invalid_changes = (
            {
                "target_type": "entity",
                "target_id": "host-1",
                "field": "name",
                "old_value": "host-1",
                "new_value": None,
            },
            {
                "target_type": "entity",
                "target_id": "host-1",
                "field": "name",
                "old_value": None,
                "new_value": None,
            },
            {
                "target_type": "entity",
                "target_id": "host-1",
                "field": "name",
                "old_value": "host-1",
                "new_value": "host-1",
            },
        )
        for change in invalid_changes:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                CaseStateDeltaChange.model_validate(change)

    def test_duplicate_same_field_is_rejected_but_multiple_fields_are_allowed(
        self,
    ) -> None:
        changes = [
            CaseStateDeltaChange(
                target_type="entity",
                target_id="host-1",
                field="name",
                old_value="host-1",
                new_value="finance-host-1",
            ),
            CaseStateDeltaChange(
                target_type="entity",
                target_id="host-1",
                field="entity_type",
                old_value="hostname",
                new_value="server",
            ),
        ]
        delta = CaseStateDelta(changes=changes)
        merged = apply_case_state_delta(
            _parent_state(),
            delta,
            source_message_id=uuid4(),
        )
        self.assertEqual(merged["entities"][0]["name"], "finance-host-1")
        self.assertEqual(merged["entities"][0]["entity_type"], "server")

        with self.assertRaises(ValidationError):
            CaseStateDelta(changes=[changes[0], changes[0].model_copy()])

    def test_mixed_add_and_modify_applies_in_one_delta(self) -> None:
        source_id = uuid4()
        delta = CaseStateDelta(
            changes=[
                CaseStateDeltaChange(
                    target_type="entity",
                    target_id="host-1",
                    field="name",
                    old_value="host-1",
                    new_value="finance-host-1",
                ),
                CaseStateDeltaChange(
                    target_type="evidence",
                    target_id="artifact-mixed",
                    field=None,
                    old_value=None,
                    new_value={
                        "evidence_id": "artifact-mixed",
                        "title": "Update.zip",
                        "description": "A user-reported attachment.",
                        "artifact_type": "file",
                        "status": "reported",
                        "confidence": "medium",
                        "source_type": "user_reported",
                    },
                ),
            ]
        )

        merged = apply_case_state_delta(
            _parent_state(),
            delta,
            source_message_id=source_id,
        )

        self.assertEqual(merged["entities"][0]["name"], "finance-host-1")
        self.assertEqual(merged["evidence"][0]["evidence_id"], "artifact-mixed")
        self.assertEqual(
            merged["evidence"][0]["source_message_ids"],
            [str(source_id)],
        )

    def test_non_empty_apply_requires_authoritative_source_message(self) -> None:
        delta = CaseStateDelta(
            changes=[
                CaseStateDeltaChange(
                    target_type="entity",
                    target_id="host-1",
                    field="name",
                    old_value="host-1",
                    new_value="finance-host-1",
                )
            ]
        )

        with self.assertRaises(CaseStateMutationFailure) as raised:
            apply_case_state_delta(_parent_state(), delta)

        self.assertEqual(raised.exception.code, "case_state_mutation_input_missing")

    def test_provider_cannot_supply_provenance(self) -> None:
        with self.assertRaises(ValidationError):
            CaseStateDeltaChange.model_validate(
                {
                    "target_type": "evidence",
                    "target_id": "artifact-1",
                    "field": None,
                    "old_value": None,
                    "new_value": {
                        "evidence_id": "artifact-1",
                        "title": "Update.zip",
                        "description": "A user-reported attachment.",
                        "artifact_type": "file",
                        "status": "reported",
                        "confidence": "medium",
                        "source_type": "user_reported",
                        "source_message_ids": [str(uuid4())],
                    },
                }
            )

    def test_add_merge_is_deterministic_and_does_not_mutate_parent(self) -> None:
        source_id = uuid4()
        parent = _parent_state()
        original = deepcopy(parent)
        delta = CaseStateDelta(
            changes=[
                CaseStateDeltaChange(
                    target_type="evidence",
                    target_id="artifact-1",
                    field=None,
                    old_value=None,
                    new_value={
                        "evidence_id": "artifact-1",
                        "title": "Update.zip",
                        "description": "A user-reported attachment.",
                        "artifact_type": "file",
                        "status": "reported",
                        "confidence": "medium",
                        "source_type": "user_reported",
                    },
                )
            ],
        )

        merged = apply_case_state_delta(
            parent,
            delta,
            source_message_id=source_id,
        )

        self.assertEqual(parent, original)
        self.assertEqual(
            apply_case_state_delta(parent, delta, source_message_id=source_id),
            merged,
        )
        self.assertEqual(merged["evidence"][0]["evidence_id"], "artifact-1")
        self.assertEqual(
            merged["evidence"][0]["source_message_ids"],
            [str(source_id)],
        )

    def test_modify_preserves_parent_and_rejects_missing_target(self) -> None:
        source_id = uuid4()
        parent = _parent_state()
        original_source_ids = list(parent["entities"][0]["source_message_ids"])
        delta = CaseStateDelta(
            changes=[
                CaseStateDeltaChange(
                    target_type="entity",
                    target_id="host-1",
                    field="name",
                    old_value="host-1",
                    new_value="finance-host-1",
                )
            ],
        )
        merged = apply_case_state_delta(parent, delta, source_message_id=source_id)
        self.assertEqual(parent["entities"][0]["name"], "host-1")
        self.assertEqual(merged["entities"][0]["name"], "finance-host-1")
        self.assertEqual(
            merged["entities"][0]["source_message_ids"],
            [*original_source_ids, str(source_id)],
        )

        missing = delta.model_copy(
            update={
                "changes": [
                    delta.changes[0].model_copy(update={"target_id": "missing"})
                ]
            }
        )
        with self.assertRaises(CaseStateMutationFailure):
            apply_case_state_delta(parent, missing, source_message_id=source_id)

    def test_modify_requires_an_exact_old_value_precondition(self) -> None:
        delta = CaseStateDelta(
            changes=[
                CaseStateDeltaChange(
                    target_type="entity",
                    target_id="host-1",
                    field="name",
                    old_value="stale-host-name",
                    new_value="finance-host-1",
                )
            ]
        )

        with self.assertRaises(CaseStateMutationFailure) as raised:
            apply_case_state_delta(
                _parent_state(),
                delta,
                source_message_id=uuid4(),
            )

        self.assertEqual(raised.exception.code, "case_state_delta_stale_target")

    def test_hallucinated_relationship_endpoint_is_rejected(self) -> None:
        source_id = uuid4()
        delta = CaseStateDelta(
            changes=[
                CaseStateDeltaChange(
                    target_type="relationship",
                    target_id="rel-1",
                    field=None,
                    old_value=None,
                    new_value={
                        "relationship_id": "rel-1",
                        "subject_entity_id": "host-1",
                        "predicate": "communicated_with",
                        "object_entity_id": "unknown-actor",
                        "statement": "The host communicated with the actor.",
                        "status": "reported",
                        "confidence": "medium",
                    },
                )
            ],
        )
        with self.assertRaises(CaseStateMutationFailure):
            apply_case_state_delta(
                _parent_state(),
                delta,
                source_message_id=source_id,
            )

    def test_parent_receives_full_baseline_validation_before_copy(self) -> None:
        parent = _parent_state()
        parent["relationships"] = [
            {
                "relationship_id": "rel-invalid",
                "subject_entity_id": "missing-entity",
                "predicate": "contacted",
                "object_entity_id": "host-1",
                "statement": "A missing entity contacted host-1.",
                "status": "reported",
                "confidence": "medium",
                "source_message_ids": [str(uuid4())],
            }
        ]

        with self.assertRaises(CaseStateMutationFailure) as raised:
            apply_case_state_delta(parent, CaseStateDelta(changes=[]))

        self.assertEqual(raised.exception.code, "case_state_parent_invalid")

    async def test_mutation_flow_extracts_delta_then_fresh_rag_then_analysis(self) -> None:
        source_id = uuid4()
        parent = _parent_state()
        state_id = uuid4()
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="The affected file was Update.zip.",
            rag_query="The affected file was Update.zip.",
            original_user_content="The affected file was Update.zip.",
            clarification_exchanges=(),
            followup_root_ordinal=2,
            request_message_id=source_id,
            post_answer_action="add_case_info",
            case_state_version_id=state_id,
            case_state_json=parent,
        )
        worker = Mock()
        worker.claim_run = AsyncMock(return_value=claimed)
        worker.complete_run = AsyncMock(return_value=True)
        rag_call = AsyncMock(
            return_value=QueryResponse(
                status="completed",
                retrieval_context_id="retrieval-2",
                context="fresh context",
            )
        )
        analysis_call = AsyncMock(return_value="Fresh grounded overview")
        delta_payload = {
            "version": "case_state_delta_v2",
            "changes": [
                {
                    "target_type": "evidence",
                    "target_id": "artifact-1",
                    "field": None,
                    "old_value": None,
                    "new_value": {
                        "evidence_id": "artifact-1",
                        "title": "Update.zip",
                        "description": "A user-reported attachment.",
                        "artifact_type": "file",
                        "status": "reported",
                        "confidence": "medium",
                        "source_type": "user_reported",
                    },
                }
            ],
        }
        adapter = _DeltaAdapter(delta_payload)

        with (
            patch(
                "app.services.chat.chat_worker.async_session",
                return_value=_SessionContext(Mock()),
            ),
            patch(
                "app.services.chat.chat_worker.ChatRunWorker",
                return_value=worker,
            ),
        ):
            await process_chat_run(
                claimed.id,
                rag_call=rag_call,
                ask_call=analysis_call,
                extraction_adapter=adapter,
            )

        outcome: AssistantOutcome = worker.complete_run.await_args.args[2]
        assert outcome.validated_case_state_json is not None
        rag_call.assert_awaited_once_with(
            project_case_state_to_retrieval_query(
                outcome.validated_case_state_json,
            )
        )
        analysis_call.assert_awaited_once()
        self.assertEqual(analysis_call.await_args.kwargs["mode"], "case_overview")
        self.assertEqual(
            analysis_call.await_args.kwargs["question"],
            None,
        )
        self.assertTrue(outcome.metadata_json["chat_action"]["state_mutated"])
        self.assertEqual(
            outcome.expected_parent_case_state_version_id,
            state_id,
        )
        self.assertIsNotNone(outcome.case_state_delta_json)
        self.assertEqual(
            outcome.case_state_delta_json["version"],
            CASE_STATE_DELTA_VERSION,
        )
        self.assertNotIn("operation", outcome.case_state_delta_json)
        self.assertEqual(outcome.rag_context_payload.retrieval_context_id, "retrieval-2")
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(
            adapter.calls[0]["system_prompt"],
            CASE_STATE_DELTA_SYSTEM_PROMPT,
        )
        self.assertIn(CASE_STATE_DELTA_PROMPT_VERSION, CASE_STATE_DELTA_SYSTEM_PROMPT)
        self.assertEqual(
            set(adapter.calls[0]["input_payload"]),
            {
                "current_case_state",
                "new_user_message",
                "source_message_id",
                "mutation_intent",
            },
        )
        self.assertEqual(
            adapter.calls[0]["input_payload"]["source_message_id"],
            str(source_id),
        )
        self.assertEqual(
            adapter.calls[0]["input_payload"]["mutation_intent"],
            "add_case_info",
        )

    async def test_no_change_skips_rag_and_durable_child(self) -> None:
        source_id = uuid4()
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="I have no additional information.",
            rag_query="I have no additional information.",
            original_user_content="I have no additional information.",
            clarification_exchanges=(),
            followup_root_ordinal=2,
            request_message_id=source_id,
            post_answer_action="add_case_info",
            case_state_version_id=uuid4(),
            case_state_json=_parent_state(),
        )
        worker = Mock()
        worker.claim_run = AsyncMock(return_value=claimed)
        worker.complete_run = AsyncMock(return_value=True)
        rag_call = AsyncMock()
        payload = {
            "version": "case_state_delta_v2",
            "changes": [],
        }
        with (
            patch(
                "app.services.chat.chat_worker.async_session",
                return_value=_SessionContext(Mock()),
            ),
            patch(
                "app.services.chat.chat_worker.ChatRunWorker",
                return_value=worker,
            ),
        ):
            await process_chat_run(
                claimed.id,
                rag_call=rag_call,
                extraction_adapter=_DeltaAdapter(payload),
            )
        rag_call.assert_not_awaited()
        outcome: AssistantOutcome = worker.complete_run.await_args.args[2]
        self.assertFalse(outcome.metadata_json["chat_action"]["state_mutated"])
        self.assertIsNone(outcome.case_state_delta_json)
        self.assertIsNone(outcome.rag_context_payload)

    async def test_actor_only_update_retrieves_from_complete_merged_lineage(self) -> None:
        source_id = uuid4()
        state_id = uuid4()
        parent = _parent_state()
        parent["case_summary"] = (
            "PowerShell executed an encoded command on host-1."
        )
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="The actor was Alice.",
            rag_query="The actor was Alice.",
            original_user_content="The actor was Alice.",
            clarification_exchanges=(),
            followup_root_ordinal=2,
            request_message_id=source_id,
            post_answer_action="add_case_info",
            case_state_version_id=state_id,
            case_state_json=parent,
        )
        worker = Mock()
        worker.claim_run = AsyncMock(return_value=claimed)
        worker.complete_run = AsyncMock(return_value=True)
        rag_call = AsyncMock(
            return_value=QueryResponse(
                status="completed",
                retrieval_context_id="retrieval-lineage",
                context="fresh context",
            )
        )
        analysis_call = AsyncMock(return_value="Updated overview")
        delta_payload = {
            "version": "case_state_delta_v2",
            "changes": [
                {
                    "target_type": "entity",
                    "target_id": "actor-1",
                    "field": None,
                    "old_value": None,
                    "new_value": {
                        "entity_id": "actor-1",
                        "name": "Alice",
                        "entity_type": "person",
                        "reported_role": "reported actor",
                        "confidence": "medium",
                    },
                }
            ],
        }

        with (
            patch(
                "app.services.chat.chat_worker.async_session",
                return_value=_SessionContext(Mock()),
            ),
            patch(
                "app.services.chat.chat_worker.ChatRunWorker",
                return_value=worker,
            ),
        ):
            await process_chat_run(
                claimed.id,
                rag_call=rag_call,
                ask_call=analysis_call,
                extraction_adapter=_DeltaAdapter(delta_payload),
            )

        retrieval_query = rag_call.await_args.args[0]
        self.assertNotEqual(retrieval_query, claimed.rag_query)
        self.assertIn("PowerShell executed an encoded command", retrieval_query)
        self.assertIn("Alice", retrieval_query)

    async def test_invalid_merge_makes_zero_rag_calls(self) -> None:
        source_id = uuid4()
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="An unknown actor contacted host-1.",
            rag_query="An unknown actor contacted host-1.",
            original_user_content="An unknown actor contacted host-1.",
            clarification_exchanges=(),
            followup_root_ordinal=2,
            request_message_id=source_id,
            post_answer_action="add_case_info",
            case_state_version_id=uuid4(),
            case_state_json=_parent_state(),
        )
        worker = Mock()
        worker.claim_run = AsyncMock(return_value=claimed)
        worker.complete_run = AsyncMock(return_value=True)
        worker.fail_run = AsyncMock(return_value=True)
        rag_call = AsyncMock()
        invalid_delta = {
            "version": "case_state_delta_v2",
            "changes": [
                {
                    "target_type": "relationship",
                    "target_id": "rel-unknown",
                    "field": None,
                    "old_value": None,
                    "new_value": {
                        "relationship_id": "rel-unknown",
                        "subject_entity_id": "unknown-actor",
                        "predicate": "contacted",
                        "object_entity_id": "host-1",
                        "statement": "An unknown actor contacted host-1.",
                        "status": "reported",
                        "confidence": "medium",
                    },
                }
            ],
        }

        with (
            patch(
                "app.services.chat.chat_worker.async_session",
                return_value=_SessionContext(Mock()),
            ),
            patch(
                "app.services.chat.chat_worker.ChatRunWorker",
                return_value=worker,
            ),
        ):
            await process_chat_run(
                claimed.id,
                rag_call=rag_call,
                extraction_adapter=_DeltaAdapter(invalid_delta),
            )

        rag_call.assert_not_awaited()
        worker.complete_run.assert_not_awaited()
        worker.fail_run.assert_awaited_once()
        self.assertEqual(
            worker.fail_run.await_args.args[2],
            "case_state_delta_invalid",
        )

    async def test_complete_run_creates_child_and_context_atomically(self) -> None:
        thread_id = uuid4()
        parent_id = uuid4()
        message_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            status="processing",
            current_case_state_version_id=parent_id,
            next_message_ordinal=3,
        )
        parent = CaseStateVersion(
            id=parent_id,
            thread_id=thread_id,
            version=1,
            parent_version_id=None,
            trigger_message_id=uuid4(),
            delta_json={
                "version": "case_state_delta_v1",
                "operation": "no_change",
                "changes": [],
            },
            state_json=_parent_state(),
        )
        historical_parent_delta = deepcopy(parent.delta_json)
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=message_id,
            operation="query",
            status="running",
            input_rag_session_id=None,
            idempotency_key="mutation-1",
            request_fingerprint="a" * 64,
            request_payload={"action": "add_case_info"},
            attempt_count=1,
            lease_owner="worker-1",
        )
        db = Mock()
        db.begin.return_value = _Transaction()
        db.add = Mock()
        db.flush = AsyncMock()
        parent_result = Mock()
        parent_result.scalar_one_or_none.return_value = parent
        db.execute = AsyncMock(return_value=parent_result)
        worker = ChatRunWorker(db)
        worker._lock_run_thread = AsyncMock(return_value=thread)
        worker._lock_owned_running_run = AsyncMock(return_value=run)
        mutation_delta = CaseStateDelta(
            changes=[
                CaseStateDeltaChange(
                    target_type="evidence",
                    target_id="artifact-2",
                    field=None,
                    old_value=None,
                    new_value={
                        "evidence_id": "artifact-2",
                        "title": "New artifact",
                        "description": "A reported artifact.",
                        "artifact_type": "file",
                        "status": "reported",
                        "confidence": "medium",
                        "source_type": "user_reported",
                    },
                )
            ],
        )
        merged_state = apply_case_state_delta(
            parent.state_json,
            mutation_delta,
            source_message_id=message_id,
        )
        from app.services.chat.outcome_mapper import RagContextPayload

        outcome = AssistantOutcome(
            content="Updated overview",
            retrieval_context_id="retrieval-2",
            metadata_json={"chat_action": {"state_mutated": True}},
            thread_status="answered",
            active_rag_session_id=None,
            validated_case_state_json=merged_state,
            rag_context_payload=RagContextPayload(
                retrieval_context_id="retrieval-2",
                context="fresh context",
                mitre_table=(),
            ),
            case_state_delta_json=mutation_delta.model_dump(mode="json"),
            expected_parent_case_state_version_id=parent_id,
        )

        self.assertTrue(await worker.complete_run(run.id, "worker-1", outcome))
        added = [call.args[0] for call in db.add.call_args_list]
        child = next(item for item in added if isinstance(item, CaseStateVersion))
        context = next(item for item in added if isinstance(item, RagContext))
        self.assertEqual(child.parent_version_id, parent_id)
        self.assertEqual(child.version, 2)
        self.assertEqual(child.trigger_message_id, message_id)
        self.assertEqual(child.delta_json["version"], "case_state_delta_v2")
        self.assertNotIn("operation", child.delta_json)
        self.assertEqual(parent.delta_json, historical_parent_delta)
        self.assertEqual(context.case_state_version_id, child.id)
        self.assertEqual(thread.current_case_state_version_id, child.id)

    async def test_complete_run_rejects_empty_delta_child(self) -> None:
        thread_id = uuid4()
        parent_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            status="processing",
            current_case_state_version_id=parent_id,
            next_message_ordinal=3,
        )
        parent = CaseStateVersion(
            id=parent_id,
            thread_id=thread_id,
            version=1,
            parent_version_id=None,
            trigger_message_id=uuid4(),
            delta_json={
                "version": "case_state_delta_v1",
                "operation": "no_change",
                "changes": [],
            },
            state_json=_parent_state(),
        )
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=uuid4(),
            operation="query",
            status="running",
            input_rag_session_id=None,
            idempotency_key="mutation-empty-child",
            request_fingerprint="a" * 64,
            request_payload={"action": "add_case_info"},
            attempt_count=1,
            lease_owner="worker-1",
        )
        db = Mock()
        db.begin.return_value = _Transaction()
        db.add = Mock()
        db.flush = AsyncMock()
        parent_result = Mock()
        parent_result.scalar_one_or_none.return_value = parent
        db.execute = AsyncMock(return_value=parent_result)
        worker = ChatRunWorker(db)
        worker._lock_run_thread = AsyncMock(return_value=thread)
        worker._lock_owned_running_run = AsyncMock(return_value=run)
        from app.services.chat.outcome_mapper import RagContextPayload

        outcome = AssistantOutcome(
            content="No change must not create a child",
            retrieval_context_id="retrieval-2",
            metadata_json={},
            thread_status="answered",
            active_rag_session_id=None,
            validated_case_state_json=deepcopy(parent.state_json),
            rag_context_payload=RagContextPayload(
                retrieval_context_id="retrieval-2",
                context="fresh context",
                mitre_table=(),
            ),
            case_state_delta_json=CaseStateDelta(changes=[]).model_dump(mode="json"),
            expected_parent_case_state_version_id=parent_id,
        )

        with self.assertRaises(CaseStateMutationFailure) as raised:
            await worker.complete_run(run.id, "worker-1", outcome)

        self.assertEqual(raised.exception.code, "case_state_delta_invalid")
        self.assertFalse(
            any(isinstance(call.args[0], CaseStateVersion) for call in db.add.call_args_list)
        )

    async def test_complete_run_rejects_stale_parent_without_child(self) -> None:
        thread = ChatThread(
            id=uuid4(),
            status="processing",
            current_case_state_version_id=uuid4(),
            next_message_ordinal=2,
        )
        run = ChatRun(
            id=uuid4(),
            thread_id=thread.id,
            request_message_id=uuid4(),
            operation="query",
            status="running",
            input_rag_session_id=None,
            idempotency_key="mutation-stale",
            request_fingerprint="a" * 64,
            request_payload={},
            attempt_count=1,
            lease_owner="worker-1",
        )
        db = Mock()
        db.begin.return_value = _Transaction()
        db.add = Mock()
        db.flush = AsyncMock()
        worker = ChatRunWorker(db)
        worker._lock_run_thread = AsyncMock(return_value=thread)
        worker._lock_owned_running_run = AsyncMock(return_value=run)
        from app.services.chat.outcome_mapper import RagContextPayload

        outcome = AssistantOutcome(
            content="stale",
            retrieval_context_id="retrieval-2",
            metadata_json={},
            thread_status="answered",
            active_rag_session_id=None,
            validated_case_state_json=_parent_state(),
            rag_context_payload=RagContextPayload(
                retrieval_context_id="retrieval-2",
                context="fresh",
                mitre_table=(),
            ),
            case_state_delta_json={"version": "case_state_delta_v2", "changes": []},
            expected_parent_case_state_version_id=uuid4(),
        )
        with self.assertRaises(CaseStateMutationFailure):
            await worker.complete_run(run.id, "worker-1", outcome)
        self.assertFalse(
            any(isinstance(call.args[0], CaseStateVersion) for call in db.add.call_args_list)
        )
