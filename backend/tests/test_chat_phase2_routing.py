from copy import deepcopy
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from app.models.case_state import CaseStateVersion
from fastapi import HTTPException

from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.models.rag_context import RagContext
from app.schemas.chat import ChatMessageCreate
from app.schemas.chat.rag import QueryResponse
from app.services.case_analysis import build_case_analysis_prompt
from app.services.chat.case_state_retrieval import (
    project_case_state_to_retrieval_query,
)
from app.services.chat.chat_message import ChatMessageService
from app.services.chat.chat_worker import (
    ClaimedChatRun,
    AssistantOutcome,
    ChatRunWorker,
    FollowUpResolution,
    map_rag_response,
    process_chat_run,
)


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class _SessionContext:
    def __init__(self, db: Mock):
        self.db = db

    async def __aenter__(self) -> Mock:
        return self.db

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


def _result(value: object) -> Mock:
    result = Mock()
    result.scalar_one_or_none.return_value = value
    return result


def _validated_case_state(summary: str) -> dict[str, object]:
    return {
        "version": "baseline_extraction_v1",
        "mode": "single_pass_llm",
        "status": "candidate",
        "case_summary": summary,
        "entities": [],
        "relationships": [],
        "evidence": [],
        "timeline": [],
        "missing_information": [],
        "warnings": [],
    }


def _answered_message_db(
    thread: ChatThread,
    state: CaseStateVersion,
) -> Mock:
    db = Mock()
    db.begin.return_value = _Transaction()
    db.execute = AsyncMock(
        side_effect=[
            _result(thread),
            _result(None),
            _result(None),
            _result(state),
        ]
    )
    added: list[object] = []
    db.add.side_effect = added.append

    async def flush() -> None:
        for item in added:
            if isinstance(item, (ChatMessage, ChatRun)) and item.id is None:
                item.id = uuid4()

    db.flush = AsyncMock(side_effect=flush)
    db.refresh = AsyncMock()
    return db


class ChatPhase2RoutingTests(unittest.IsolatedAsyncioTestCase):
    def _answered_thread_and_state(self) -> tuple[ChatThread, CaseStateVersion]:
        thread_id = uuid4()
        state_id = uuid4()
        message_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Answered case",
            status="answered",
            current_case_state_version_id=state_id,
            next_message_ordinal=2,
        )
        state = CaseStateVersion(
            id=state_id,
            thread_id=thread_id,
            version=1,
            parent_version_id=None,
            trigger_message_id=message_id,
            delta_json={},
            state_json={"case_summary": "reported host-7 activity"},
        )
        return thread, state

    def test_rag_response_maps_only_retrieval_context(self) -> None:
        outcome = map_rag_response(
            QueryResponse(
                status="completed",
                retrieval_context_id="retrieval-1",
                context="bounded context",
            )
        )

        self.assertEqual(outcome["retrieved_context"], "bounded context")
        self.assertNotIn("answer", outcome)

    def test_ask_prompt_contains_case_state_analysis_context_and_question(self) -> None:
        prompt = build_case_analysis_prompt(
            mode="question_answer",
            case_state_json={"case_summary": "reported host-7 activity"},
            analysis_context={
                "answer": "The latest analysis identified host-7.",
                "retrieval_context_id": "retrieval-1",
                "mitre_table": [{"technique_id": "T1059"}],
            },
            question="Which host should be investigated next?",
        )

        self.assertIn("reported host-7 activity", prompt)
        self.assertIn("The latest analysis identified host-7.", prompt)
        self.assertIn("retrieval-1", prompt)
        self.assertIn("Which host should be investigated next?", prompt)
        self.assertIn('"analysis_mode":"question_answer"', prompt)

    async def test_ask_claim_loads_exact_current_case_and_rag_context(self) -> None:
        thread_id = uuid4()
        state_id = uuid4()
        request_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Answered case",
            status="answered",
            current_case_state_version_id=state_id,
            next_message_ordinal=4,
        )
        state = CaseStateVersion(
            id=state_id,
            thread_id=thread_id,
            version=1,
            parent_version_id=None,
            trigger_message_id=uuid4(),
            delta_json={},
            state_json={"case_summary": "reported host-7 activity"},
        )
        rag_context = RagContext(
            retrieval_context_id="retrieval-1",
            thread_id=thread_id,
            case_state_version_id=state_id,
            context="bounded durable context",
            mitre_table=[{"technique_id": "T1059"}],
        )
        request_message = ChatMessage(
            id=request_id,
            thread_id=thread_id,
            ordinal=3,
            role="user",
            content="Which host should be investigated next?",
            metadata_json={},
        )
        run = ChatRun(
            id=uuid4(),
            thread_id=thread_id,
            request_message_id=request_id,
            operation="query",
            status="queued",
            input_rag_session_id=None,
            idempotency_key="ask-claim-1",
            request_fingerprint="a" * 64,
            request_payload={
                "content": request_message.content,
                "rag_query": request_message.content,
                "action": "ask",
            },
            attempt_count=0,
        )
        run_result = _result(run)
        pointer_result = _result(state.id)
        state_result = _result(state)
        rag_context_result = _result(rag_context)
        request_result = _result(request_message)

        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(
            side_effect=[
                run_result,
                pointer_result,
                state_result,
                rag_context_result,
                request_result,
            ]
        )
        db.flush = AsyncMock()

        claimed = await ChatRunWorker(db).claim_run(run.id, "worker-ask")

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual(claimed.case_state_json, state.state_json)
        self.assertEqual(
            claimed.analysis_context,
            {
                "retrieved_context": "bounded durable context",
                "retrieval_context_id": "retrieval-1",
                "mitre_table": [{"technique_id": "T1059"}],
                "previous_analysis": None,
            },
        )
        executed_statements = [call.args[0] for call in db.execute.await_args_list]
        state_statement = str(executed_statements[2])
        context_statement = str(executed_statements[3])
        self.assertIn("case_state_versions.thread_id", state_statement)
        self.assertIn("case_state_versions.id", state_statement)
        self.assertIn("rag_contexts.thread_id", context_statement)
        self.assertIn("rag_contexts.case_state_version_id", context_statement)

    async def test_ask_keeps_case_state_pointer_without_building_a_rag_query(
        self,
    ) -> None:
        thread, state = self._answered_thread_and_state()
        db = _answered_message_db(thread, state)

        _, run = await ChatMessageService(db).create_message_and_run(
            thread.id,
            ChatMessageCreate(
                content="Which host should be investigated next?",
                idempotency_key="ask-1",
                action="ask",
            ),
        )

        self.assertEqual(thread.current_case_state_version_id, state.id)
        self.assertEqual(run.request_payload["action"], "ask")
        self.assertIn(
            "Which host should be investigated next?",
            run.request_payload["rag_query"],
        )
        self.assertFalse(
            any(
                isinstance(call.args[0], CaseStateVersion)
                for call in db.add.call_args_list
            )
        )

    async def test_add_case_info_uses_distinct_route_without_state_mutation(self) -> None:
        thread, state = self._answered_thread_and_state()
        db = _answered_message_db(thread, state)

        _, run = await ChatMessageService(db).create_message_and_run(
            thread.id,
            ChatMessageCreate(
                content="The affected host was confirmed as host-9.",
                idempotency_key="add-1",
                action="add_case_info",
            ),
        )

        self.assertEqual(run.request_payload["action"], "add_case_info")
        self.assertEqual(
            run.request_payload["rag_query"],
            "The affected host was confirmed as host-9.",
        )
        self.assertEqual(thread.current_case_state_version_id, state.id)
        self.assertFalse(
            any(
                isinstance(call.args[0], CaseStateVersion)
                for call in db.add.call_args_list
            )
        )

    async def test_answered_requires_an_explicit_action(self) -> None:
        thread, state = self._answered_thread_and_state()
        db = _answered_message_db(thread, state)

        with self.assertRaises(HTTPException) as raised:
            await ChatMessageService(db).create_message_and_run(
                thread.id,
                ChatMessageCreate(
                    content="What happened next?",
                    idempotency_key="missing-action",
                ),
            )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(thread.current_case_state_version_id, state.id)

    async def test_add_case_info_worker_routes_through_mutation_pipeline(self) -> None:
        from app.services.chat.case_state_mutation import CaseStateDelta

        source_message_id = uuid4()
        state_id = uuid4()
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="A new reported case fact.",
            rag_query="A new reported case fact.",
            original_user_content="A new reported case fact.",
            clarification_exchanges=(),
            followup_root_ordinal=2,
            request_message_id=source_message_id,
            post_answer_action="add_case_info",
            case_state_version_id=state_id,
            case_state_json={"case_summary": "existing"},
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
        analysis_call = AsyncMock(return_value="Updated overview")
        delta = CaseStateDelta(changes=[])

        with (
            patch(
                "app.services.chat.chat_worker.async_session",
                return_value=_SessionContext(Mock()),
            ),
            patch(
                "app.services.chat.chat_worker.ChatRunWorker",
                return_value=worker,
            ),
            patch(
                "app.services.chat.chat_worker.run_case_state_delta_extraction",
                new=AsyncMock(
                    return_value=(
                        delta,
                        {"status": "candidate", "version": "case_state_delta_v2"},
                    )
                ),
            ),
        ):
            await process_chat_run(
                claimed.id,
                rag_call=rag_call,
                ask_call=analysis_call,
            )

        rag_call.assert_not_awaited()
        outcome: AssistantOutcome = worker.complete_run.await_args.args[2]
        self.assertEqual(outcome.thread_status, "answered")
        self.assertEqual(
            outcome.metadata_json["chat_action"]["route"],
            "case_update",
        )
        self.assertFalse(outcome.metadata_json["chat_action"]["state_mutated"])
        self.assertIsNone(outcome.validated_case_state_json)

    async def test_ask_reuses_exact_persisted_context_without_rag(self) -> None:
        case_state = {"case_summary": "reported host-7 activity"}
        analysis_context = {
            "retrieved_context": "bounded durable context",
            "retrieval_context_id": "retrieval-1",
            "mitre_table": [
                {
                    "technique_id": "T1059",
                    "name": "Command and Scripting Interpreter",
                }
            ],
            "previous_analysis": None,
        }
        expected_case_state = deepcopy(case_state)
        expected_analysis_context = deepcopy(analysis_context)
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="Which host should be investigated next?",
            rag_query="Which host should be investigated next?",
            original_user_content="Which host should be investigated next?",
            clarification_exchanges=(),
            followup_root_ordinal=3,
            post_answer_action="ask",
            case_state_json=case_state,
            analysis_context=analysis_context,
        )
        worker = Mock()
        worker.claim_run = AsyncMock(return_value=claimed)
        worker.complete_run = AsyncMock(return_value=True)
        rag_call = AsyncMock()
        ask_inputs: dict[str, object] = {}
        extraction_call = AsyncMock()

        async def ask_call(**kwargs: object) -> str:
            ask_inputs.update(kwargs)
            return "Reasoned answer from the existing case context."

        with (
            patch(
                "app.services.chat.chat_worker.async_session",
                return_value=_SessionContext(Mock()),
            ),
            patch(
                "app.services.chat.chat_worker.ChatRunWorker",
                return_value=worker,
            ),
            patch(
                "app.services.chat.chat_worker.request_rag",
                new=AsyncMock(),
            ) as default_rag_call,
            patch(
                "app.services.chat.chat_worker.run_validated_case_state_extraction",
                new=extraction_call,
            ),
        ):
            await process_chat_run(
                claimed.id,
                rag_call=rag_call,
                ask_call=ask_call,
            )

        rag_call.assert_not_awaited()
        default_rag_call.assert_not_awaited()
        extraction_call.assert_not_awaited()
        self.assertEqual(ask_inputs["case_state_json"], case_state)
        self.assertEqual(ask_inputs["analysis_context"], analysis_context)
        self.assertEqual(
            ask_inputs["question"],
            "Which host should be investigated next?",
        )
        self.assertEqual(ask_inputs["mode"], "question_answer")
        outcome: AssistantOutcome = worker.complete_run.await_args.args[2]
        self.assertEqual(
            outcome.content,
            "Reasoned answer from the existing case context.",
        )
        self.assertEqual(outcome.retrieval_context_id, "retrieval-1")
        self.assertFalse(outcome.metadata_json["chat_action"]["rag_invoked"])
        self.assertTrue(
            outcome.metadata_json["chat_action"]["retrieval_context_reused"]
        )
        self.assertFalse(outcome.metadata_json["chat_action"]["state_mutated"])
        self.assertFalse(
            outcome.metadata_json["chat_action"]["case_state_version_created"]
        )
        self.assertIsNone(outcome.validated_case_state_json)
        self.assertIsNone(outcome.rag_context_payload)
        self.assertEqual(case_state, expected_case_state)
        self.assertEqual(analysis_context, expected_analysis_context)
        outcome.metadata_json["mitre_table"][0]["name"] = "mutated output"
        self.assertEqual(
            analysis_context["mitre_table"][0]["name"],
            "Command and Scripting Interpreter",
        )

    async def test_action_free_initial_flow_uses_extraction_rag_then_analysis(self) -> None:
        extraction_input = Mock()
        claimed = ClaimedChatRun(
            id=uuid4(),
            operation="query",
            input_rag_session_id=None,
            content="Investigate the suspicious PowerShell event.",
            rag_query="Investigate the suspicious PowerShell event.",
            original_user_content="Investigate the suspicious PowerShell event.",
            clarification_exchanges=(),
            followup_root_ordinal=1,
            extraction_input=extraction_input,
        )
        worker = Mock()
        worker.claim_run = AsyncMock(return_value=claimed)
        worker.complete_run = AsyncMock(return_value=True)
        rag_call = AsyncMock(
            return_value=QueryResponse(
                status="completed",
                retrieval_context_id="retrieval-1",
                context="bounded context",
            )
        )
        case_state = _validated_case_state("validated candidate Case State")
        extraction_metadata = {"status": "candidate", "validation_status": "validated"}
        analysis_call = AsyncMock(return_value="Grounded initial analysis.")

        with (
            patch(
                "app.services.chat.chat_worker.async_session",
                return_value=_SessionContext(Mock()),
            ),
            patch(
                "app.services.chat.chat_worker.ChatRunWorker",
                return_value=worker,
            ),
            patch(
                "app.services.chat.chat_worker.evaluate_followup_outcome",
                new=AsyncMock(
                    return_value=FollowUpResolution(
                        outcome=None,
                        metadata_json={},
                    )
                ),
            ),
            patch(
                "app.services.chat.chat_worker.run_validated_case_state_extraction",
                new=AsyncMock(return_value=(case_state, extraction_metadata)),
            ) as extraction_call,
        ):
            await process_chat_run(
                claimed.id,
                rag_call=rag_call,
                ask_call=analysis_call,
            )

        extraction_call.assert_awaited_once()
        rag_call.assert_awaited_once_with(
            project_case_state_to_retrieval_query(case_state)
        )
        analysis_call.assert_awaited_once_with(
            mode="case_overview",
            case_state_json=case_state,
            analysis_context={
                "retrieved_context": "bounded context",
                "retrieval_context_id": "retrieval-1",
                "mitre_table": [],
                "previous_analysis": None,
            },
            question=None,
        )
        outcome: AssistantOutcome = worker.complete_run.await_args.args[2]
        self.assertEqual(outcome.content, "Grounded initial analysis.")
        self.assertEqual(outcome.thread_status, "answered")
        self.assertEqual(outcome.metadata_json["retrieved_context"], "bounded context")
        self.assertIsNotNone(outcome.rag_context_payload)
        assert outcome.rag_context_payload is not None
        self.assertEqual(
            outcome.rag_context_payload.retrieval_context_id,
            "retrieval-1",
        )
        self.assertEqual(outcome.rag_context_payload.context, "bounded context")
        self.assertEqual(outcome.rag_context_payload.mitre_table, ())

    async def test_initial_flow_rejects_missing_durable_rag_data_before_main(
        self,
    ) -> None:
        invalid_responses = (
            QueryResponse(
                status="completed",
                retrieval_context_id=None,
                context="bounded context",
            ),
            QueryResponse(
                status="completed",
                retrieval_context_id="retrieval-1",
                context="   ",
            ),
        )
        for response in invalid_responses:
            with self.subTest(response=response.model_dump()):
                claimed = ClaimedChatRun(
                    id=uuid4(),
                    operation="query",
                    input_rag_session_id=None,
                    content="Investigate the suspicious PowerShell event.",
                    rag_query="Investigate the suspicious PowerShell event.",
                    original_user_content=(
                        "Investigate the suspicious PowerShell event."
                    ),
                    clarification_exchanges=(),
                    followup_root_ordinal=1,
                    extraction_input=Mock(),
                )
                worker = Mock()
                worker.claim_run = AsyncMock(return_value=claimed)
                worker.complete_run = AsyncMock(return_value=True)
                worker.fail_run = AsyncMock(return_value=True)
                rag_call = AsyncMock(return_value=response)
                analysis_call = AsyncMock(return_value="must not be used")

                with (
                    patch(
                        "app.services.chat.chat_worker.async_session",
                        return_value=_SessionContext(Mock()),
                    ),
                    patch(
                        "app.services.chat.chat_worker.ChatRunWorker",
                        return_value=worker,
                    ),
                    patch(
                        "app.services.chat.chat_worker.evaluate_followup_outcome",
                        new=AsyncMock(
                            return_value=FollowUpResolution(
                                outcome=None,
                                metadata_json={},
                            )
                        ),
                    ),
                    patch(
                        "app.services.chat.chat_worker.run_validated_case_state_extraction",
                        new=AsyncMock(
                            return_value=(
                                _validated_case_state("validated case state"),
                                {"status": "candidate"},
                            )
                        ),
                    ),
                ):
                    await process_chat_run(
                        claimed.id,
                        rag_call=rag_call,
                        ask_call=analysis_call,
                    )

                rag_call.assert_awaited_once()
                analysis_call.assert_not_awaited()
                worker.complete_run.assert_not_awaited()
                worker.fail_run.assert_awaited_once()
                failure_args = worker.fail_run.await_args.args
                self.assertEqual(failure_args[2], "rag_invalid_response")
                self.assertEqual(
                    failure_args[3],
                    "RAG service returned an invalid response",
                )

    async def test_awaiting_followup_remains_action_free(self) -> None:
        thread_id = uuid4()
        thread = ChatThread(
            id=thread_id,
            title="Follow-up case",
            status="awaiting_followup",
            next_message_ordinal=3,
        )
        original = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=1,
            role="user",
            content="Investigate the suspicious PowerShell event.",
            metadata_json={},
        )
        question = ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            ordinal=2,
            role="assistant",
            content="Which host was affected?",
            metadata_json={},
        )
        db = Mock()
        db.begin.return_value = _Transaction()
        db.execute = AsyncMock(
            side_effect=[
                _result(thread),
                _result(None),
                _result(None),
                Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[original, question])))),
            ]
        )
        added: list[object] = []
        db.add.side_effect = added.append

        async def flush() -> None:
            for item in added:
                if isinstance(item, (ChatMessage, ChatRun)) and item.id is None:
                    item.id = uuid4()

        db.flush = AsyncMock(side_effect=flush)
        db.refresh = AsyncMock()

        _, run = await ChatMessageService(db).create_message_and_run(
            thread_id,
            ChatMessageCreate(
                content="host-7",
                idempotency_key="followup-1",
            ),
        )

        self.assertNotIn("action", run.request_payload)
        self.assertEqual(run.request_payload["followup_round"], 1)
        self.assertEqual(thread.status, "processing")
