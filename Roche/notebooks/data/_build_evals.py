"""
Track B evaluation builder.

Reads the Lab 1 Chinese FAQ docs and Lab 3 bilingual docs (all in
notebooks/data/) and writes three JSON evaluation files used by Lab 3,
Lab 8 and Lab 11:

  - eval_30.json    : 30-question regression set over the Chinese FAQ
  - eval_lab3.json  : 20-question cross-lingual retrieval set
  - bad_cases.json  : 10 hand-curated bad-case examples

ground_truth_doc_ids strictly match the YAML frontmatter `doc_id` of the
real source files (which equals the file stem). Question texts are
hand-written to mimic real, slightly noisy customer phrasing.

Usage:
    python3 _build_evals.py
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Sanity check: every doc_id we reference must really exist on disk.
# ---------------------------------------------------------------------------
EXPECTED_DOCS = {
    # Lab 1 FAQ (zh)
    "returns":            DATA_DIR / "faq" / "returns.md",
    "shipping":           DATA_DIR / "faq" / "shipping.md",
    "membership":         DATA_DIR / "faq" / "membership.md",
    "payment":            DATA_DIR / "faq" / "payment.md",
    # Lab 3 cn products
    "iphone_15_pro_max":  DATA_DIR / "m4" / "cn_products" / "iphone_15_pro_max.md",
    "macbook_pro_m3":     DATA_DIR / "m4" / "cn_products" / "macbook_pro_m3.md",
    "galaxy_s24_ultra":   DATA_DIR / "m4" / "cn_products" / "galaxy_s24_ultra.md",
    "galaxy_buds3_pro":   DATA_DIR / "m4" / "cn_products" / "galaxy_buds3_pro.md",
    "sony_wh1000xm5":     DATA_DIR / "m4" / "cn_products" / "sony_wh1000xm5.md",
    "dji_mini4_pro":      DATA_DIR / "m4" / "cn_products" / "dji_mini4_pro.md",
    "anker_powercore":    DATA_DIR / "m4" / "cn_products" / "anker_powercore.md",
    "thinkpad_x1_carbon": DATA_DIR / "m4" / "cn_products" / "thinkpad_x1_carbon.md",
    # Lab 3 en policies
    "return_policy_us":   DATA_DIR / "m4" / "en_policies" / "return_policy_us.md",
    "return_policy_jp":   DATA_DIR / "m4" / "en_policies" / "return_policy_jp.md",
    "return_policy_kr":   DATA_DIR / "m4" / "en_policies" / "return_policy_kr.md",
    "shipping_global":    DATA_DIR / "m4" / "en_policies" / "shipping_global.md",
    "warranty_apple":     DATA_DIR / "m4" / "en_policies" / "warranty_apple.md",
    "warranty_samsung":   DATA_DIR / "m4" / "en_policies" / "warranty_samsung.md",
    "duty_and_tax":       DATA_DIR / "m4" / "en_policies" / "duty_and_tax.md",
    "repair_service":     DATA_DIR / "m4" / "en_policies" / "repair_service.md",
}


def _check_docs_exist() -> None:
    missing = [d for d, p in EXPECTED_DOCS.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Required source docs not found: " + ", ".join(missing)
        )


def _validate_doc_ids(items: list[dict], key: str) -> None:
    """Ensure every doc_id referenced by an eval item exists on disk."""
    for it in items:
        for did in it.get(key, []):
            if did not in EXPECTED_DOCS:
                raise ValueError(f"Unknown doc_id '{did}' in item {it}")


# ---------------------------------------------------------------------------
# eval_30.json — 30-question Chinese FAQ regression set
# ---------------------------------------------------------------------------
EVAL_30: list[dict] = [
    # ---------- 18 × faq_simple ----------
    {
        "qid": "Q01",
        "question": "你们家退货期限是多少天啊？我刚收到货",
        "ground_truth": "签收后 7 天内可申请无理由退换，前提是商品没人为损坏、配件齐全、包装完好。",
        "expected_doc_ids": ["returns"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q02",
        "question": "Buds3 Pro 已经拆封了还能退吗",
        "ground_truth": "入耳式耳机（如 Galaxy Buds3 Pro、AirPods Pro 2）出于卫生原因，一旦拆封就不支持无理由退货。",
        "expected_doc_ids": ["returns"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q03",
        "question": "iPhone 激活了还能退款不",
        "ground_truth": "手机激活后默认进入换货流程，不再退款；若属 DOA（开箱即损），48 小时内可申请原厂换新。",
        "expected_doc_ids": ["returns"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q04",
        "question": "海淘的东西退货大概要多久，关税能退吗？",
        "ground_truth": "海淘商品退货整个流程一般 10-14 天，关税不予退还。",
        "expected_doc_ids": ["returns"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q05",
        "question": "买 MacBook 送的 HUB 退货要一起寄回去吗",
        "ground_truth": "买 MacBook Pro 送的 Type-C HUB 等赠品需要一起寄回，否则会按市场价扣款。",
        "expected_doc_ids": ["returns"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q06",
        "question": "下单默认走啥快递呀",
        "ground_truth": "国内默认顺丰，部分偏远地区走京东或邮政 EMS；手机类默认顺丰陆运 + 保价。",
        "expected_doc_ids": ["shipping"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q07",
        "question": "几点之前付款能当天发货？",
        "ground_truth": "工作日下午 4 点前付款的当天发出，4 点以后顺延到第二天。",
        "expected_doc_ids": ["shipping"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q08",
        "question": "日本仓直邮一般几天到呀",
        "ground_truth": "日本仓直邮通常 10-15 个工作日，含清关；爆仓季会延长 3-5 天。",
        "expected_doc_ids": ["shipping"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q09",
        "question": "我西藏那边收件，要加运费么",
        "ground_truth": "新疆、西藏、内蒙部分地区、海南有偏远附加费，下单时系统会自动提示，时效也会多 2-3 天。",
        "expected_doc_ids": ["shipping"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q10",
        "question": "国内运费有没有满多少包邮",
        "ground_truth": "国内订单满 99 元包邮，未满 99 元起步运费 8 元。",
        "expected_doc_ids": ["shipping"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q11",
        "question": "买无人机能放菜鸟驿站吗",
        "ground_truth": "DJI Mini 4 Pro 等高价值商品默认必须本人签收，不放驿站。",
        "expected_doc_ids": ["shipping"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q12",
        "question": "你们家会员一共分几个等级？",
        "ground_truth": "会员分四个等级：普通会员、银卡、金卡、黑卡。",
        "expected_doc_ids": ["membership"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q13",
        "question": "升银卡要消费多少",
        "ground_truth": "年累计消费满 5000 元升银卡，满 20000 升金卡，满 80000 升黑卡。",
        "expected_doc_ids": ["membership"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q14",
        "question": "积分能抵多少钱啊？最多抵几成？",
        "ground_truth": "1 积分 = 0.01 元，下单时最高可抵扣订单金额的 30%。",
        "expected_doc_ids": ["membership"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q15",
        "question": "你们会员日是哪天",
        "ground_truth": "每月 8 号是会员日，全场叠加 95 折券，金卡及以上还有专属满减。",
        "expected_doc_ids": ["membership"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q16",
        "question": "支持 Apple Pay 吗 还有啥支付方式",
        "ground_truth": "支持微信支付、支付宝、银联（含云闪付）、Apple Pay 以及招行/建行/工行的信用卡分期，跨境订单还支持 PayPal。",
        "expected_doc_ids": ["payment"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q17",
        "question": "iPhone 15 Pro Max 能 12 期免息吗",
        "ground_truth": "MacBook Pro M3、iPhone 15 Pro Max 等商品经常做 12 期免息活动，下单页会标注「免息」字样，具体以下单时实际显示为准。",
        "expected_doc_ids": ["payment"],
        "category": "faq_simple",
        "lang": "zh",
    },
    {
        "qid": "Q18",
        "question": "退款多久能到账啊",
        "ground_truth": "微信、支付宝原路退回 1-3 个工作日；信用卡 3-7 个工作日；分期付款按已分期数依次退回。",
        "expected_doc_ids": ["payment"],
        "category": "faq_simple",
        "lang": "zh",
    },

    # ---------- 5 × faq_cross_doc ----------
    {
        "qid": "Q19",
        "question": "想退个东西，寄回的时候用啥快递？要不要付邮费？",
        "ground_truth": "寄回推荐顺丰（不接收到付）；非质量问题邮费由客户承担，质量问题则由商家承担来回运费。",
        "expected_doc_ids": ["returns", "shipping"],
        "category": "faq_cross_doc",
        "lang": "zh",
    },
    {
        "qid": "Q20",
        "question": "海淘订单不想要了，关税那部分还能退回来不",
        "ground_truth": "跨境订单退款只退商品款和已支付的运费，关税已经交给海关，不予退还。",
        "expected_doc_ids": ["returns", "payment"],
        "category": "faq_cross_doc",
        "lang": "zh",
    },
    {
        "qid": "Q21",
        "question": "金卡折扣能跟优惠券一起用么",
        "ground_truth": "代金券和优惠券一般不能叠加，但会员折扣可以叠加优惠券；不能与满减券同时使用，下单时系统会自动算最优组合。",
        "expected_doc_ids": ["membership", "payment"],
        "category": "faq_cross_doc",
        "lang": "zh",
    },
    {
        "qid": "Q22",
        "question": "日本直邮的耳机如果质量有问题怎么退，时效大概多久？",
        "ground_truth": "质量问题运费由商家承担，跨境订单退货流程比国内慢 5-7 天，整体一般 10-14 天；耳机若已拆封不支持无理由退货，但质量问题仍可走质保。",
        "expected_doc_ids": ["returns", "shipping"],
        "category": "faq_cross_doc",
        "lang": "zh",
    },
    {
        "qid": "Q23",
        "question": "MacBook 这种贵重的商品发货保价吗，万一丢了怎么办？",
        "ground_truth": "单价 3000 元以上的商品（如 MacBook Pro M3、ThinkPad X1 Carbon）默认买保价，保价费由商家承担；保价订单按申报金额理赔，未保价按快递公司标准（一般 7 倍运费）。",
        "expected_doc_ids": ["shipping", "returns"],
        "category": "faq_cross_doc",
        "lang": "zh",
    },

    # ---------- 3 × out_of_kb ----------
    {
        "qid": "Q24",
        "question": "iPhone 15 Pro Max 的电池容量是多少 mAh？",
        "ground_truth": "知识库没有该信息，应请用户查阅官方规格。",
        "expected_doc_ids": [],
        "category": "out_of_kb",
        "lang": "zh",
    },
    {
        "qid": "Q25",
        "question": "MacBook Pro M3 的 SSD 顺序读写速度具体多少 MB/s",
        "ground_truth": "知识库没有该信息，应请用户查阅官方规格。",
        "expected_doc_ids": [],
        "category": "out_of_kb",
        "lang": "zh",
    },
    {
        "qid": "Q26",
        "question": "你们 400 客服电话每天几点到几点能打通？",
        "ground_truth": "知识库没有该信息，应请用户查阅官方规格或客服公告。",
        "expected_doc_ids": [],
        "category": "out_of_kb",
        "lang": "zh",
    },

    # ---------- 2 × numeric ----------
    {
        "qid": "Q27",
        "question": "我下单 27 天了，现在退还来得及吗？",
        "ground_truth": "27 天已经超过 7 天无理由和 15 天质量问题退换的窗口；超过 15 天但仍在保修期内的只能走维修流程，不再退款。",
        "expected_doc_ids": ["returns"],
        "category": "numeric",
        "lang": "zh",
    },
    {
        "qid": "Q28",
        "question": "想升黑卡的话一年得花多少钱才行",
        "ground_truth": "黑卡需要年累计消费满 80000 元自动升级，也支持邀请制。",
        "expected_doc_ids": ["membership"],
        "category": "numeric",
        "lang": "zh",
    },

    # ---------- 2 × multi_step ----------
    {
        "qid": "Q29",
        "question": "买的 Sony WH-1000XM5 拆封了不能退，作为金卡用户有没有什么补偿方案？",
        "ground_truth": "拆封耳机原则上不支持无理由退货；但金卡享每月一次免费上门取件维修和优先客服通道，可以走质量问题报修或客服协商；同时下单按金卡 9 折并按 1.5 倍积分累计。",
        "expected_doc_ids": ["returns", "membership"],
        "category": "multi_step",
        "lang": "zh",
    },
    {
        "qid": "Q30",
        "question": "海淘的 Galaxy S24 Ultra 想退，关税能退吗？退款大概多久到我支付宝？",
        "ground_truth": "跨境订单的关税不予退还，只退商品款和已支付运费；支付宝原路退款一般 1-3 个工作日到账，整体退货流程 10-14 天。",
        "expected_doc_ids": ["returns", "payment"],
        "category": "multi_step",
        "lang": "zh",
    },
]


# ---------------------------------------------------------------------------
# eval_lab3.json — 20-question bilingual retrieval set
# ---------------------------------------------------------------------------
EVAL_LAB3: list[dict] = [
    # ---- 6 × same_lingual zh -> zh (cn_products) ----
    {
        "qid": "L3-01",
        "question": "iPhone 15 Pro Max 主摄是多少 MP？",
        "lang_q": "zh",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["iphone_15_pro_max"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-02",
        "question": "MacBook Pro M3 14 寸最长能用多少小时？",
        "lang_q": "zh",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["macbook_pro_m3"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-03",
        "question": "Galaxy S24 Ultra 长焦最高能放大多少倍？",
        "lang_q": "zh",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["galaxy_s24_ultra"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-04",
        "question": "Sony WH-1000XM5 开降噪能听多久？",
        "lang_q": "zh",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["sony_wh1000xm5"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-05",
        "question": "DJI Mini 4 Pro 整机重量是多少？需不需要登记？",
        "lang_q": "zh",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["dji_mini4_pro"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-06",
        "question": "ThinkPad X1 Carbon Gen 12 用的什么 CPU？",
        "lang_q": "zh",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["thinkpad_x1_carbon"],
        "category": "same_lingual",
    },

    # ---- 6 × same_lingual en -> en (en_policies) ----
    {
        "qid": "L3-07",
        "question": "What is the return window for orders shipped to the United States?",
        "lang_q": "en",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["return_policy_us"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-08",
        "question": "How many days is the cooling-off period for mail-order purchases in Japan?",
        "lang_q": "en",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["return_policy_jp"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-09",
        "question": "Korea VAT refund on returns – how does that work?",
        "lang_q": "en",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["return_policy_kr"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-10",
        "question": "Which carriers do you use for international shipping?",
        "lang_q": "en",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["shipping_global"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-11",
        "question": "How much is the AppleCare+ screen damage fee for iPhone 15 Pro Max?",
        "lang_q": "en",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["warranty_apple"],
        "category": "same_lingual",
    },
    {
        "qid": "L3-12",
        "question": "What is Samsung's battery warranty period for Galaxy phones?",
        "lang_q": "en",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["warranty_samsung"],
        "category": "same_lingual",
    },

    # ---- 4 × cross_lingual zh -> en (zh question, en policy) ----
    {
        "qid": "L3-13",
        "question": "在美国怎么退货，期限是多久？",
        "lang_q": "zh",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["return_policy_us"],
        "category": "cross_lingual",
    },
    {
        "qid": "L3-14",
        "question": "发到欧盟的订单大概要多少天？",
        "lang_q": "zh",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["shipping_global"],
        "category": "cross_lingual",
    },
    {
        "qid": "L3-15",
        "question": "iPhone 进口到欧盟大概要交多少税？",
        "lang_q": "zh",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["duty_and_tax"],
        "category": "cross_lingual",
    },
    {
        "qid": "L3-16",
        "question": "MacBook Pro 14 寸 M3 换电池要多少钱啊？",
        "lang_q": "zh",
        "lang_doc": "en",
        "ground_truth_doc_ids": ["repair_service"],
        "category": "cross_lingual",
    },

    # ---- 4 × cross_lingual en -> zh (en question, zh product) ----
    {
        "qid": "L3-17",
        "question": "What is the battery life of Sony WH-1000XM5 with ANC on?",
        "lang_q": "en",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["sony_wh1000xm5"],
        "category": "cross_lingual",
    },
    {
        "qid": "L3-18",
        "question": "How light is the DJI Mini 4 Pro – is it under 250 grams?",
        "lang_q": "en",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["dji_mini4_pro"],
        "category": "cross_lingual",
    },
    {
        "qid": "L3-19",
        "question": "ThinkPad X1 Carbon Gen 12 battery life on a single charge?",
        "lang_q": "en",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["thinkpad_x1_carbon"],
        "category": "cross_lingual",
    },
    {
        "qid": "L3-20",
        "question": "What is the IP rating of Galaxy Buds3 Pro? Can I run with them in the rain?",
        "lang_q": "en",
        "lang_doc": "zh",
        "ground_truth_doc_ids": ["galaxy_buds3_pro"],
        "category": "cross_lingual",
    },
]


# ---------------------------------------------------------------------------
# bad_cases.json — 10 hand-curated bad cases
# ---------------------------------------------------------------------------
BAD_CASES: list[dict] = [
    # ---- 3 × retrieval (correct doc was skipped) ----
    {
        "id": "BC-001",
        "query": "退货期限是多少天？",
        "bad_answer": "默认快递走顺丰，工作日 4 点前下单当天发货。",
        "expected": "签收后 7 天内可申请无理由退换，前提是商品没人为损坏、配件齐全、包装完好（来源：returns）。",
        "category": "retrieval",
        "evidence": "Top-K 检索召回的是 shipping，应该召回 returns；问题里只出现『退货』关键词，但与 shipping 中『退货寄回走什么快递』段落语义重叠，导致 BM25 命中错文档。",
        "hint": "讲师可以借此演示『关键词命中 ≠ 语义命中』，引出向量检索 + 重排（rerank）的必要性。",
    },
    {
        "id": "BC-002",
        "query": "Anker PowerCore 容量是多少？",
        "bad_answer": "MacBook Pro M3 容量可选 512GB 到 8TB。",
        "expected": "Anker PowerCore 24000 PD 140W 容量是 24000mAh / 86.4Wh，接近民航 100Wh 上限（来源：anker_powercore）。",
        "category": "retrieval",
        "evidence": "Top-K 召回了 macbook_pro_m3 而不是 anker_powercore；原因可能是『容量』一词在 MacBook 文档里以存储容量形式高频出现，主导了相似度。",
        "hint": "演示 query 中的歧义词（容量 = 电池容量 vs 存储容量）会导致检索漂移，可用产品名词 NER + 强约束 filter 修复。",
    },
    {
        "id": "BC-003",
        "query": "Galaxy Buds3 Pro 防水等级到底多少？",
        "bad_answer": "Galaxy S24 Ultra 是 IP68 防尘防水，可放心日常使用。",
        "expected": "Galaxy Buds3 Pro 是 IP57 防尘防水，防汗水但激烈运动建议搭配耳挂（来源：galaxy_buds3_pro）。",
        "category": "retrieval",
        "evidence": "Top-K 召回了 galaxy_s24_ultra（同品牌、同关键词『Galaxy』『防水』），跳过了 galaxy_buds3_pro。",
        "hint": "同品牌多产品语义高度相似时，BM25 / dense embedding 都容易混淆；引出 metadata filter（按型号过滤）或 hybrid + cross-encoder rerank。",
    },

    # ---- 4 × generation (right doc retrieved, wrong answer) ----
    {
        "id": "BC-004",
        "query": "你们家退货期限多久？",
        "bad_answer": "我们的退货期限是 14 天，签收后 14 天内都可以申请。",
        "expected": "中文 FAQ 的政策是签收后 7 天内可无理由退换，15 天内可申请质量问题退换；14 天是美国 return_policy_us 的窗口，不应套用到 CN。",
        "category": "generation",
        "evidence": "检索结果包含 returns（CN）和 return_policy_us（US，14 天）；LLM 错误地引用了 US 政策回答中文用户。必要片段在检索结果中。",
        "hint": "经典『多文档冲突』问题。演示 prompt 中要让模型显式选择匹配 region 的文档，或在 retrieval 时基于用户语言/地区做 metadata filter。",
    },
    {
        "id": "BC-005",
        "query": "金卡需要多少累计消费才能升上去？",
        "bad_answer": "金卡需要年累计消费满 50000 元才能升级。",
        "expected": "金卡门槛是年累计消费满 20000 元（来源：membership Q1）。",
        "category": "generation",
        "evidence": "Top-K 检索召回了 membership 文档，且文档明确写明『5000 银卡 / 20000 金卡 / 80000 黑卡』。LLM 编造了 50000 这个数字。",
        "hint": "演示 numeric hallucination；可加『请引用原文片段』『不知道就说不知道』的 system prompt 约束并配合 grounding 检查。",
    },
    {
        "id": "BC-006",
        "query": "PowerCore 24000 这块充电宝能带上飞机吗？",
        "bad_answer": "不能，超过民航 100Wh 限制了，要托运也不行。",
        "expected": "PowerCore 24000 PD 140W 容量为 86.4Wh，低于民航 100Wh 上限，可以随身上飞机但需要在机场报备（来源：anker_powercore）。",
        "category": "generation",
        "evidence": "检索结果包含 anker_powercore，文档原文是 86.4Wh、低于 100Wh；LLM 把『接近 100Wh 上限』误读成超过。必要片段在检索结果中。",
        "hint": "演示『细节方向反向』错误（low/below 被误识别为 over）；引出 self-consistency check 或抽取式 QA 二次校对。",
    },
    {
        "id": "BC-007",
        "query": "日本仓发货到我手上一般要几天？",
        "bad_answer": "日本仓直邮一般 3-5 天到。",
        "expected": "日本仓直邮 10-15 个工作日（含清关），爆仓季会再多 3-5 天（来源：shipping）。",
        "category": "generation",
        "evidence": "检索结果包含 shipping 文档，正确答案明确写在 Q3。LLM 把国内顺丰 3-5 天的时效错套到日本仓。",
        "hint": "经典『跨段落串读』错误。演示 chunk 重叠 + reference 引用的重要性，让模型在引用具体段落时不易跨段拼接。",
    },

    # ---- 3 × kb_missing ----
    {
        "id": "BC-008",
        "query": "iPhone 15 Pro Max 的电池容量是多少 mAh？",
        "bad_answer": "iPhone 15 Pro Max 电池容量约 4422 mAh。",
        "expected": "知识库的 iphone_15_pro_max 文档中没有给出 mAh 数字，FAQ 也明确说『电池容量本身的标称值我们 FAQ 里不会写，请以官网规格表为准』。正确做法是回复『以官方规格为准』。",
        "category": "kb_missing",
        "evidence": "确实不在 KB 中。检索召回 iphone_15_pro_max + returns，但两份文档都未提及 mAh 数字。",
        "hint": "演示 hallucination 高发场景：用户用具体单位提问 → 模型为了『有用』倾向于编。引出『不知道就说不知道』的 prompt + 阈值兜底。",
    },
    {
        "id": "BC-009",
        "query": "MacBook Pro M3 的 SSD 顺序读取速度具体是多少 MB/s？",
        "bad_answer": "MacBook Pro M3 的 SSD 顺序读取速度约 7400 MB/s。",
        "expected": "知识库 macbook_pro_m3 文档只列出了 SSD 容量范围（512GB-8TB），没有给具体读写速度数字。正确做法是回复『请以官方规格为准』。",
        "category": "kb_missing",
        "evidence": "信息确实不在 KB 中。文档只描述了容量、接口和续航，未涉及 SSD 性能数字。",
        "hint": "另一个 hallucination 演示。可让学员对比『有 mAh』『有 MB/s』两类外部数字的检测策略，并在 RAG 评测里把它们标成 out_of_kb。",
    },
    {
        "id": "BC-010",
        "query": "DJI Mini 4 Pro 在欧盟的 C-class 标识是 C0 还是 C1？",
        "bad_answer": "DJI Mini 4 Pro 在欧盟标 C0 类。",
        "expected": "知识库 dji_mini4_pro 文档只写了重量 <249g 与 CE 区域图传 10 公里，没有提到具体 EU C-class 等级码。正确做法是回复『以官方规格 / 民航局公告为准』。",
        "category": "kb_missing",
        "evidence": "EU C-class 字符在所有产品 / 政策文档中均未出现；属于真正的 KB 缺口。",
        "hint": "演示『监管细节』类问题极易超出 KB 覆盖。可引申到 RAG 系统加 『不在 KB 内时调用 web search』 的 fallback 设计。",
    },
]


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------
def _validate_eval_30(items: list[dict]) -> None:
    assert len(items) == 30, f"eval_30 should have 30 items, got {len(items)}"
    cat_counts = {
        "faq_simple":    18,
        "faq_cross_doc": 5,
        "out_of_kb":     3,
        "numeric":       2,
        "multi_step":    2,
    }
    actual = {}
    for it in items:
        for k in ["qid", "question", "ground_truth", "expected_doc_ids", "category", "lang"]:
            assert k in it, f"missing key '{k}' in {it}"
        actual[it["category"]] = actual.get(it["category"], 0) + 1
        if it["category"] == "out_of_kb":
            assert it["expected_doc_ids"] == [], f"out_of_kb must have empty doc_ids: {it}"
    for c, n in cat_counts.items():
        assert actual.get(c, 0) == n, f"category {c}: expected {n}, got {actual.get(c, 0)}"
    _validate_doc_ids(items, "expected_doc_ids")


def _validate_eval_lab3(items: list[dict]) -> None:
    assert len(items) == 20, f"eval_lab3 should have 20 items, got {len(items)}"
    lang_counts = {}
    for it in items:
        for k in ["qid", "question", "lang_q", "lang_doc",
                  "ground_truth_doc_ids", "category"]:
            assert k in it, f"missing key '{k}' in {it}"
        lang_counts[(it["lang_q"], it["lang_doc"])] = (
            lang_counts.get((it["lang_q"], it["lang_doc"]), 0) + 1
        )
    expected_lang = {
        ("zh", "zh"): 6,
        ("en", "en"): 6,
        ("zh", "en"): 4,
        ("en", "zh"): 4,
    }
    for k, v in expected_lang.items():
        assert lang_counts.get(k, 0) == v, (
            f"lang pair {k}: expected {v}, got {lang_counts.get(k, 0)}"
        )
    _validate_doc_ids(items, "ground_truth_doc_ids")


def _validate_bad_cases(items: list[dict]) -> None:
    assert len(items) == 10, f"bad_cases should have 10 items, got {len(items)}"
    cat_counts = {"retrieval": 3, "generation": 4, "kb_missing": 3}
    actual = {}
    for it in items:
        for k in ["id", "query", "bad_answer", "expected",
                  "category", "evidence", "hint"]:
            assert k in it, f"missing key '{k}' in {it}"
        actual[it["category"]] = actual.get(it["category"], 0) + 1
    for c, n in cat_counts.items():
        assert actual.get(c, 0) == n, f"category {c}: expected {n}, got {actual.get(c, 0)}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    _check_docs_exist()

    _validate_eval_30(EVAL_30)
    _validate_eval_lab3(EVAL_LAB3)
    _validate_bad_cases(BAD_CASES)

    out_files = {
        DATA_DIR / "eval_30.json":     EVAL_30,
        DATA_DIR / "eval_lab3.json":   EVAL_LAB3,
        DATA_DIR / "bad_cases.json":   BAD_CASES,
    }
    for path, payload in out_files.items():
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"wrote {path} ({len(payload)} items)")


if __name__ == "__main__":
    main()
