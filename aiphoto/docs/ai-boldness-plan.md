# AI 调色"质感差异化"实现方案

## 核心问题

当前 AI 输出的参数和手动微调几乎没有区别，原因是多层的：

1. **Prompt 心理暗示**：示例 JSON 的数字暗示了"保守是安全的"，AI 倾向于不冒险
2. **参数范围被低估**：brightness ±0.1 级别的调整肉眼几乎不可见，而预设里的 cinematic 用了 -0.2/+0.3 才有感觉
3. **缺乏场景感知分级**：欠曝的夜景和过曝的海滩场景，不应该用同一套力度
4. **没有"AI 签名"**：AI 调出来的结果应该有一种"这不是普通人会这样调"的组合感

---

## 目标效果定义

| | 手动调参 | AI 调参 |
|---|---|---|
| 典型特征 | 单参数线性调整，保守，对称 | 多维度组合，非对称，有方向感 |
| 亮度 | 拉个滑块到感觉舒服为止 | 基于像素分布决定，可能亮度-0.1 但阴影+25 |
| 色彩 | 饱和度+10 | 饱和度-5，色温+15，色调+8 构成特定色感 |
| 质感 | 对比度+10 | 对比度+20，锐度+15，高光-15 同时压制，制造"通透感" |
| 结果感知 | "看起来稍微好一点" | "哦这个调色有想法" |

---

## 实现方案（三层改造）

### 第一层：Prompt 大胆化

**改 `PROMPT_EDIT` 的调性**，去掉保守暗示，加入明确的"大胆"指令：

```
重要：调色要有明确的视觉冲击力，不能让人感觉"几乎没变化"。
- brightness 若需调整，幅度应在 ±0.2 以上才有感觉
- contrast 若需调整，±20 以上才明显
- 不要所有参数都用小数值，宁可几个参数用大值，也不要12个参数都是个位数
- 组合使用参数制造"质感"：例如要做通透感 = highlights-15 + shadows+20 + contrast+15 + sharpness+10 同时用
- 要让人一眼看出这张图被"AI调过了"
```

**加入场景-力度对照表**（prompt 里描述）：

| 场景 | 推荐力度策略 |
|------|-------------|
| 欠曝人像 | brightness+0.3~0.5, shadows+20~30, highlights-10 |
| 过曝户外 | brightness-0.2~0.4, highlights-20~30, contrast+15 |
| 灰暗风景 | contrast+25~40, saturation+15~25, sharpness+15~20 |
| 室内暖光 | temperature-15~25（拉回色温平衡），contrast+10 |
| 夜景城市 | contrast+35, brightness-0.1, vignette+30, sharpness+20 |
| 食物/静物 | temperature+10~20（暖色增食欲），saturation+15，sharpness+10 |

---

### 第二层：图片内容分析 → 参数力度分级

在后端 `auto_enhance` 增加**基于 OpenCV 的图像诊断**，输出更精准的分析数据传给 AI，让 AI 做有依据的大胆决策。

当前 `analysis_service` 已经输出 `issues` 列表，但 `auto_enhance` 的响应力度太小：

```python
# 当前：保守
if issue["type"] == "underexposed":
    enhancements["brightness"] = 0.3  # 太小

# 目标：基于严重程度分级
if issue["type"] == "underexposed":
    severity = issue.get("severity", 1.0)  # 0~1
    enhancements["brightness"] = 0.3 + severity * 0.3   # 0.3~0.6
    enhancements["shadows"] = 15 + severity * 20         # 15~35
    enhancements["contrast"] = severity * 15             # 0~15
```

分析数据需要增加 `severity`（严重程度 0~1）字段。

---

### 第三层：AI Prompt 注入图像诊断数据

**最关键的改造**：在调用 VisionService 之前，先用 OpenCV 做快速诊断，把诊断数字注入 prompt，让 AI 基于数据而非猜测做决策：

```python
# chat.py 中，调用 vision.chat 之前：

analysis = await analysis_service.quick_diagnose(image_path)
# 返回：{"brightness_mean": 87, "contrast_std": 31, "saturation_mean": 45, 
#        "issues": ["underexposed", "low_contrast"], "scene_hint": "outdoor_landscape"}

diagnosis_text = f"""
【图像诊断数据】
- 平均亮度：{analysis['brightness_mean']}/255（{'偏暗' if analysis['brightness_mean'] < 100 else '偏亮' if analysis['brightness_mean'] > 155 else '正常'}）
- 对比度：{analysis['contrast_std']}（{'偏低需增强' if analysis['contrast_std'] < 40 else '正常'}）
- 平均饱和度：{analysis['saturation_mean']}（{'偏灰' if analysis['saturation_mean'] < 60 else '正常'}）
- 检测到的问题：{', '.join(analysis['issues']) or '无明显问题'}
- 场景推测：{analysis['scene_hint']}

请根据以上数据，制定有针对性的、力度足够的调色方案。
"""

ai_response = await vision.chat(diagnosis_text + "\n" + msg + "\n\n" + PROMPT_EDIT, image_path)
```

这样 AI 拿到的是**真实的像素统计数据**，不是靠"看图猜"，输出的参数会更有依据，力度也更准确。

---

## 实现优先级

### P0（核心，改完立刻有感觉）
- [ ] 修改 `PROMPT_EDIT`：加入大胆调色指令 + 场景力度对照表
- [ ] `auto_enhance` 里增加 `severity` 分级，力度提升2倍

### P1（效果更稳定）
- [ ] `analysis_service` 增加 `quick_diagnose` 方法，输出亮度均值/对比度/饱和度/场景推测
- [ ] `chat.py` 注入诊断数据到 AI prompt

### P2（锦上添花）
- [ ] 增加"对比展示"：修改前/后左右滑动对比，让用户看到明确差异
- [ ] 每次 AI 调色后，把实际用的参数展示给用户（`实际应用：亮度+0.4 对比度+30...`）

---

## 预期效果

P0 完成后：同一张欠曝人像，AI 优化后亮度提升幅度从 +0.1 → +0.35~0.5，对比度从 +15 → +25~35，用户肉眼可见明显差异。

P1 完成后：AI 不再依赖"猜"——它知道这张图的亮度均值是 82，饱和度均值是 38，会精确输出对应的补偿参数，不同图片之间的参数差异会非常明显。
