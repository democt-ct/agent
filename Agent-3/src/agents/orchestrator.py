"""Orchestrator Agent -- 意图路由 + 编排.

职责:
1. 接收用户输入,判断意图,路由到正确的 Specialist Agent
2. 必要时协调多个 Agent(串行编排)
3. 兜底/降级策略
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

from src.config import config
from src.llm_client import call_llm_with_retry
from src.protocol.types import AgentRegistration

# ═══════════════════════════════════════════════════════════════════
# Agent 注册表
# ═══════════════════════════════════════════════════════════════════

AGENT_REGISTRY: dict[str, AgentRegistration] = {
    "hr_agent": AgentRegistration(
        agent_name="hr_agent",
        display_name="HR 专家",
        description=(
            "负责回答人事制度,考勤,请假(年假/病假/事假),薪酬福利,"
            "社保公积金,入职离职,绩效考核,培训发展相关问题."
            "可以查询员工假期余额,提交请假申请,查询人事政策."
        ),
        tool_descriptions=[
            "get_leave_balance(user_id) -- 查询员工年假/病假剩余天数",
            "submit_leave_request(user_id, leave_type, start_date, end_date, reason) -- 提交请假申请",
            "get_my_applications(user_id) -- 查询用户所有申请记录(请假/工单/报销)",
        ],
    ),
    "it_agent": AgentRegistration(
        agent_name="it_agent",
        display_name="IT 专家",
        description=(
            "负责回答 IT 设备申领,报修,软件安装,网络问题,VPN 配置,"
            "密码重置,账号管理,打印机,邮箱,电脑故障相关问题."
            "可以查询工单状态,创建新工单,查询设备库存."
        ),
        tool_descriptions=[
            "check_ticket_status(ticket_id) -- 查询工单处理状态",
            "create_ticket(user_id, issue_type, description, priority) -- 创建 IT 工单",
            "check_device_inventory(device_type) -- 查询设备库存",
            "get_my_applications(user_id) -- 查询用户所有申请记录(请假/工单/报销)",
        ],
    ),
    "legal_agent": AgentRegistration(
        agent_name="legal_agent",
        display_name="法务专家",
        description=(
            "负责回答合规,合同审批,数据保护,个人信息保护,保密协议,"
            "知识产权,竞业限制相关法律政策问题."
            "可以搜索合同条款,进行合规初步检查."
        ),
        tool_descriptions=[
            "search_contract(keyword) -- 搜索合同条款",
            "check_compliance(doc_summary) -- 合规性初步检查",
            "get_my_applications(user_id) -- 查询用户所有申请记录(请假/工单/报销)",
        ],
    ),
    "finance_agent": AgentRegistration(
        agent_name="finance_agent",
        display_name="财务专家",
        description=(
            "负责回答报销,预算,薪资结构,出差标准,采购流程,"
            "费用审批相关财务制度和流程问题."
            "可以查询报销政策,提交报销申请,查询部门预算,查询薪资社保说明."
        ),
        tool_descriptions=[
            "query_expense_policy(expense_type) -- 查询报销制度和限额",
            "submit_expense_report(user_id, expense_type, amount, description) -- 提交报销申请",
            "check_budget(department_id) -- 查询部门预算余额",
            "query_salary_structure(user_id) -- 查询薪资构成社保比例",
            "check_travel_policy(destination, days) -- 查询出差标准",
            "get_my_applications(user_id) -- 查询用户所有申请记录(请假/工单/报销)",
        ],
    ),
    "fallback": AgentRegistration(
        agent_name="fallback",
        display_name="通用助手",
        description="当问题不属于以上任何领域时,提供通用兜底回答.",
        tool_descriptions=[],
    ),
}

# ═══════════════════════════════════════════════════════════════════
# 意图分类关键词(query vs action)
# ═══════════════════════════════════════════════════════════════════

INTENT_ACTION_KEYWORDS: list[str] = [
    "申请", "提交", "创建", "审批", "修改", "删除", "重置",
    "注册", "注销", "帮我", "帮忙", "我要", "我想", "取消", "撤回",
    "更新", "配置", "安装", "卸载", "开通", "关闭", "启用", "禁用",
    "预约", "预定", "下单", "采购", "发起", "执行", "处理",
]

# 需要结构化详细回答的提问方式(应走 action 级 prompt,不限制句数)
INTENT_ANALYSIS_KEYWORDS: list[str] = [
    "区别", "对比", "比较", "哪个好", "哪种", "不同", "差异",
    "优缺点", "优劣", "选择", "推荐", "怎么选", "如何选择",
    "详解", "详细", "流程", "步骤", "怎么", "如何", "怎么办",
    "条件", "要求", "规定", "标准", "计算", "怎么算",
]


# ═══════════════════════════════════════════════════════════════════
# 关键词规则层(规则命中 → 跳过 LLM,直接返回路由结果)
# ═══════════════════════════════════════════════════════════════════

# ── 从统一配置构建关键词规则 ───────────────────────────────
# 单一数据源 config.domain_keywords,避免与 Planner 漂移
_KEYWORD_RULES_CACHE: list[tuple[list[str], str]] | None = None
_DOMAIN_KW_TOTALS: dict[str, int] = {}


def _get_keyword_rules() -> list[tuple[list[str], str]]:
    """延迟构建关键词规则列表(从 config.domain_keywords)."""
    global _KEYWORD_RULES_CACHE, _DOMAIN_KW_TOTALS
    if _KEYWORD_RULES_CACHE is None:
        _KEYWORD_RULES_CACHE = []
        for agent_key, keywords in config.domain_keywords.items():
            _KEYWORD_RULES_CACHE.append((keywords, agent_key))
            _DOMAIN_KW_TOTALS[agent_key] = len(keywords)
    return _KEYWORD_RULES_CACHE

# 寒暄/无关话题(直接 fallback,不调 LLM)
GREETING_PATTERNS: list[str] = [
    r"^(你好|您好|hi|hello|早上好|下午好|晚上好|在吗|在不在)[\s!!..]*$",
    r"^(谢谢|多谢|感谢|thanks|thank)[\s!!..]*$",
    r"^(再见|拜拜|bye|晚安)[\s!!..]*$",
    r"^(你是|你是谁|你叫什么)[\s!!..??]*$",
]

# ═══════════════════════════════════════════════════════════════════
# LLM 路由 Prompt
# ═══════════════════════════════════════════════════════════════════

ROUTING_SYSTEM_PROMPT = """你是一个精确的问题路由专家.根据用户问题,判断应由以下哪个专家处理,以及用户意图类型.

## 专家列表

- hr_agent: 人事制度,考勤,请假,薪酬福利,社保,入职离职,绩效,培训
- it_agent: 设备报修,工单,软件安装,网络VPN,密码账号,电脑故障
- legal_agent: 合同,合规,数据保护,保密协议,知识产权,法务
- finance_agent: 报销,预算,薪资结构,出差标准,采购流程,财务制度
- fallback: 不属于以上任何领域(寒暄,闲聊,超出范围的问题)

## 路由规则

1. 问题明确属于某个领域 → primary 填该领域,secondary 为 null,confidence ≥ 0.9
2. 问题跨多个领域 → primary 填最核心领域,secondary 填次要领域,confidence 0.7-0.85
3. 问题不属于任何领域 → primary 填 "fallback",secondary 为 null
4. 寒暄 ("你好""谢谢""再见") → primary 填 "fallback"
5. 模糊问题 ("帮我查一下") → confidence ≤ 0.5,不猜测

## 意图分类(intent)

- "action": 用户要执行操作(申请,提交,报销,创建…),或需要详细回答的对比/分析问题(区别,对比,怎么选,流程,条件,计算)
- "query": 用户只是简单查询(查看,查询余额,快速确认)

## 输出格式(严格 JSON,不要多余文字)

{"primary": "agent_name", "secondary": "agent_name | null", "confidence": 0.0-1.0, "intent": "action | query"}"""


# ── 操作卡片意图规则 ──────────────────────────────────────────
# 格式: (触发关键词列表, card_type, prefill字段)
ACTION_CARD_RULES: list[tuple[list[str], str, dict]] = [
    (["我要请假", "我想请假", "帮我请假", "帮我申请假", "申请假", "提交请假", "请个假", "申请年假", "申请病假", "申请事假"], "leave_form", {}),
    (["提交报销", "申请报销", "报销申请", "我要报销", "我想报销", "帮我报销"], "expense_form", {}),
    (["修电脑", "电脑坏了", "电脑维修", "维修电脑", "报修", "我要报修", "帮我报修", "提交工单", "创建工单", "设备维修", "笔记本维修", "电脑蓝屏", "电脑开不了机", "笔记本开不了机"], "ticket_form", {"issue_type": "硬件报修", "priority": "中"}),
    (["打卡", "上班打卡", "下班打卡", "签到", "签退"], "attendance_punch", {}),
    (["申请加班", "加班申请", "提交加班", "我要加班", "我想加班"], "overtime_form", {}),
    (["申请出差", "出差申请", "提交出差", "我要出差", "我想出差"], "trip_form", {}),
    (["待审批", "审批列表", "有没有审批", "需要审批", "审批一下", "帮我审批"], "approval_check", {}),
]

_ACTION_VERBS = ("申请", "提交", "创建", "发起", "办理", "帮我", "我要", "我想", "我需要", "需要", "想要")
_QUERY_MARKERS = ("多少", "几天", "还剩", "余额", "查询", "查看", "有没有", "是否", "吗", "?", "?")

# 否定前缀模式(用于过滤被否定的关键词匹配)
_NEGATION_PATTERNS = re.compile(r"(不|无需|不需要|不想|没有|取消)(.{0,4})$")


def _is_negated(text: str, keyword: str) -> bool:
    """检测关键词前面是否有否定词,如"不需要请假"."""
    idx = text.find(keyword)
    if idx <= 0:
        return False
    before = text[:idx]
    return bool(_NEGATION_PATTERNS.search(before))

# 每种卡片的语义描述,供 LLM 意图识别使用
_ACTION_CARD_INTENTS = {
    "leave_form": "用户想请假,休假,申请假期(年假/病假/事假等)",
    "expense_form": "用户想报销,提交费用申请",
    "ticket_form": "用户的设备出了问题,需要维修,报修或提交IT工单",
    "attendance_punch": "用户想打卡,签到或签退",
    "overtime_form": "用户想申请加班",
    "trip_form": "用户想申请出差",
    "approval_check": "用户想查看或处理待审批事项",
}

# 每种卡片对应的 prefill(与 ACTION_CARD_RULES 保持一致)
_ACTION_CARD_PREFILL: dict[str, dict] = {
    "ticket_form": {"issue_type": "硬件报修", "priority": "中"},
}

# 每种卡片的字段定义 -- 前端按此动态渲染表单
_ACTION_CARD_FIELDS: dict[str, dict] = {
    "leave_form": {
        "title": "申请请假",
        "submit_action": "submit_leave",
        "fields": [
            {"name": "leave_type", "label": "类型", "type": "select", "options": ["年假", "病假", "事假"], "required": True},
            {"name": "start_date", "label": "开始日期", "type": "date", "required": True},
            {"name": "end_date", "label": "结束日期", "type": "date", "required": True},
            {"name": "reason", "label": "原因", "type": "text", "required": False, "placeholder": "可选"},
        ],
    },
    "expense_form": {
        "title": "提交报销",
        "submit_action": "submit_expense",
        "fields": [
            {"name": "expense_type", "label": "类型", "type": "select", "options": ["差旅", "办公", "招待", "培训", "其他"], "required": True},
            {"name": "amount", "label": "金额", "type": "number", "required": True, "placeholder": "元"},
            {"name": "description", "label": "说明", "type": "text", "required": True, "placeholder": "费用说明"},
        ],
    },
    "ticket_form": {
        "title": "IT 维修工单",
        "submit_action": "submit_ticket",
        "fields": [
            {"name": "issue_type", "label": "问题类型", "type": "select", "options": ["硬件报修", "软件安装", "网络问题", "账号问题", "其他"], "required": True},
            {"name": "priority", "label": "优先级", "type": "select", "options": ["高", "中", "低"], "required": False},
            {"name": "description", "label": "问题描述", "type": "text", "required": True, "placeholder": "例如:电脑开不了机,蓝屏,键盘损坏……"},
        ],
    },
    "attendance_punch": {
        "title": "考勤打卡",
        "submit_action": "punch",
        "fields": [],
        "punch_buttons": True,
    },
    "overtime_form": {
        "title": "申请加班",
        "submit_action": "submit_overtime",
        "fields": [
            {"name": "date", "label": "日期", "type": "date", "required": True},
            {"name": "hours", "label": "时长(h)", "type": "number", "required": True, "placeholder": "2"},
            {"name": "reason", "label": "原因", "type": "text", "required": False, "placeholder": "加班原因"},
        ],
    },
    "trip_form": {
        "title": "申请出差",
        "submit_action": "submit_trip",
        "fields": [
            {"name": "destination", "label": "目的地", "type": "text", "required": True, "placeholder": "城市"},
            {"name": "start_date", "label": "开始日期", "type": "date", "required": True},
            {"name": "end_date", "label": "结束日期", "type": "date", "required": True},
            {"name": "amount", "label": "预估费用", "type": "number", "required": False, "placeholder": "元"},
            {"name": "reason", "label": "事由", "type": "text", "required": False, "placeholder": "出差目的"},
        ],
    },
    "approval_check": {
        "title": "待审批",
        "submit_action": "load_approvals",
        "fields": [],
    },
}


def _detect_action_card(query: str, intent: str = "action", client: OpenAI | None = None) -> dict | None:
    """检测是否需要返回操作卡片.关键词优先,未命中时 LLM 兜底."""
    qlower = query.lower()
    if intent == "query" or any(marker in qlower for marker in _QUERY_MARKERS):
        if not any(verb in qlower for verb in _ACTION_VERBS):
            return None

    # 1. 关键词快速匹配
    for keywords, card_type, prefill in ACTION_CARD_RULES:
        if any(kw in qlower for kw in keywords):
            card: dict = {"type": card_type}
            if prefill:
                card["prefill"] = prefill
            # 附加字段定义,供前端动态渲染
            if card_type in _ACTION_CARD_FIELDS:
                card.update(_ACTION_CARD_FIELDS[card_type])
            return card

    # 2. LLM 意图识别兜底
    if client is None:
        return None

    intent_desc = "\n".join(f"- {k}: {v}" for k, v in _ACTION_CARD_INTENTS.items())
    response = call_llm_with_retry(
        client,
        model=config.llm_model,
        messages=[{
            "role": "user",
            "content": (
                f"判断用户输入是否表达了[执行某个操作的意图],而非仅仅在询问,了解或查询信息.\n\n"
                f"规则:\n"
                f"- 用户想[做]某件事(申请,提交,打卡等)→ 返回对应 type\n"
                f"- 用户只是在[问]或[了解]某件事 → 返回 null\n\n"
                f"可用操作类型:\n{intent_desc}\n\n"
                f"用户输入:{query}\n\n"
                f'以 JSON 格式回复:{{"type": "xxx"}} 或 {{"type": null}}'
            ),
        }],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        card_type = json.loads(response.choices[0].message.content or "{}").get("type")
    except (json.JSONDecodeError, AttributeError):
        return None

    if card_type and card_type in _ACTION_CARD_INTENTS:
        card = {"type": card_type}
        if card_type in _ACTION_CARD_PREFILL:
            card["prefill"] = _ACTION_CARD_PREFILL[card_type]
        if card_type in _ACTION_CARD_FIELDS:
            card.update(_ACTION_CARD_FIELDS[card_type])
        return card

    return None


# ═══════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════


class Orchestrator:
    """Orchestrator Agent -- 路由 + 编排中枢.

    使用方式:
        orchestrator = Orchestrator(client)
        result = orchestrator.route("我请病假工资怎么算")
        # → {"primary": "hr_agent", "secondary": null, "confidence": 0.95, "method": "keyword"}
    """

    def __init__(
        self,
        client: OpenAI,
        model: str = "deepseek-v4-flash",
    ) -> None:
        self.client = client
        self.model = model

    # ── 公共入口 ──────────────────────────────────────────────

    def route(self, query: str, use_llm: bool = True, history: list[dict] | None = None) -> dict[str, Any]:
        """路由一个用户问题到对应的 Agent.

        Args:
            query: 用户问题.
            use_llm: 是否使用 LLM 兜底路由(False 时仅关键词匹配).
            history: 最近几轮对话 [{role, content}, ...],用于短应答的上下文推断.

        Returns:
            {
                "primary": "hr_agent",
                "secondary": null,
                "confidence": 0.95,
                "method": "keyword" | "llm" | "greeting" | "context",
                "intent": "query" | "action",
            }
        """
        # 1. 寒暄检测
        if self._is_greeting(query):
            return {
                "primary": "fallback",
                "secondary": None,
                "confidence": 1.0,
                "method": "greeting",
                "intent": "query",
                "action_card": None,
            }

        # 2. 关键词规则匹配
        keyword_result = self._keyword_match(query)
        if keyword_result:
            keyword_result["action_card"] = _detect_action_card(query, keyword_result.get("intent", "action"), self.client)
            return keyword_result

        # 3. 短应答上下文推断("需要""好的""可以"等确认词)
        if self._is_short_confirm(query) and history:
            ctx_result = self._context_route(query, history)
            if ctx_result:
                return ctx_result

        # 4. LLM 路由(可选)
        if not use_llm:
            return {
                "primary": "fallback",
                "secondary": None,
                "confidence": 0.0,
                "method": "keyword_only",
                "intent": "action",
                "action_card": None,
            }

        result = self._llm_route(query, history)
        result["action_card"] = _detect_action_card(query, result.get("intent", "action"), self.client)
        return result

    # ── 关键词规则 ────────────────────────────────────────────

    def _is_greeting(self, query: str) -> bool:
        """检测是否是寒暄/无关话题."""
        stripped = query.strip()
        for pattern in GREETING_PATTERNS:
            if re.match(pattern, stripped):
                return True
        return False

    def _keyword_match(self, query: str) -> dict[str, Any] | None:
        """关键词规则匹配.命中返回路由结果,否则返回 None.

        只有当关键词 exclusively 指向一个领域时才生效;
        如果同时命中多个领域,退回让 LLM 判断.

        支持否定句检测:"不需要请假" 不计入 HR 命中.
        """
        hits: dict[str, list[str]] = {}
        for keywords, agent in _get_keyword_rules():
            matched = [kw for kw in keywords if kw.lower() in query.lower()]
            # 过滤被否定的关键词
            matched = [kw for kw in matched if not _is_negated(query, kw)]
            if matched:
                hits.setdefault(agent, []).extend(matched)

        intent = self._detect_intent(query)

        if len(hits) == 1:
            agent, matched_keywords = next(iter(hits.items()))
            # Dynamic confidence: more matched keywords → higher confidence
            total_kw = _DOMAIN_KW_TOTALS.get(agent, len(matched_keywords))
            ratio = len(matched_keywords) / max(total_kw, 1)
            confidence = round(min(0.95, 0.75 + 0.20 * ratio), 2)
            return {
                "primary": agent,
                "secondary": None,
                "confidence": confidence,
                "method": "keyword",
                "intent": intent,
                "matched_keywords": matched_keywords,
            }

        if len(hits) > 1:
            # 多领域命中 → 按命中数排序
            sorted_hits = sorted(hits.items(), key=lambda x: len(x[1]), reverse=True)
            primary_agent, primary_kw = sorted_hits[0]
            secondary_agent, secondary_kw = (
                sorted_hits[1] if len(sorted_hits) > 1 else (None, [])
            )

            # 命中数差异大(≥2倍)→ 信任规则
            if secondary_agent and len(primary_kw) >= len(secondary_kw) * 2:
                # Dynamic confidence: larger ratio → higher confidence
                ratio = len(primary_kw) / max(len(secondary_kw), 1)
                confidence = round(min(0.85, 0.70 + 0.10 * min(ratio - 1, 1.5)), 2)
                return {
                    "primary": primary_agent,
                    "secondary": secondary_agent,
                    "confidence": confidence,
                    "method": "keyword",
                    "intent": intent,
                    "matched_keywords": primary_kw,
                }

            # 命中数相近 → 用位置优先级:先提到的领域是主问题
            first_pos: dict[str, int] = {}
            for agent, keywords in hits.items():
                positions = [query.lower().index(kw.lower()) for kw in keywords]
                first_pos[agent] = min(positions)

            by_position = sorted(first_pos.items(), key=lambda x: x[1])
            primary_agent = by_position[0][0]
            secondary_agent = by_position[1][0] if len(by_position) > 1 else None

            # Dynamic confidence: earlier position → slightly higher confidence
            primary_pos = first_pos[primary_agent]
            pos_ratio = 1.0 - (primary_pos / max(len(query), 1))
            confidence = round(min(0.80, 0.60 + 0.20 * pos_ratio), 2)

            return {
                "primary": primary_agent,
                "secondary": secondary_agent,
                "confidence": confidence,
                "method": "keyword",
                "intent": intent,
                "matched_keywords": [kw for kw_list in hits.values() for kw in kw_list],
            }

        return None

    def _detect_intent(self, query: str) -> str:
        """通过关键词检测用户意图.

        操作类动词 → action;对比/分析/详解类 → action(需要结构化回答);
        简单查询 → query.
        """
        qlower = query.lower()
        for kw in INTENT_ACTION_KEYWORDS:
            if kw in qlower:
                return "action"
        for kw in INTENT_ANALYSIS_KEYWORDS:
            if kw in qlower:
                return "action"
        return "query"

    # ── LLM 路由 ──────────────────────────────────────────────

    def _is_short_confirm(self, query: str) -> bool:
        """检测是否是短确认词("需要""好的""可以""是的""对"等)."""
        confirm_words = {
            "需要", "要", "要的", "好的", "好", "好滴", "好呀",
            "可以", "行", "行吧", "ok", "OK", "Ok",
            "是的", "是", "是滴", "对", "对滴", "对的",
            "嗯", "嗯嗯", "没错", "正确", "搞", "整", "来吧",
            "创建", "提交", "帮我", "帮我弄", "帮忙",
        }
        stripped = query.strip()
        return stripped in confirm_words or len(stripped) <= 2

    def _context_route(self, query: str, history: list[dict]) -> dict[str, Any] | None:
        """从对话历史推断路由.查看最后几条 assistant 消息的引导语."""
        # 倒序找最近的 assistant 消息(可能有工具调用分隔符)
        last_assistant = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant" and msg.get("content"):
                last_assistant = msg["content"]
                break

        if not last_assistant:
            return None

        # 检测引导关键词 -- 按优先级匹配(IT 放最后,避免"工单"泛匹配劫持法务/HR 上下文)
        agent_key = None
        last_lower = last_assistant.lower()
        if any(kw in last_lower for kw in [
            "请假", "年假", "病假", "事假", "调休", "产假", "陪产假",
            "婚假", "提交请假", "请假申请",
        ]):
            agent_key = "hr_agent"
        elif any(kw in last_lower for kw in [
            "报销", "出差", "采购", "预算", "差旅", "发票",
            "招待费", "住宿标准", "提交报销",
        ]):
            agent_key = "finance_agent"
        elif any(kw in last_lower for kw in [
            "合同", "合规", "法务", "保密", "竞业", "数据保护",
            "知识产权", "合同审批",
        ]):
            agent_key = "legal_agent"
        elif any(kw in last_lower for kw in [
            "报修", "工单", "it工单", "蓝屏", "修电脑",
            "设备故障", "网络问题", "密码忘了", "软件安装",
            "报修工单", "提交工单", "创建报修",
        ]) and not any(kw in last_lower for kw in [
            "法务", "法律", "合同", "合规", "请假", "报销",
        ]):
            agent_key = "it_agent"

        if agent_key:
            return {
                "primary": agent_key,
                "secondary": None,
                "confidence": 0.85,
                "method": "context",
                "intent": "action",
                "action_card": _detect_action_card(last_assistant, "action", self.client),
            }
        return None

    def _llm_route(self, query: str, history: list[dict] | None = None) -> dict[str, Any]:
        """LLM 意图分类."""
        agent_descriptions = "\n".join(
            f"- {name}: {info.description}"
            for name, info in AGENT_REGISTRY.items()
            if name != "fallback"
        )

        # 带上最近对话历史,让 LLM 理解短应答的上下文
        history_text = ""
        if history:
            recent = history[-4:]  # 最近 4 轮
            history_text = "\n".join(
                f"{'👤' if m['role'] == 'user' else '🤖'}: {m.get('content', '')[:200]}"
                for m in recent
            )
            history_text = f"""## 对话历史

{history_text}

"""

        user_prompt = f"""## 专家能力

{agent_descriptions}

{history_text}## 用户问题

{query}"""

        response = call_llm_with_retry(
            self.client,
            model=self.model or config.llm_model,
            messages=[
                {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.llm_routing_temperature,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            return {
                "primary": "fallback",
                "secondary": None,
                "confidence": 0.0,
                "method": "llm",
                "intent": "action",
                "error": f"JSON 解析失败: {content[:100]}",
            }

        # Pydantic schema 校验 + 重试(一次)
        from src.agents.validation import validate_route_result
        validated = validate_route_result(result)
        primary = validated["primary"]
        secondary = validated["secondary"]
        intent = validated["intent"]

        # 如果校验失败且 primary 无效,重试一次
        if primary == "fallback" and validated["confidence"] < 0.4:
            logger.warning("LLM route validation failed, retrying once...")
            try:
                retry_resp = call_llm_with_retry(
                    self.client,
                    model=self.model or config.llm_model,
                    messages=[
                        {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                retry_content = retry_resp.choices[0].message.content or "{}"
                retry_result = json.loads(retry_content)
                validated = validate_route_result(retry_result)
                primary = validated["primary"]
                secondary = validated["secondary"]
                intent = validated["intent"]
            except Exception:
                pass

        # 校验 primary 是否在注册表中
        if primary not in AGENT_REGISTRY:
            primary = "fallback"

        if secondary and secondary not in AGENT_REGISTRY:
            secondary = None

        return {
            "primary": primary,
            "secondary": secondary,
            "confidence": float(validated.get("confidence", 0.5)),
            "method": "llm",
            "intent": intent,
            "raw": result,
        }

    # ── 后续扩展(第3周接入真实 Agent 后) ───────────────────

    def chat(self, query: str) -> str:
        """用户对话入口(骨架 -- Agent 就绪后接入真实执行)."""
        route_result = self.route(query)

        if route_result["primary"] == "fallback":
            return "这个问题不在我的知识范围内.你可以询问以下领域的问题:请假/报修,合规/合同,人事政策."

        agent_name = route_result["primary"]
        display = AGENT_REGISTRY[agent_name].display_name
        method = route_result["method"]
        confidence = route_result["confidence"]

        return (
            f"[路由] → {display} ({agent_name})\n"
            f"[方法] {method}  |  置信度 {confidence:.0%}\n"
            f"[提示] Agent 集成进行中,第3周完成后返回真实回答."
        )
