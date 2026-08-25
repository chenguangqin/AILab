import pytest

from roche_agent.providers import ReplayChatProvider, ReplayEmbeddingProvider


def test_replay_providers_are_deterministic():
    chat = ReplayChatProvider({"case-1": {"text": "固定回答", "input_tokens": 4}})
    assert chat.complete("ignored", metadata={"replay_key": "case-1"}).text == "固定回答"
    with pytest.raises(KeyError):
        chat.complete("ignored", metadata={"replay_key": "missing"})

    embeddings = ReplayEmbeddingProvider({"query": [1.0, 0.0], "doc": [0.0, 1.0]})
    assert embeddings.dimension == 2
    assert embeddings.embed_query("query") == [1.0, 0.0]

