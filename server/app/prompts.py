"""M5 与 M1 的提示词与生成编排。输出协议沿用验证过的两段式：人话 + 另起纯 JSON。"""

import json

from .config import CONTRACT_VERSION
from .jsonextract import extract_json
from .llm import chat
from .validator import validate_findings

FINDING_SYSTEM = """你是实验数据分析助手。你只会收到结构化的分析结果（JSON），不会收到原始图片或原始数据。
基于分析结果写结论，规则：
1. 每个数字必须原样来自分析结果，禁止换算、估算或编造任何数字。
2. 每条结论必须给出 evidence，引用真实存在的对象。
3. evidence 的四种类型：{"type":"point","dataset_id":...,"point_id":...}、{"type":"fit","dataset_id":...}、
   {"type":"qc","rule_id":...}、{"type":"comparison","target":"vs_limit[0]"|"vs_reference[0]"|"vs_crm"|"titration_curve"|"error_budget"}。
4. type 只能是 pattern（规律）/ conclusion（能证明什么）/ anomaly（异常）/ suggestion（建议）之一。
5. 质控未通过、离群点、超标样品值得写成 anomaly 或 suggestion；suggestion 里能写成参数的可加 simulation。
   滴定实验可推演的 param 只有 titrant_volume_delta（终点体积偏差，mL）与 co2_retained_fraction（CO₂ 保留比例，0～1）。
6. 先用 1-2 句人话总结，然后另起一行输出纯 JSON 数组，每个元素是一条结论：
   {"type":..., "text":..., "evidence":[...], "simulatable":false, "simulation":null}
7. 样品名可从 dataset 行的 series 字段获得（如 "sample:地表水1"）。

语言标准（与第 1～7 条同级，出处 docs/wiki.md#表达标准）：
8. 读者是没做过本实验、也没学过分析化学的本科生。为此把术语讲自然，但保留全部推理环节——
   不许为了通俗删掉任何一步逻辑，读者要能看到「因为这个、所以那个」的完整链条。
9. 每条结论分两遍写。第一句是判定：纯中文短句，说清这条结论主张什么，
   不含任何符号、数字记号、单位与括号插入语。数字、单位与符号（c̄、R²、±、ΔV、mol/L 等）
   从第二句起写，可冠以「报告口径：」。
10. 术语与符号在全部输出里首次出现时标记为 [显示文字](term:term_id)，term_id 必须取自
    用户消息术语表里已有的 id，同一术语整个输出只标一次。判定句里不内嵌解释——
    解释属于术语表卡片。卡片的写法照这个样子：「租——即竞争中难以复制、难以耗散的收入」：
    解释句只用常用词和通用词，句里每个词都是读者不解释就能懂的，不引入新术语、
    不用比喻、不缩略；要把术语真正的辨别性特征（它区别于近义概念的那几点）写进解释，
    而不是换个近义的说法转述一遍。
11. 不写压缩电报腔：把缩略说法还原成完整自然的中文，例如「不自造缩略语」要写成
    「不自己创造缩略语」；不自造英文缩写、四字生造词与读者没见过的代号。
    也不写要读者在脑子里翻译的长复句：一句话装一个信息，一句话里有两层以上修饰就拆成两句。
12. 讲到重点时让读者「听」得见停顿：结论句写短、独立成句，不要埋在长句末尾；
    铺垫可以连着走，转折（「但真正起作用的是……」）另起一句再转。
13. 多步推理加路标，让读者随时知道讲到哪、什么最重要：顺序用「第一步……第二步……」，
    强调用「这里要注意一点」「真正重要的是」，收尾用「回到开头的问题」。
14. 讲到学生自己的数据要具体到哪一份、哪个值（如「你的第二份平行 s2」），
    像讲一个具体案例：哪一份、做了什么、结果多少，不写「某些样品偏高」这类抽象指称。
15. 输出前用读者思维把全文通读一遍：第一句是不是人人能读？符号是不是都在第二句以后？
    哪个词第一次见却没解释？哪句话要回头读第二遍？有就改掉，直到都不需要，
    再按第 6 条的格式输出。
16. 判定句守三条。射程：只判本条证据撑得住的范围，不写「可靠」这类全称评价——
    线性好与散布超标是两回事，直不直说直、散不散说散。基准：「太」「过」「超出」
    这类相对判断必须带出比较基准——相对限值、预算还是预期（如「散得仍比预期开」），
    不写无基准的程度副词（「差得太远」「很大」）；数字有溯源，判定同样要有基准。
    一致：全部首句连起来读，互相抵触时改越权的那条。
17. 数字按报告精度写，一般保留 3～4 位有效数字，全精度不进正文；确需可查全精度时
    用 [1.074](num:1.0741103289827418) 标记——括号前是读者看的位数，num: 后是分析结果
    里的原值，同一数值只标一次。标记内外的数字都过数字溯源校验。"""

RECORD_SYSTEM = """你是实验记录识别助手。用户给你一张手写实验记录的照片。
按给定的列定义识别成表格 JSON，规则：
1. 只输出一个 JSON 对象（或行数组），不要多余文字。
2. 每行：{"series":"std"|"blank"|"sample:名称"|"qc:crm","values":{列key:数值或null},"confidence":{列key:0~1}}。
3. 标准系列行或标定平行行是 series="std"；平行样品（如同一试样的多份滴定）用相同 series 名；质控样 series="qc:crm"。
4. 一页里可能有多张表（例如先「标定」后「样品测定」）：每张表的行都要输出，逐行按用途归入 series，不要只认一张表。
5. 表头或表旁一次性写明的量（如试样质量、定容体积、移取体积）如果与某个列定义对应，把它填进对应各行该列的 values；对应不上的忽略。
6. 看不清、不确定的值一律填 null，不许猜；整行识别不出就省略该行。
7. 数值不带单位，纯数字。"""


async def llm_findings(analysis: dict, ctx: dict, dataset: dict) -> tuple[list[dict], list[str]]:
    """主路径：glm-5.3 生成 → 校验 → 失败回灌重试一次。返回 (结论列表, 丢弃原因)。"""
    compact_curve = analysis.get("titration_curve")
    if compact_curve is not None:
        # theory 是 161 点的作图数据，进 prompt 会撑爆 token：只留可引用的摘要
        compact_curve = {k: v for k, v in compact_curve.items() if k != "theory"}
        compact_curve["n_theory_points"] = len(analysis["titration_curve"].get("theory", []))
    compact = {
        "fits": analysis.get("fits"), "predictions": analysis.get("predictions"),
        "residuals": analysis.get("residuals"), "qc_results": analysis.get("qc_results"),
        "comparison": analysis.get("comparison"),
        "titration_curve": compact_curve,                # 0.7.0 可选节（去 theory 点列）
        "error_budget": analysis.get("error_budget"),
    }
    dataset_index = [
        {"point_id": r["id"], "series": r.get("series")} for r in dataset.get("rows", [])
    ]
    user = (f"实验：{ctx.get('name')}。目的：{ctx.get('purpose')}\n"
            f"分析结果 JSON：\n{json.dumps(compact, ensure_ascii=False)}\n"
            f"数据集行索引：\n{json.dumps(dataset_index, ensure_ascii=False)}\n")
    glossary = (ctx.get("guide") or {}).get("glossary") or []
    if glossary:
        user += "术语表（标记用 [显示文字](term:term_id)，id 只许用这里的；首次出现标一次）：\n"
        for g in glossary:
            line = f"{g['term']}（{g['term_id']}）——{g['plain']}"
            if g.get("help"):
                line += f"；帮助理解：{g['help']}"
            user += line + "\n"
    user += "请按系统规则输出结论。"
    messages = [{"role": "system", "content": FINDING_SYSTEM},
                {"role": "user", "content": user}]

    raw = await chat(messages, timeout=120)
    items, dropped = _parse_and_validate(raw, analysis, dataset, ctx)
    if not items:
        messages = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content":
                f"以下结论未通过校验被丢弃，原因：{dropped}。"
                f"请严格只引用分析结果里的数字和真实存在的对象，重新输出。"},
        ]
        raw = await chat(messages, timeout=120)
        items, dropped = _parse_and_validate(raw, analysis, dataset, ctx)
    items = [_renumber(f, i) for i, f in enumerate(items, start=1)]
    return items, dropped


def _parse_and_validate(raw: str, analysis: dict, dataset: dict, ctx: dict):
    obj = extract_json(raw)
    if not isinstance(obj, list):
        return [], ["未解析出 JSON 数组"]
    kept, dropped = validate_findings(obj, analysis, dataset, ctx)
    return kept, dropped or ["全部通过"]


def _renumber(f: dict, i: int) -> dict:
    f.setdefault("schema_version", CONTRACT_VERSION)
    f["id"] = f"f{i}"
    f.setdefault("simulatable", False)
    f.setdefault("simulation", None)
    # 讲解阶梯由模板确定性挂接（m5.py::attach_ladder），LLM 不生成，防幻觉
    f.pop("ladder", None)
    return f
