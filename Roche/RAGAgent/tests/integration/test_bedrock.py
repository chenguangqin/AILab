import os

import pytest


@pytest.mark.bedrock
@pytest.mark.skipif(
    not os.getenv("BEDROCK_CHAT_MODEL_ID") or not os.getenv("BEDROCK_EMBED_MODEL_ID"),
    reason="Bedrock model IDs are not configured",
)
def test_bedrock_provider_contract():
    from roche_agent.providers.bedrock import BedrockChatProvider, TitanEmbeddingProvider

    chat = BedrockChatProvider()
    response = chat.complete("只回答：ok")
    assert response.text
    embeddings = TitanEmbeddingProvider()
    vector = embeddings.embed_query("检验科")
    assert len(vector) > 100

