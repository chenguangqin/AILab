# Workshop联调清单

## EC2基础环境

- Python 3.12
- 能访问PyPI或预装wheelhouse
- 可访问Bedrock Runtime
- 可访问共享Langfuse
- 每人独立工作目录和虚拟环境

## 安装

```bash
cd Roche/RAGAgent
bash scripts/bootstrap.sh
cp .env.example .env
```

RAGAS依赖较重，建议预装到AMI；临时安装使用：

```bash
INSTALL_RAGAS=1 bash scripts/bootstrap.sh
```

项目将RAGAS固定在0.3系列，并将其依赖的`langchain-community`固定在0.3系列。不要在课堂现场单独升级这些包；评估框架升级必须先通过离线兼容性测试。

## 联调顺序

1. `.venv/bin/pytest`
2. 配置准确的Bedrock Model ID
3. `.venv/bin/pytest -m bedrock`
4. 配置Langfuse三项凭证
5. 同步Dataset并运行E0
6. 确认Claude/Titan调用、Token和Trace
7. 30台EC2并发运行小样本，观察限流

## 不稳定依赖的兜底

- Bedrock不可用：切换Fake/Replay；
- Langfuse不可用：写入JSON Trace；
- RAGAS不可用：保留确定性指标；
- PyPI不可用：使用预制AMI或wheelhouse；
- OCR不可用：使用预生成OCR JSON。
