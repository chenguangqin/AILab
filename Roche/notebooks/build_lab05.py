#!/usr/bin/env python3
"""生成 lab_05_multimodal.ipynb（弱化多模态 · 演示型 · 检验科）。
程序化生成，避免手写 JSON 转义。修改后重跑覆盖。"""
from __future__ import annotations
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md("""# Lab 5 · 多模态轻量演示 — 读懂一张手填温度记录表

|     |     |
| --- | --- |
| **模块** | M6 · 多模态 RAG（**弱化 · 演示型**） |
| **时长** | 20 min |
| **形态** | 演示型（不建多模态索引） |
| **关键产出** | "LLM 读图抽结构化 + 程序规则判读"的体感 |

> **本 Lab 刻意弱化**（客户要求弱化多模态、强化复杂文档，见 M3）。这里只演示一件事：
> **识别交给 AI、合规判定留在可审计的程序规则里**——这正是全课的主张。"""))

cells.append(md("""## 1. 背景

检验科有大量非文本原始记录：手填温度记录表、仪器报警截图、报告单扫描件。纯文本 RAG 读不到它们。

本演示：用 **Bedrock Claude 的视觉能力**读一张（模拟的）冰箱温度记录表，抽出每行 `{日期, 温度, 判定}`，再用**程序规则**校验"温度超阈值却被标合格"的不符合项。

> 真实场景是手写字迹（更难，建议 PaddleOCR 本地方案 + 人工复核）。这里用清晰打印表做演示，聚焦"识别 vs 判定"的分工。"""))

cells.append(md("""## 2. 环境准备
> - Bedrock 已开通**视觉能力的 Claude**（`gen_main` = Sonnet 4.6 支持图片输入）
> - `pip install pillow boto3`
> - 本 cell 会用 PIL 现场生成一张模拟温度记录表到 `data/multimodal/`"""))

cells.append(code('''import os, io, json, base64
from pathlib import Path
import boto3
from PIL import Image, ImageDraw
from IPython.display import Image as IPyImage, display

from common import REGION, MODEL_IDS, DATA_DIR

IMG_DIR = DATA_DIR / "multimodal"
IMG_DIR.mkdir(parents=True, exist_ok=True)
IMG_PATH = IMG_DIR / "fridge_temp_log.png"

# 现场生成一张"模拟冰箱温度记录表"（用 ASCII/数字，规避字体缺失；真实为中文手填）
# 阈值：冷藏冰箱 <= 5.0 ℃ 为合格。故意埋一行 7.0℃ 却标 OK 的不符合项。
def make_mock_log(path):
    W, H, rows = 620, 260, [
        ("Date",   "Temp(C)", "Judge", "By"),
        ("06-01",  "4.2",     "OK",    "N01"),
        ("06-02",  "3.8",     "OK",    "N02"),
        ("06-03",  "7.0",     "OK",    "N01"),   # <-- 异常：7.0 超阈值却判 OK
        ("06-04",  "4.9",     "OK",    "N03"),
        ("06-05",  "5.0",     "OK",    "N02"),
    ]
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    d.text((16, 10), "Fridge Temperature Log (threshold <= 5.0 C)", fill="black")
    x0, y0, rh = 16, 40, 34
    cols = [0, 140, 300, 440, 560]
    for r, row in enumerate(rows):
        y = y0 + r * rh
        d.line([(x0, y), (W-16, y)], fill="black")
        for c, cell in enumerate(row):
            d.text((x0 + cols[c] + 6, y + 8), str(cell), fill="black")
    d.line([(x0, y0 + len(rows)*rh), (W-16, y0 + len(rows)*rh)], fill="black")
    img.save(path)

if not IMG_PATH.exists():
    make_mock_log(IMG_PATH)
print("图片：", IMG_PATH)
display(IPyImage(filename=str(IMG_PATH)))'''))

cells.append(md("""## 3. 步骤 1 — 用 Claude 视觉读表，抽成结构化数据

用 Bedrock Converse 传图 + 指令，让模型把表读成 JSON。**注意**：让它只做"识别/转录"，不做合规判定——判定留给下一步的程序规则。"""))

cells.append(code('''brt = boto3.client("bedrock-runtime", region_name=REGION)
img_bytes = IMG_PATH.read_bytes()

prompt = (
    "这是一张冰箱温度记录表的图片。请只做转录，不要做任何合规判断。"
    "把每一行数据行抽成 JSON 数组，字段：date, temp（数字）, judge, by。"
    "只输出 JSON，不要多余文字。"
)
resp = brt.converse(
    modelId=MODEL_IDS["gen_main"],
    messages=[{"role": "user", "content": [
        {"text": prompt},
        {"image": {"format": "png", "source": {"bytes": img_bytes}}},
    ]}],
    inferenceConfig={"maxTokens": 800, "temperature": 0.0},
)
raw = resp["output"]["message"]["content"][0]["text"]
print("模型原始输出：\\n", raw)

# 容错解析 JSON（去掉可能的```代码围栏）
txt = raw.strip().strip("`")
if txt.startswith("json"):
    txt = txt[4:]
start, end = txt.find("["), txt.rfind("]")
rows = json.loads(txt[start:end+1]) if start >= 0 else []
print("\\n解析出的行：", rows)'''))

cells.append(md("""## 4. 步骤 2 — 程序规则判读（可审计）

识别完，**判定不交给 LLM**，交给确定性的程序规则：冷藏冰箱温度 > 5.0℃ 却被标记为合格 → 不符合项。规则显式、可留痕、可审计。"""))

cells.append(code('''THRESHOLD = 5.0
findings = []
for r in rows:
    try:
        temp = float(r.get("temp"))
    except (TypeError, ValueError):
        continue
    judged_ok = str(r.get("judge", "")).upper() in ("OK", "合格", "PASS")
    if temp > THRESHOLD and judged_ok:
        findings.append({**r, "issue": f"温度 {temp}℃ 超阈值({THRESHOLD}℃)却判合格"})

print("不符合项：")
for f in findings:
    print("  ⚠️", f)
if not findings:
    print("  （未发现不符合项）")'''))

cells.append(md("""## 5. 复盘

- **分工**：AI 负责"把图读成结构化数据"（识别），程序规则负责"判合不合规"（判定）。判定逻辑显式、可留痕、可审计——这正是检验科/GxP 要的。
- **别把判定交给 LLM**：温度是否超标、是否该判合格，是确定性规则，交给程序更可靠、可追溯（呼应 M11 智能审核）。
- **手填字迹更难**：真实记录是手写，识别难度高；建议 **PaddleOCR（本地、中文强）+ 关键字段抽取 + 人工复核**，不追求全自动。

## 6. 扩展任务
1. **本地 OCR**：用 PaddleOCR 替代视觉大模型抽取字段，对比准确率与资源占用（on-prem 更现实）。
2. **报告单扫描件**：把一张报告单扫描件 OCR 成文本后走 M2 的文本 RAG——很多"多模态"需求本质是"扫描件→文本"。
3. **视觉 Embedding 索引**：用开源 CLIP/jina-clip 对一组镜检图建索引，做"以图搜图"，体会显存代价。
4. **判断卡**：对你们科室的非文本数据列一张"该 OCR / 该视觉 / 该人工"的分流表。"""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})
with open("lab_05_multimodal.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"✅ written lab_05_multimodal.ipynb  cells={len(cells)}")
