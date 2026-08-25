#!/usr/bin/env python3
"""
模型可用性探测 —— 开新实验环境/上课前跑一遍，确认课程依赖的模型真能调。

为什么不用控制面的 availability API 判定：
    实测发现 get-foundation-model-availability 可能显示 agreement=NOT_AVAILABLE，
    但模型其实能正常 invoke。**以最小真实调用为准**。

用法：
    python3 check_models.py                 # 用默认 region（环境变量 AWS_REGION 或 us-west-2）
    AWS_REGION=us-east-1 python3 check_models.py

退出码：全部可用返回 0，有任一不可用返回 1（方便接 CI / 课前检查）。
"""
from __future__ import annotations

import json
import os
import sys

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-west-2")

bedrock = boto3.client("bedrock", region_name=REGION)
brt = boto3.client("bedrock-runtime", region_name=REGION)
bart = boto3.client("bedrock-agent-runtime", region_name=REGION)
ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]


def model_arn(model_id: str) -> str:
    """与 common.build_model_arn 同规则：带区域前缀 → inference-profile，否则 foundation-model。"""
    if model_id.startswith(("us.", "global.", "eu.", "apac.")):
        return f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:inference-profile/{model_id}"
    return f"arn:aws:bedrock:{REGION}::foundation-model/{model_id}"


def _err(e: ClientError) -> str:
    code = e.response["Error"]["Code"]
    msg = e.response["Error"]["Message"]
    if "marketplace" in msg.lower() or code == "AccessDeniedException":
        return f"🔒 未开通/无权限 ({code})"
    if code == "ResourceNotFoundException":
        return f"❓ 不存在/区域不支持 ({code})"
    return f"⚠️ {code}: {msg[:120]}"


def check_generation(model_id: str) -> tuple[bool, str]:
    """生成模型：用 Converse 发一个最短 prompt。modelId 直接传（profile id 亦可）。"""
    try:
        resp = brt.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "ping，回一个字"}]}],
            inferenceConfig={"maxTokens": 16, "temperature": 0.0},
        )
        txt = resp["output"]["message"]["content"][0]["text"].strip()
        return True, f"✅ 可用（回 {txt[:20]!r}）"
    except ClientError as e:
        return False, _err(e)
    except Exception as e:  # noqa: BLE001
        return False, f"⚠️ {type(e).__name__}: {str(e)[:120]}"


def check_embedding(model_id: str) -> tuple[bool, str]:
    """嵌入模型：invoke_model 发一条短文本。Titan 与 Cohere 的 body 不同。"""
    if model_id.startswith("cohere."):
        body = {"texts": ["测试 hello"], "input_type": "search_query"}
        key = "embeddings"
    else:  # Titan text
        body = {"inputText": "测试 hello"}
        key = "embedding"
    try:
        resp = brt.invoke_model(modelId=model_id, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
        vec = payload[key][0] if key == "embeddings" else payload[key]
        return True, f"✅ 可用（dim {len(vec)}）"
    except ClientError as e:
        return False, _err(e)
    except Exception as e:  # noqa: BLE001
        return False, f"⚠️ {type(e).__name__}: {str(e)[:120]}"


def check_rerank(model_id: str) -> tuple[bool, str]:
    """重排模型：用 Bedrock Rerank API 发 2 个候选。"""
    try:
        resp = bart.rerank(
            queries=[{"type": "TEXT", "textQuery": {"text": "退货政策"}}],
            sources=[
                {"type": "INLINE",
                 "inlineDocumentSource": {"type": "TEXT", "textDocument": {"text": d}}}
                for d in ["七天无理由退货", "物流时效说明"]
            ],
            rerankingConfiguration={
                "type": "BEDROCK_RERANKING_MODEL",
                "bedrockRerankingConfiguration": {
                    "numberOfResults": 2,
                    "modelConfiguration": {"modelArn": model_arn(model_id)},
                },
            },
        )
        return True, f"✅ 可用（{len(resp.get('results', []))} 条）"
    except ClientError as e:
        return False, _err(e)
    except Exception as e:  # noqa: BLE001
        return False, f"⚠️ {type(e).__name__}: {str(e)[:120]}"


# 课程依赖的 Bedrock 模型清单：(类别, 模型 ID, 检测函数)
# 开源栈版：生成 = Bedrock Claude；嵌入 = Bedrock Titan。
#   ⚠️ 下面 Claude 的 inference-profile id 各账号/区域不同，请替换为本环境实测 id
#      （与 common.MODEL_IDS 的 gen_* 保持一致）。
# 重排（bge-reranker-v2-m3）与本地嵌入（bge-m3）是本地开源模型，不走 Bedrock，
#   不在此校验；如需自检见文末 check_local()。
MODELS = [
    ("生成", os.environ.get("BEDROCK_CHAT_MODEL_ID", "us.anthropic.claude-sonnet-4-6"), check_generation),
    ("嵌入", os.environ.get("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0"), check_embedding),
]


def check_local() -> None:
    """可选：验证本地开源模型能加载（重排 bge-reranker、可选 bge-m3 嵌入）。
    仅在需要本地/离线路径时跑；首次会下载权重，较慢。"""
    print("-" * 72)
    try:
        from sentence_transformers import CrossEncoder  # noqa: F401
        print("[本地] sentence-transformers 可导入 ✅（bge-reranker-v2-m3 首次调用时下载）")
    except Exception as e:  # noqa: BLE001
        print(f"[本地] sentence-transformers 不可用 ⚠️：{e}")
    try:
        import langchain_qdrant  # noqa: F401
        import qdrant_client     # noqa: F401
        print("[本地] qdrant-client / langchain-qdrant 可导入 ✅")
    except Exception as e:  # noqa: BLE001
        print(f"[本地] Qdrant 依赖缺失 ⚠️：{e}")


def main() -> int:
    print(f"Region : {REGION}")
    print(f"Account: {ACCOUNT_ID}")
    print("=" * 72)
    all_ok = True
    for category, model_id, fn in MODELS:
        ok, detail = fn(model_id)
        all_ok &= ok
        print(f"[{category}] {model_id:40s} {detail}")
    print("=" * 72)
    print("结果：Bedrock 模型全部可用 ✅" if all_ok else "结果：有 Bedrock 模型不可用 ❌（见上方）")
    if os.environ.get("CHECK_LOCAL"):
        check_local()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
