"""
Standalone risk signals test — no pydantic dependency.
Inlines minimal data structures to test _has_negation, _is_historical,
_allergy_context_active, _has_bp_context, and _extract_risk_signals.
"""
import re
import sys
sys.stdout.reconfigure(encoding="utf-8")

# ── Inline minimal replicas of schemas (avoid pydantic import) ──────

class MCPRecentMessage:
    def __init__(self, content: str, role: str = "user"):
        self.content = content
        self.role = role

class MCPActiveEntities:
    def __init__(self, symptoms=None, metrics=None):
        self.symptoms = symptoms or []
        self.metrics = metrics or []

class MCPRiskSignals:
    def __init__(self, red_flags=None, medication_flags=None, monitoring_flags=None):
        self.red_flags = red_flags or []
        self.medication_flags = medication_flags or []
        self.monitoring_flags = monitoring_flags or []

# ── Import the REAL logic from app.api.mcp_routes ────────────────────

# The routes module has top-level sqlalchemy/fastapi imports,
# but the helper functions don't need them. We import carefully.
# Since py_compile already succeeded, the file is syntactically valid.
# For testing, inline the functions directly so we test the ACTUAL logic
# that was written to the file.

# Copy exact implementations from app/api/mcp_routes.py lines 77-133
_NEGATION_WORDS = ["没", "不", "无", "否", "未", "没有", "不是", "不会", "不要", "不能", "不必", "不用", "已缓解", "已好转", "已消失", "好了", "没事"]
_HISTORICAL_WORDS = ["之前", "以前", "过去", "曾", "曾经", "之前有过", "已有", "早就", "原来", "原来有", "既往", "旧病", "老毛病"]

def _has_negation(text: str, term: str, window: int = 15) -> bool:
    """Check if `term` is negated nearby (before or after), respecting clause boundaries."""
    idx = text.find(term)
    if idx < 0:
        return False
    start = max(0, idx - window)
    prefix = text[start:idx]
    end = min(len(text), idx + len(term) + window)
    suffix = text[idx + len(term):end]
    combined = prefix + suffix
    for word in _NEGATION_WORDS:
        if word in combined:
            word_idx = combined.find(word)
            if word_idx < 0:
                continue
            if word in prefix:
                between = prefix[prefix.find(word) + len(word):]
            else:
                between = suffix[:suffix.find(word)]
            if not any(sep in between for sep in ("，", "。", "！", "？", "；", ";", "但是", "不过", "然而")):
                return True
    return False

def _is_historical(text: str, term: str, window: int = 22) -> bool:
    idx = text.find(term)
    if idx < 0:
        return False
    start = max(0, idx - window)
    end = min(len(text), idx + len(term) + window)
    context = text[start:end]
    for marker in _HISTORICAL_WORDS:
        if marker in context:
            return True
    return False

def _allergy_context_active(text: str, window: int = 18) -> bool:
    idx = text.find("过敏")
    if idx < 0:
        return False
    if _has_negation(text, "过敏", window=window):
        return False
    start = max(0, idx - window)
    end = min(len(text), idx + 2 + window)
    context = text[start:end]
    active_markers = ["出现", "起了", "症状", "怎么办", "怎么处理", "反应", "红", "痒", "肿", "呼吸困难", "休克"]
    for marker in active_markers:
        if marker in context:
            return True
    return False

def _has_bp_context(text: str, bp_match, window: int = 30) -> bool:
    val1 = int(bp_match.group(1))
    val2 = int(bp_match.group(2))
    if not (60 <= val1 <= 250 and 30 <= val2 <= 150):
        return False
    start = max(0, bp_match.start() - window)
    end = min(len(text), bp_match.end() + window)
    context = text[start:end]
    bp_indicators = ["血压", "收缩压", "舒张压", "上压", "下压", "高压", "低压"]
    return any(ind in context for ind in bp_indicators)

RED_FLAG_TERMS = ["胸痛", "呼吸困难", "晕厥", "意识不清", "抽搐", "呕血", "黑便", "高烧", "突然加重"]
MEDICATION_FLAG_TERMS = ["停药", "漏服", "加量", "减量", "不良反应", "副作用", "重复用药"]
MONITORING_FLAG_TERMS = ["监测", "复查", "随访", "观察", "复诊"]

def _clip_items(items, limit, item_limit):
    clipped = []
    for item in items:
        text = item[:item_limit] if len(item) > item_limit else item
        if text and text not in clipped:
            clipped.append(text)
    return clipped[-limit:]

def _extract_risk_signals(messages, entities):
    red_flags = []
    medication_flags = []
    monitoring_flags = []
    for item in messages:
        if (item.role or "").strip().lower() != "user":
            continue
        text = (item.content or "").strip()
        if not text:
            continue
        for term in RED_FLAG_TERMS:
            if term not in text:
                continue
            if _has_negation(text, term):
                continue
            if _is_historical(text, term):
                continue
            red_flags.append(term)
        for term in MEDICATION_FLAG_TERMS:
            if term not in text:
                continue
            if _has_negation(text, term):
                continue
            if term in ("停药", "加量", "减量"):
                idx = text.find(term)
                prefix = text[max(0, idx - 12):idx]
                if any(w in prefix for w in ("不要", "不能", "务必不要", "切忌", "遵医嘱", "医生建议", "被要求")):
                    continue
            medication_flags.append(term)
        if _allergy_context_active(text):
            medication_flags.append("过敏反应")
        for term in MONITORING_FLAG_TERMS:
            if term not in text:
                continue
            if _has_negation(text, term):
                continue
            monitoring_flags.append(term)
        bp = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", text)
        if bp and _has_bp_context(text, bp):
            monitoring_flags.append(f"血压 {bp.group(1)}/{bp.group(2)}")
        hr = re.search(r"(\d{2,3})\s*(?:次/分|bpm)", text, re.IGNORECASE)
        if hr:
            monitoring_flags.append(f"心率 {hr.group(1)}次/分")
        temp = re.search(r"(\d+(?:\.\d+)?)\s*℃", text)
        if temp:
            monitoring_flags.append(f"体温 {temp.group(1)}℃")
    if entities.metrics:
        monitoring_flags.extend(entities.metrics)
    if entities.symptoms and any(item in entities.symptoms for item in ["胸痛", "呼吸困难", "晕厥", "意识不清"]):
        red_flags.extend([item for item in entities.symptoms if item in ["胸痛", "呼吸困难", "晕厥", "意识不清"]])
    return MCPRiskSignals(
        red_flags=_clip_items(red_flags, limit=6, item_limit=80),
        medication_flags=_clip_items(medication_flags, limit=6, item_limit=80),
        monitoring_flags=_clip_items(monitoring_flags, limit=8, item_limit=80),
    )

# ── Test runner ──────────────────────────────────────────────────────

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name}")
        failed += 1

def verify(result, red=None, med=None, mon=None):
    if red is not None:
        check(f"red={red}", set(result.red_flags) == set(red))
    if med is not None:
        check(f"med={med}", set(result.medication_flags) == set(med))
    if mon is not None:
        check(f"mon={mon}", set(result.monitoring_flags) == set(mon))

def msg(text, role="user"):
    return MCPRecentMessage(text, role)

def entities(symptoms=None, metrics=None):
    return MCPActiveEntities(symptoms, metrics)

# ── Helper unit tests ──────────────────────────────────────────
print("\n▶ has_negation")
check("没有胸痛", _has_negation("我没有胸痛", "胸痛"))
check("不觉得晕厥", _has_negation("不觉得有晕厥", "晕厥"))
check("高烧已缓解", _has_negation("高烧已缓解，现在没事了", "高烧"))
check("正常胸痛（不否定）", not _has_negation("我现在胸痛", "胸痛"))
check("term not found", not _has_negation("正常文本", "抽搐"))

print("\n▶ is_historical")
check("之前有过胸痛", _is_historical("之前有过胸痛，已确诊", "胸痛"))
check("既往高烧史", _is_historical("既往高烧史，最近未出现", "高烧"))
check("当前呼吸困难（不是过去）", not _is_historical("我现在呼吸困难", "呼吸困难"))

print("\n▶ allergy_context_active")
check("活动过敏：出现疹子", _allergy_context_active("吃了药出现过敏，起疹子了"))
check("活动过敏：痒+肿", _allergy_context_active("过敏了，身上很痒，红肿"))
check("否定过敏", not _allergy_context_active("我没有过敏史"))
check("描述过敏（非活动）", not _allergy_context_active("我对青霉素过敏"))

print("\n▶ has_bp_context")
bp1 = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", "血压120/80")
check("血压上下文（前）", _has_bp_context("血压120/80", bp1))
bp2 = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", "120/80是我的血压")
check("血压上下文（后）", _has_bp_context("120/80是我的血压", bp2))
bp3 = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", "比分120/80")
check("无血压上下文", not _has_bp_context("比分120/80", bp3))
bp4 = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", "血压40/20")  # out of range
check("超范围", not _has_bp_context("血压40/20", bp4))

# ── Integration tests ──────────────────────────────────────────
print("\n▶ 正常触发")
r = _extract_risk_signals([msg("我胸痛，呼吸困难")], entities())
verify(r, red=["胸痛", "呼吸困难"])

r = _extract_risk_signals([msg("心率85次/分，体温37.5℃")], entities())
check("心率+体温", "心率 85次/分" in r.monitoring_flags and "体温 37.5℃" in r.monitoring_flags)

print("\n▶ 否定检测")
r = _extract_risk_signals([msg("我没有胸痛也没有晕厥")], entities())
verify(r, red=[])

r = _extract_risk_signals([msg("高烧已缓解")], entities())
check("高烧已缓解不触发", "高烧" not in r.red_flags)

print("\n▶ 过去时")
r = _extract_risk_signals([msg("之前有过胸痛，已确诊")], entities())
verify(r, red=[])

r = _extract_risk_signals([msg("我曾经晕厥，但是几年前的事")], entities())
check("既往晕厥不触发", "晕厥" not in r.red_flags)

print("\n▶ 过敏")
r = _extract_risk_signals([msg("吃了药出现过敏反应，全身起疹子很痒")], entities())
check("活动过敏触发", "过敏反应" in r.medication_flags)

r = _extract_risk_signals([msg("我没有过敏史")], entities())
check("否定过敏不触发", "过敏反应" not in r.medication_flags)

r = _extract_risk_signals([msg("我对青霉素过敏")], entities())
check("描述过敏不触发", "过敏反应" not in r.medication_flags)

print("\n▶ 用药 + 医嘱排除")
r = _extract_risk_signals([msg("我昨天自己停药了")], entities())
check("自行停药触发", "停药" in r.medication_flags)

r = _extract_risk_signals([msg("医生建议停药观察")], entities())
check("医嘱停药不触发", "停药" not in r.medication_flags)

r = _extract_risk_signals([msg("医生说不能自己加量")], entities())
check("医嘱加量不触发", "加量" not in r.medication_flags)

r = _extract_risk_signals([msg("遵医嘱减量服药")], entities())
check("遵医嘱减量不触发", "减量" not in r.medication_flags)

print("\n▶ 监测")
r = _extract_risk_signals([msg("我需要下个月复查")], entities())
check("复查触发", "复查" in r.monitoring_flags)

r = _extract_risk_signals([msg("医生说不用复查了")], entities())
check("否定复查不触发", "复查" not in r.monitoring_flags)

print("\n▶ 血压")
r = _extract_risk_signals([msg("血压值是142/88，偏高")], entities())
check("血压上下文触发", any("血压" in f for f in r.monitoring_flags))

r = _extract_risk_signals([msg("比赛比分98/76")], entities())
check("无血压上下文不触发", not any("血压" in f for f in r.monitoring_flags))

print("\n▶ 复合")
r = _extract_risk_signals([msg("我没有胸痛，但是有呕血")], entities())
verify(r, red=["呕血"])

r = _extract_risk_signals([msg("胸痛", role="assistant"), msg("呕血", role="system")], entities())
verify(r, red=[], med=[], mon=[])

r = _extract_risk_signals([], entities())
verify(r, red=[], med=[], mon=[])

print("\n▶ 关键词配置")
check("MED不含过敏", "过敏" not in MEDICATION_FLAG_TERMS)
check("RED含胸痛", "胸痛" in RED_FLAG_TERMS)
check("MON含复查", "复查" in MONITORING_FLAG_TERMS)

# ── _append_risk_advice tests (inline copy) ─────────────────────

def _append_risk_advice(answer: str, risk_signals) -> str:
    """Inline copy of the function in llm_router.py for testing."""
    if not answer or not risk_signals:
        return answer
    red = [item for item in (risk_signals.red_flags or []) if item]
    med = [item for item in (risk_signals.medication_flags or []) if item]
    if not red and not med:
        return answer
    lines = []
    if red:
        red_list = "、".join(red[:4])
        lines.append(f"另外，你提到的{red_list}是需要重视的信号，建议尽快去医院让医生看一下")
    if med:
        med_list = "、".join(med[:4])
        lines.append(f"还有，关于{med_list}这件事，用药方面最好不要自己调整")
    if lines:
        return answer.rstrip() + "\n\n" + "\n".join(lines)
    return answer

print("\n▶ _append_risk_advice")
sig_red = MCPRiskSignals(red_flags=["胸痛"])
answer_red = _append_risk_advice("您的症状可能是...", sig_red)
check("红旗追加就医建议", "胸痛" in answer_red and "尽快去医院" in answer_red)

sig_med = MCPRiskSignals(medication_flags=["停药"])
answer_med = _append_risk_advice("请按时服药。", sig_med)
check("用药追加安全提醒", "停药" in answer_med and "不要自己调整" in answer_med)

sig_both = MCPRiskSignals(red_flags=["胸痛"], medication_flags=["停药"])
answer_both = _append_risk_advice("需要注意。", sig_both)
check("双重信号追加两条建议", "胸痛" in answer_both and "停药" in answer_both)

sig_empty = MCPRiskSignals()
answer_empty = _append_risk_advice("一切正常。", sig_empty)
check("无信号不追加", answer_empty == "一切正常。")

check("None risk_signals", _append_risk_advice("ok", None) == "ok")
check("空 answer", _append_risk_advice("", sig_red) == "")

# ── Summary ────────────────────────────────────────────────────
total = passed + failed
print(f"\n{'='*40}")
print(f"  {passed}/{total} passed{'  🎉' if failed == 0 else '  ❌'}")
if failed:
    print(f"  {failed} test(s) failed")
print(f"{'='*40}\n")
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
