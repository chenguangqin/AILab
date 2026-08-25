#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建检验科知识图谱（Lab 9 GraphRAG 演示用）。

Schema
------
节点类型（每个节点带 node_type 属性）：
  * Item        检验项目（CREA/K/GLU/...）
  * Instrument  仪器（生化分析仪/血球分析仪/...）
  * Reagent     试剂
  * CriticalValue 危急值（阈值，挂在有危急值的项目下）
  * Interference  干扰/异常来源（溶血/脂血/吸样针堵塞/...）
  * QCRule      室内质控规则（Westgard）
  * SOP         科室 SOP（对应 data/kb 的 4 份文档）
  * Standard    外部标准（ISO 15189 / CNAS-RL01）

边类型（edge_type）：
  * MEASURED_BY       Item -> Instrument
  * USES_REAGENT      Item -> Reagent
  * HAS_CRITICAL_VALUE Item -> CriticalValue
  * AFFECTED_BY       Item -> Interference
  * GOVERNED_BY       Item -> SOP
  * HAS_FACTOR        Instrument -> Interference（仪器类因素）
  * MONITORED_BY      Instrument -> QCRule
  * DEFINED_IN        QCRule -> SOP(室内质控)
  * REF_STANDARD      SOP -> Standard

幂等：每次运行从零重建。
"""
from __future__ import annotations

import os
import pickle
from collections import Counter

import networkx as nx

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(DATA_DIR, "lab_graph.gpickle")

INSTRUMENTS = ["生化分析仪", "血球分析仪", "凝血分析仪", "化学发光免疫分析仪"]

# 仪器类因素（AFFECTED / HAS_FACTOR）
INSTRUMENT_FACTORS = {
    "生化分析仪": ["吸样针堵塞", "光学元件污染", "试剂针交叉污染"],
    "血球分析仪": ["鞘流异常", "计数小孔堵塞"],
    "凝血分析仪": ["光路老化"],
    "化学发光免疫分析仪": ["加样系统异常"],
}

# 标本/生物类干扰
SAMPLE_FACTORS = [
    "溶血", "脂血", "黄疸", "凝块", "采集量不足", "标本超时",
    "抗凝剂错误", "输液同侧采血", "血小板聚集",
]

QC_RULES = {
    "1_2s": "1 个质控值超过 ±2SD（警告）",
    "1_3s": "1 个质控值超过 ±3SD（失控·随机误差）",
    "2_2s": "连续 2 个质控值同侧超过 ±2SD（失控·系统误差）",
    "R_4s": "同批两水平极差超过 4SD（失控·随机误差）",
    "4_1s": "连续 4 个质控值同侧超过 ±1SD（失控·系统误差）",
    "10x":  "连续 10 个质控值在均值同侧（失控·趋势/漂移）",
}

SOPS = ["危急值管理", "室内质控", "标本采集与拒收", "报告审核与复检"]
STANDARDS = ["ISO 15189", "CNAS-RL01"]

# 检验项目：name, 仪器, 试剂, (危急值下限, 上限, 单位) 或 None, 干扰来源, 归属SOP
ITEMS = [
    ("CREA 肌酐",   "生化分析仪", "肌酐酶法试剂",  (None, 600, "μmol/L"),
     ["吸样针堵塞", "光学元件污染", "溶血"], "报告审核与复检"),
    ("K 血钾",      "生化分析仪", "钾电极试剂",    (2.8, 6.5, "mmol/L"),
     ["溶血", "抗凝剂错误", "输液同侧采血"], "危急值管理"),
    ("Na 血钠",     "生化分析仪", "钠电极试剂",    (120, 160, "mmol/L"),
     ["输液同侧采血"], "危急值管理"),
    ("Ca 血钙",     "生化分析仪", "钙比色试剂",    (1.6, 3.5, "mmol/L"),
     ["抗凝剂错误"], "危急值管理"),
    ("GLU 血糖",    "生化分析仪", "葡萄糖氧化酶试剂", (2.5, 22.2, "mmol/L"),
     ["标本超时", "输液同侧采血"], "标本采集与拒收"),
    ("ALT 谷丙转氨酶", "生化分析仪", "ALT 速率法试剂", None,
     ["溶血"], "报告审核与复检"),
    ("AST 谷草转氨酶", "生化分析仪", "AST 速率法试剂", None,
     ["溶血"], "报告审核与复检"),
    ("LDH 乳酸脱氢酶", "生化分析仪", "LDH 速率法试剂", None,
     ["溶血"], "报告审核与复检"),
    ("WBC 白细胞",  "血球分析仪", "溶血素试剂",    (1.0, 30.0, "×10⁹/L"),
     ["血小板聚集"], "报告审核与复检"),
    ("PLT 血小板",  "血球分析仪", "稀释液试剂",    (20, 1000, "×10⁹/L"),
     ["血小板聚集", "抗凝剂错误", "凝块"], "报告审核与复检"),
    ("HGB 血红蛋白", "血球分析仪", "溶血素试剂",   (50, 200, "g/L"),
     ["脂血", "溶血"], "危急值管理"),
    ("PT 凝血酶原时间", "凝血分析仪", "PT 试剂",   (None, 30, "s"),
     ["采集量不足", "凝块"], "标本采集与拒收"),
    ("TnI 肌钙蛋白", "化学发光免疫分析仪", "TnI 化学发光试剂", None,
     ["溶血"], "报告审核与复检"),
]


def build_graph() -> nx.DiGraph:
    G = nx.DiGraph()

    for ins in INSTRUMENTS:
        G.add_node(ins, node_type="Instrument", name=ins)
    for factor in set(SAMPLE_FACTORS) | {f for fs in INSTRUMENT_FACTORS.values() for f in fs}:
        G.add_node(factor, node_type="Interference", name=factor)
    for rid, desc in QC_RULES.items():
        G.add_node(rid, node_type="QCRule", name=rid, desc=desc)
    for sop in SOPS:
        G.add_node(sop, node_type="SOP", name=sop)
    for std in STANDARDS:
        G.add_node(std, node_type="Standard", name=std)

    # 仪器 -> 仪器类因素；仪器 -> 质控规则
    for ins, factors in INSTRUMENT_FACTORS.items():
        for f in factors:
            G.add_edge(ins, f, edge_type="HAS_FACTOR")
        for rid in QC_RULES:
            G.add_edge(ins, rid, edge_type="MONITORED_BY")

    # 质控规则 -> 定义于 室内质控 SOP
    for rid in QC_RULES:
        G.add_edge(rid, "室内质控", edge_type="DEFINED_IN")

    # SOP -> 引用标准
    for sop in SOPS:
        G.add_edge(sop, "ISO 15189", edge_type="REF_STANDARD")
    G.add_edge("室内质控", "CNAS-RL01", edge_type="REF_STANDARD")
    G.add_edge("报告审核与复检", "CNAS-RL01", edge_type="REF_STANDARD")

    # 项目节点及其边
    for name, ins, reagent, crit, factors, sop in ITEMS:
        G.add_node(name, node_type="Item", name=name)
        G.add_edge(name, ins, edge_type="MEASURED_BY")

        rnode = f"试剂:{reagent}"
        if rnode not in G:
            G.add_node(rnode, node_type="Reagent", name=reagent)
        G.add_edge(name, rnode, edge_type="USES_REAGENT")

        if crit is not None:
            low, high, unit = crit
            cv = f"危急值:{name}"
            G.add_node(cv, node_type="CriticalValue", name=cv,
                       low=low, high=high, unit=unit)
            G.add_edge(name, cv, edge_type="HAS_CRITICAL_VALUE")

        for f in factors:
            G.add_edge(name, f, edge_type="AFFECTED_BY")

        G.add_edge(name, sop, edge_type="GOVERNED_BY")

    return G


def report(G: nx.DiGraph) -> None:
    nc = Counter(d["node_type"] for _, d in G.nodes(data=True))
    ec = Counter(d["edge_type"] for _, _, d in G.edges(data=True))
    print(f"[graph] nodes total = {len(G.nodes)}")
    print(f"[graph] edges total = {len(G.edges)}")
    print("[graph] node types:", dict(nc))
    print("[graph] edge types:", dict(ec))


def main() -> None:
    G = build_graph()
    report(G)
    with open(OUT_PATH, "wb") as f:
        pickle.dump(G, f)
    print(f"[graph] saved -> {OUT_PATH} ({os.path.getsize(OUT_PATH)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
