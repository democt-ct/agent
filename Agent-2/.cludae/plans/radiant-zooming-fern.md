# 五维标签体系 + 双阶段渐进式推荐 重构计划

## Context

当前 POI 推荐存在两个核心问题：
1. 分类太粗——单个 `kind` 字段只有十几个值，无法表达"自然风光+拍照打卡"或"历史文化+带长辈"这类组合偏好
2. 冷启动推荐差——用户第一次模糊提问时，系统不分青红皂白推荐一堆小众地点，没有引导用户补充偏好

本次重构引入五维标签体系和双阶段推荐逻辑，在保持现有 AMap 搜索管线和 reflexion 引擎兼容的前提下，增强推荐的精准度和体验。

---

## 修改文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `fastapi/poi_tags.py` | **新建** | 五维标签数据模型、映射表、规则推断函数 |
| `fastapi/intent_extractor.py` | **新建** | 意图清晰度评估、五维偏好提取、追问问题生成 |
| `fastapi/models/schemas.py` | 修改 | 新增 POITagSchema，扩展现有模型 |
| `fastapi/core.py` | 修改 | 管线集成：候选召回、POI 装饰、排序、两阶段分支 |
| `fastapi/reflexion_engine.py` | 修改 | 用 function 维度替代 kind 做重叠检测和替换评分 |

---

## Phase 1: 基础模块（不影响现有管线）

### 1.1 新建 `fastapi/poi_tags.py`

**数据模型：**

```python
class FunctionDimension(str, Enum):
    ATTRACTION = "attraction"
    FOOD = "food"
    STAY = "stay"
    TRANSPORT = "transport"

class TimeDimension(BaseModel):
    duration_hours: float = 2.0
    best_time: List[str] = ["上午", "下午"]

class BudgetDimension(BaseModel):
    price_level: int = 2  # 1=免费, 2=低消, 3=中等, 4=昂贵

class POITag(BaseModel):
    function: FunctionDimension = FunctionDimension.ATTRACTION
    experience: List[str] = []   # 从 EXPERIENCE_VOCAB 取值
    crowd: List[str] = []        # 从 CROWD_VOCAB 取值
    time: TimeDimension = TimeDimension()
    budget: BudgetDimension = BudgetDimension()
    is_landmark: bool = False
    legacy_place_kind: str = ""  # 向后兼容
```

**受控词表：**
```python
EXPERIENCE_VOCAB = [
    "自然风光", "拍照打卡", "历史文化", "特种兵", "慢节奏",
    "亲子互动", "美食探索", "夜生活", "文艺小资", "购物休闲",
]
CROWD_VOCAB = [
    "亲子友好", "情侣约会", "带长辈", "单人", "朋友聚会",
]
```

**映射表：**
- `LEGACY_KIND_TO_FUNCTION`: old kind → FunctionDimension（museum→ATTRACTION, food_poi→FOOD, cafe→FOOD, bar→FOOD, shopping→ATTRACTION, lodging→STAY, transport→TRANSPORT）
- `FUNCTION_TO_LEGACY_KIND(tag: POITag) -> str`: 反向映射，用 experience 辅助推断（如 ATTRACTION+"历史文化"→"museum"，FOOD+"文艺小资"→"cafe"）

**核心函数：**

```python
def infer_poi_tags(
    name: str, category: str = "", query: str = "",
    legacy_place_kind: str = "",
) -> POITag
```
- 替代并兼容 `_infer_planner_place_kind`，用相同的正则级联确定 function
- 根据关键词推断 experience（museum→["历史文化"], park→["自然风光"], night_view→["夜生活"], cafe→["文艺小资"], food→["美食探索"] 等）
- 根据关键词推断 crowd（"亲子"/"儿童"→["亲子友好"], "情侣"→["情侣约会"] 等）
- 根据 function 推断 time.duration_hours（museum=2.5, park=2.0, food=1.5 等）和 time.best_time（复用 `_preferred_slots_for_place_kind` 逻辑）
- 根据 category 推断 budget.price_level（"免费"/"公园"→1, 默认→2）
- is_landmark: 暂时默认 False，后续由管线中 AMap confidence + 是否在 fallback queries 中决定

### 1.2 新建 `fastapi/intent_extractor.py`

**数据模型：**

```python
class IntentClarity(str, Enum):
    VAGUE = "vague"       # Stage 1: 几乎无偏好信息
    PARTIAL = "partial"   # 有部分偏好
    CLEAR = "clear"       # Stage 2: 足够做精排

class FiveDimPreference(BaseModel):
    function_weights: Dict[str, float] = {"attraction": 1.0}
    experience_desired: List[str] = []
    crowd_required: List[str] = []
    time_preference: Optional[TimeDimension] = None
    budget_preference: Optional[BudgetDimension] = None
    landmark_only: bool = False  # Stage 1 时为 True

class IntentExtractionResult(BaseModel):
    clarity: IntentClarity
    preference: FiveDimPreference
    follow_up_questions: List[str] = []
```

**核心函数：**

```python
def assess_intent_clarity(
    requirement_payload: Dict[str, Any],
    message: str,
) -> IntentExtractionResult
```

评分规则：
- must_have 非空：每项 +2
- memory_profile.preferences 有非 None 值：每项 +1
- budget_level 有值：+1
- theme ≠ "general"：+1
- trip_style ≠ "moderate"：+1

阈值：≤2 → VAGUE, 3-5 → PARTIAL, ≥6 → CLEAR

VAGUE 时设 `landmark_only=True`，生成追问问题（从缺失维度选：预算、人群、体验偏好、节奏）

**映射现有偏好到五维：**
```python
def _map_requirement_to_fivedim(requirement_payload) -> FiveDimPreference
```
- must_have 中 "美食" → function_weights["food"] += 1, experience += ["美食探索"]
- must_have 中 "夜景" → experience += ["夜生活"], time.best_time += ["夜间"]
- memory low_fatigue=True → experience += ["慢节奏"]
- memory family_friendly=True → crowd += ["亲子友好"]
- memory budget_level="premium" → budget_preference.price_level=3

### 1.3 修改 `fastapi/models/schemas.py`

- 新增 `POITagSchema`（与 `poi_tags.py` 的 `POITag` 对应）
- `PoiPlaceCandidate` 加字段 `poi_tag: Optional[POITagSchema] = None`
- `PlannerRequirementV2` 加字段 `poi_preference: Optional[Dict[str, Any]] = None`, `intent_clarity: Optional[str] = None`, `follow_up_questions: List[str] = []`
- `PlannerCandidateRecallItem` 加字段 `poi_tag: Optional[POITagSchema] = None`

---

## Phase 2: 管线集成（core.py）

### 2.1 `_run_tool_using_chat_workflow` 中插入两阶段分支

**位置**：requirement_interpret 之后、city_recall 之前（约 core.py:2991 后）

```python
from intent_extractor import assess_intent_clarity
intent_result = assess_intent_clarity(requirement_payload, message)
```

**Stage 1 分支**（VAGUE/PARTIAL + landmark_only）：
- `_build_candidate_recall_prompt` 追加规则："只推荐城市核心地标，不推荐小众/咖啡/酒吧"
- 候选解析后，过滤只保留 `poi_tag.is_landmark == True` 或 confidence 最高的前 N 个
- `_generate_day_segment_plan` 正常执行（用地标候选）
- `assistant_text` 中追加追问问题

**Stage 2 分支**（CLEAR 或 PARTIAL 但有明确偏好）：
- 正常召回候选
- 解析后加一步：`_rank_validated_candidates_by_fivedim` 排序
- 后续流程不变

### 2.2 新增 `_rank_validated_candidates_by_fivedim`

```python
def _rank_validated_candidates_by_fivedim(
    validated_candidates: List[Dict[str, Any]],
    preference: FiveDimPreference,
) -> List[Dict[str, Any]]
```

排序公式：
```
score = (
  1.0 * function_match           # tag.function 在 preference.function_weights 中
+ 1.5 * jaccard(experience)       # experience 交集/并集
+ 1.2 * crowd_match               # crowd 有交集
+ 0.8 * time_fit                  # best_time 有交集
+ 1.0 * budget_fit               # price_level 匹配
+ 0.6 * landmark_bonus            # is_landmark
+ 0.3 * confidence                # AMap 原始 confidence
)
```

### 2.3 修改 `_build_candidate_recall_prompt`

新增可选参数 `intent_result: Optional[IntentExtractionResult] = None`

- VAGUE 时追加规则 8：只推荐核心地标
- CLEAR 时追加规则 8：用户偏好为 {json.dumps(preference)}，据此筛选
- JSON 输出结构中 kind 字段说明更新为包含 Function 维度值

### 2.4 修改 `_normalize_candidate_recall_entry`

推断 `place_kind` 后，调用 `infer_poi_tags()` 生成 `poi_tag`，存入返回的 dict

### 2.5 修改 `_decorate_validated_place`

新增可选参数 `poi_tag: Optional[POITag] = None`
- 如果未提供，用 `infer_poi_tags()` 推断
- 将 `poi_tag.dict()` 写入返回的 decorated dict
- `legacy_place_kind` 保持一致

### 2.6 修改 `_supplement_validated_candidates`

在提拔 backup 时，如果 requirement_payload 中有 `poi_preference`，用五维评分替代 `_backup_candidate_promote_score`

### 2.7 修改 `_fill_score`（`_enrich_itinerary_with_remaining_validated_candidates` 内）

同上：有 `poi_preference` 时用五维评分，否则用原有 kind bonus dict

### 2.8 追问问题输出

在 Stage 1 的 `assistant_text` 中追加 intent_result.follow_up_questions，引导用户补充偏好

---

## Phase 3: Reflexion 引擎适配

### 3.1 `validate_quality` — 重叠检测

当前检测 `kind in categories_seen`，改为同时检测 `function in functions_seen`：
- 用 `infer_poi_tags` 从 item 推断 POITag
- 如果 `tag.function` 重复，发 category_overlap issue
- 仍保留 kind 级别的重叠检测作为辅助

### 3.2 `_find_replacement` — 替换评分

当前 `kind_match = 25 if same_kind else 5`，改为：
```python
old_tag = infer_poi_tags(old_name, old_category, old_query, old_kind)
new_tag = infer_poi_tags(poi_name, poi_category, query, poi_kind)
kind_match = 25 if old_tag.function == new_tag.function else (
    15 if old_tag.legacy_place_kind == poi_kind else 5
)
kind_match += len(set(old_tag.experience) & set(new_tag.experience)) * 3
```

### 3.3 `SLOT_KIND_PREFERENCE` 保留

不动。`POITag.time.best_time` 是补充而非替代。

---

## Phase 4: 向后兼容保证

1. **place_kind 不删除**：`_decorate_validated_place` 仍然写入 `place_kind` 字段，reflexion_engine 和前端照常读取
2. **poi_tag 是附加字段**：新增到 POI dict 中，旧代码忽略它
3. **评分函数兼容**：无 `poi_preference` 时走原有逻辑，有时走五维逻辑
4. **LLM prompt 兼容**：kind 字段在 prompt 中保留，只是增加了 function 维度说明

---

## 验证方法

1. **单元测试**：`infer_poi_tags` 覆盖所有旧 kind → 新 function 映射 + experience/crowd 推断
2. **意图评估测试**：`assess_intent_clarity` 对各种输入（模糊/半明确/明确）返回正确的 clarity
3. **端到端测试**：
   - 模糊输入（"我想去绵阳玩"）→ Stage 1 → 只返回地标 + 追问问题
   - 明确输入（"带父母去绵阳，想看历史文化，不要太累，预算中等"）→ Stage 2 → 五维精排
4. **回归验证**：已有 test_travel_planning_pipeline.py 通过
