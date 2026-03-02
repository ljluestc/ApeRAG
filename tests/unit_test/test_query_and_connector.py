# Copyright 2025 ApeCloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for aperag.query.query and aperag.vectorstore.connector."""

import pytest

from aperag.query.query import DocumentWithScore, Query, QueryResult, QueryWithEmbedding, get_packed_answer


# ── DocumentWithScore model tests ────────────────────────────

class TestDocumentWithScore:
    def test_defaults(self):
        doc = DocumentWithScore()
        assert doc.text is None
        assert doc.score is None
        assert doc.metadata is None

    def test_with_values(self):
        doc = DocumentWithScore(text="hello", score=0.95, metadata={"source": "test.md"})
        assert doc.text == "hello"
        assert doc.score == 0.95
        assert doc.metadata["source"] == "test.md"

    def test_serialization_roundtrip(self):
        doc = DocumentWithScore(text="x", score=0.5, metadata={"k": "v"})
        data = doc.model_dump()
        restored = DocumentWithScore(**data)
        assert restored == doc


# ── Query / QueryWithEmbedding model tests ───────────────────

class TestQueryModels:
    def test_query_defaults(self):
        q = Query(query="What is Kubernetes?")
        assert q.query == "What is Kubernetes?"
        assert q.top_k == 3

    def test_query_custom_top_k(self):
        q = Query(query="test", top_k=10)
        assert q.top_k == 10

    def test_query_with_embedding(self):
        q = QueryWithEmbedding(query="test", embedding=[0.1, 0.2, 0.3])
        assert q.embedding == [0.1, 0.2, 0.3]
        assert q.top_k == 3  # inherited default


# ── QueryResult model tests ──────────────────────────────────

class TestQueryResult:
    def test_empty_results(self):
        qr = QueryResult(query="test", results=[])
        assert len(qr.results) == 0

    def test_with_documents(self):
        docs = [
            DocumentWithScore(text="a", score=0.9),
            DocumentWithScore(text="b", score=0.8),
        ]
        qr = QueryResult(query="search", results=docs)
        assert len(qr.results) == 2
        assert qr.results[0].text == "a"


# ── get_packed_answer tests ──────────────────────────────────

class TestGetPackedAnswer:
    def test_basic_packing(self):
        results = [
            DocumentWithScore(text="Hello world", score=0.9, metadata={}),
            DocumentWithScore(text="Foo bar", score=0.8, metadata={}),
        ]
        answer = get_packed_answer(results)
        assert "Hello world" in answer
        assert "Foo bar" in answer
        assert "\n\n" in answer

    def test_url_prefix(self):
        results = [
            DocumentWithScore(
                text="Pod is a group of containers",
                score=0.9,
                metadata={"url": "https://k8s.io/docs"},
            ),
        ]
        answer = get_packed_answer(results)
        assert "The following information is from: https://k8s.io/docs" in answer
        assert "Pod is a group of containers" in answer

    def test_limit_length(self):
        results = [
            DocumentWithScore(text="A" * 1000, score=0.9, metadata={}),
        ]
        answer = get_packed_answer(results, limit_length=50)
        assert len(answer) == 50

    def test_limit_length_zero_returns_full(self):
        results = [
            DocumentWithScore(text="Full text", score=0.9, metadata={}),
        ]
        answer = get_packed_answer(results, limit_length=0)
        assert answer == "Full text"

    def test_none_metadata_no_crash(self):
        """Regression: metadata=None should not cause AttributeError."""
        results = [
            DocumentWithScore(text="safe text", score=0.5, metadata=None),
        ]
        answer = get_packed_answer(results)
        assert answer == "safe text"

    def test_none_text_no_crash(self):
        """Regression: text=None should not cause TypeError."""
        results = [
            DocumentWithScore(text=None, score=0.5, metadata={"url": "http://example.com"}),
        ]
        answer = get_packed_answer(results)
        assert "example.com" in answer

    def test_both_none_no_crash(self):
        """Regression: both text=None and metadata=None should not crash."""
        results = [DocumentWithScore()]
        answer = get_packed_answer(results)
        assert answer == ""

    def test_empty_results(self):
        answer = get_packed_answer([])
        assert answer == ""

    def test_multiple_urls(self):
        results = [
            DocumentWithScore(text="A", score=0.9, metadata={"url": "http://a.com"}),
            DocumentWithScore(text="B", score=0.8, metadata={"url": "http://b.com"}),
        ]
        answer = get_packed_answer(results)
        assert "http://a.com" in answer
        assert "http://b.com" in answer


# ── VectorStoreConnectorAdaptor tests ────────────────────────

class TestVectorStoreConnectorAdaptor:
    def test_unsupported_type_raises_value_error(self):
        """Regression: ValueError should have a clear message, not a tuple."""
        from aperag.vectorstore.connector import VectorStoreConnectorAdaptor

        with pytest.raises(ValueError, match="unsupported vector store type: faketype"):
            VectorStoreConnectorAdaptor("faketype", ctx={})

    def test_unsupported_type_error_is_string(self):
        """Ensure the error message is a string, not a tuple."""
        from aperag.vectorstore.connector import VectorStoreConnectorAdaptor

        try:
            VectorStoreConnectorAdaptor("badtype", ctx={})
        except ValueError as e:
            # Before the fix, str(e) would be "('unsupported vector store type:', 'badtype')"
            assert "badtype" in str(e)
            assert "(" not in str(e)  # No tuple representation


# ── Prompts backward compatibility test ──────────────────────

class TestPromptsBackwardCompat:
    def test_memory_templates_accessible(self):
        from aperag.llm.prompts import DEFAULT_MODEL_MEMORY_PROMPT_TEMPLATES

        assert "vicuna-13b" in DEFAULT_MODEL_MEMORY_PROMPT_TEMPLATES

    def test_old_typo_alias_still_works(self):
        from aperag.llm.prompts import DEFAULT_MODEL_MEMOTY_PROMPT_TEMPLATES

        assert "vicuna-13b" in DEFAULT_MODEL_MEMOTY_PROMPT_TEMPLATES

    def test_both_are_same_object(self):
        from aperag.llm.prompts import (
            DEFAULT_MODEL_MEMORY_PROMPT_TEMPLATES,
            DEFAULT_MODEL_MEMOTY_PROMPT_TEMPLATES,
        )

        assert DEFAULT_MODEL_MEMORY_PROMPT_TEMPLATES is DEFAULT_MODEL_MEMOTY_PROMPT_TEMPLATES
