import ast
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from RAG.GraphRAG.llm_content import LlmContentError, require_message_text


PIPELINE_FILES = (
    "agent_graph.py",
    "chain.py",
    "cross_lingual.py",
    "evaluator.py",
    "query_decomposer.py",
    "router.py",
)
RESPONSE_NAMES = {
    "response",
    "resp",
    "reasoning_response",
    "translation_response",
}


class StubLlm:
    def __init__(self, response: AIMessage) -> None:
        self.response = response

    def invoke(self, messages: object) -> AIMessage:
        return self.response


class RaisingLlm:
    def invoke(self, messages: object) -> AIMessage:
        raise RuntimeError("transport failure")


class StubRouter:
    def route_query(self, query: str) -> str:
        return "GENERAL_EXPLANATION"


class BrokenTextMessage(AIMessage):
    @property
    def text(self) -> str:
        raise ValueError("provider-secret")


def message(content: Any) -> AIMessage:
    return AIMessage(content=content)


def test_string_content_is_returned_without_trimming() -> None:
    assert (
        require_message_text(message("  visible answer  "), operation="test response")
        == "  visible answer  "
    )


def test_mixed_reasoning_and_text_returns_only_visible_text() -> None:
    secret = "encrypted-reasoning-secret"
    result = require_message_text(
        message(
            [
                {"type": "redacted_thinking", "data": secret},
                {"type": "text", "text": "visible answer"},
            ]
        ),
        operation="test response",
    )

    assert result == "visible answer"
    assert secret not in result


def test_text_blocks_are_concatenated_in_order() -> None:
    result = require_message_text(
        message(
            [
                {"type": "text", "text": "first"},
                {"type": "text", "text": " second"},
            ]
        ),
        operation="test response",
    )

    assert result == "first second"


def test_unknown_blocks_are_ignored_when_visible_text_exists() -> None:
    result = require_message_text(
        message(
            [
                {"type": "future_provider_block", "payload": "hidden"},
                {"type": "text", "text": "visible"},
            ]
        ),
        operation="test response",
    )

    assert result == "visible"


@pytest.mark.parametrize(
    "content",
    (
        "",
        " \t\n",
        [],
        [{"type": "redacted_thinking", "data": "hidden"}],
        [{"type": "future_provider_block", "payload": "hidden"}],
        [{"type": "text"}],
        [{"type": "text", "text": None}],
    ),
)
def test_empty_unknown_and_malformed_content_raises(content: Any) -> None:
    with pytest.raises(LlmContentError, match="test response"):
        require_message_text(message(content), operation="test response")


def test_error_does_not_expose_block_or_property_secrets() -> None:
    block_secret = "unknown-block-secret"
    with pytest.raises(LlmContentError) as block_error:
        require_message_text(
            message([{"type": "unknown", "data": block_secret}]),
            operation="safe operation",
        )

    with pytest.raises(LlmContentError) as property_error:
        require_message_text(
            BrokenTextMessage(content=""),
            operation="safe operation",
        )

    assert str(block_error.value) == "safe operation returned no usable text"
    assert str(property_error.value) == "safe operation returned no usable text"
    assert block_secret not in str(block_error.value)
    assert "provider-secret" not in str(property_error.value)


def test_evaluator_reads_visible_json_and_propagates_empty_content() -> None:
    from RAG.GraphRAG.pipeline.evaluator import ContextEvaluator

    evaluator = ContextEvaluator.__new__(ContextEvaluator)
    evaluator.llm = StubLlm(
        message(
            [
                {"type": "redacted_thinking", "data": "evaluator-secret"},
                {
                    "type": "text",
                    "text": '{"verdict":"SUFFICIENT","reason":"grounded"}',
                },
            ]
        )
    )

    result = evaluator.evaluate("query", "query", "context", verbose=False)

    assert result.verdict == "SUFFICIENT"
    assert result.reason == "grounded"

    evaluator.llm = StubLlm(message([{"type": "unknown", "data": "hidden"}]))
    with pytest.raises(LlmContentError, match="context evaluation"):
        evaluator.evaluate("query", "query", "context", verbose=False)


def test_router_falls_back_only_for_content_error() -> None:
    from RAG.GraphRAG.pipeline.router import QueryRouter

    router = QueryRouter.__new__(QueryRouter)
    router.llm = StubLlm(message([{"type": "unknown", "data": "hidden"}]))

    assert router.route_query("query") == "INCIDENT_ANALYSIS"

    router.llm = RaisingLlm()
    with pytest.raises(RuntimeError, match="transport failure"):
        router.route_query("query")


def test_decomposer_keeps_existing_whole_query_fallback() -> None:
    from RAG.GraphRAG.pipeline.query_decomposer import QueryDecomposer

    decomposer = QueryDecomposer.__new__(QueryDecomposer)
    decomposer.llm = StubLlm(message([{"type": "unknown", "data": "hidden"}]))

    assert decomposer.decompose("suspicious activity", verbose=False) == [
        "suspicious activity"
    ]


def test_cross_lingual_translation_returns_original_on_content_error() -> None:
    from RAG.GraphRAG.pipeline.cross_lingual import CrossLingualLayer

    translator = CrossLingualLayer.__new__(CrossLingualLayer)
    translator.llm = StubLlm(message([{"type": "unknown", "data": "hidden"}]))
    query = "พบมัลแวร์ในเครื่อง"

    assert translator.translate_query(query) == query

    translator.llm = RaisingLlm()
    with pytest.raises(RuntimeError, match="transport failure"):
        translator.translate_query(query)


def test_chain_final_answer_excludes_non_text_blocks() -> None:
    from RAG.GraphRAG.pipeline.chain import GraphRAGChain

    chain = GraphRAGChain.__new__(GraphRAGChain)
    chain.router = StubRouter()
    chain.reasoning_llm = StubLlm(
        message(
            [
                {"type": "redacted_thinking", "data": "answer-secret"},
                {"type": "text", "text": "final visible answer"},
            ]
        )
    )

    result = chain.query_with_details("What is phishing?", verbose=False)

    assert result.answer == "final visible answer"
    assert "answer-secret" not in result.answer

    chain.reasoning_llm = StubLlm(message([{"type": "unknown"}]))
    with pytest.raises(LlmContentError, match="general explanation"):
        chain.query_with_details("What is phishing?", verbose=False)


def test_pipeline_files_do_not_directly_consume_response_content() -> None:
    pipeline_dir = (
        Path(__file__).parents[1] / "app" / "RAG" / "GraphRAG" / "pipeline"
    )

    for filename in PIPELINE_FILES:
        tree = ast.parse((pipeline_dir / filename).read_text(encoding="utf-8"))
        direct_consumers = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "content"
            and isinstance(node.value, ast.Name)
            and node.value.id in RESPONSE_NAMES
        ]
        assert not direct_consumers, filename
