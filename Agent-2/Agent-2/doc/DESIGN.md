# Travel Planning Agent Design System

This file defines the product design direction for the Travel Planning Agent workspace. Use it as the primary UI reference before editing `fastapi/static/index.html` or any future frontend surface.

## Product Positioning

The product is an itinerary generation and revision workspace, not a broad travel discovery portal.

Core user job:

1. Describe one trip in natural language.
2. Let the agent collect missing constraints.
3. Generate a usable first itinerary.
4. Revise the itinerary through follow-up instructions.
5. Clearly see what changed and whether the plan is executable.

The interface should feel like a calm planning desk: structured, trustworthy, warm, and map-aware. It should not feel like a marketing homepage, a generic chatbot, or a raw debug console.

## Target Audience

- Independent travelers who want a practical plan without reading many guides.
- Light travel users who need a reliable draft quickly.
- Families and groups who care about pace, comfort, budget, and route efficiency.
- Couples or friends who care about food, atmosphere, photo spots, and local experience.
- Business travelers extending a work trip with limited spare time.

Primary context: users are making decisions before or during a trip, often under time pressure. They need clarity more than decoration.

## Brand Voice

Use a voice that is:

- Clear: every screen should answer "what stage am I in?" and "what should I do next?"
- Practical: prioritize executable route, time, budget, pace, and tradeoffs.
- Warm: travel planning should feel less stressful, but avoid cute or playful copy.
- Evidence-aware: surface warnings, assumptions, and route constraints plainly.

Avoid:

- Over-promising AI magic.
- Long explanatory paragraphs.
- Internal backend language in primary UI, such as raw JSON, requirement id, itinerary id, generator internals.
- Generic slogans like "unlock your journey" or "AI-powered travel companion".

## Visual Direction

Design concept: "field notebook meets route operations desk".

The UI should combine:

- A light, paper-like workspace for reading and editing travel plans.
- Muted map colors that suggest terrain, route, time, and destination.
- Dense but calm information hierarchy for itinerary details.
- One strong action color for generation/revision.

The current warm paper, teal, rust, sage, and gold direction is appropriate. Refine it rather than replacing it with neon, purple gradients, or pure grayscale.

## Color Tokens

Prefer OKLCH for new CSS tokens. Hex values are acceptable only when integrating with existing code.

Core palette:

```css
:root {
  color-scheme: light;

  --color-bg: oklch(0.955 0.018 85);
  --color-surface: oklch(0.985 0.012 82 / 0.86);
  --color-surface-strong: oklch(0.99 0.018 82);
  --color-field: oklch(0.995 0.006 95 / 0.78);

  --color-ink: oklch(0.23 0.025 160);
  --color-ink-soft: oklch(0.42 0.028 160);
  --color-muted: oklch(0.58 0.022 155);
  --color-line: oklch(0.32 0.025 160 / 0.14);
  --color-line-strong: oklch(0.32 0.025 160 / 0.24);

  --color-action: oklch(0.48 0.09 185);
  --color-action-strong: oklch(0.36 0.075 185);
  --color-rust: oklch(0.55 0.12 45);
  --color-gold: oklch(0.66 0.095 82);
  --color-sage: oklch(0.89 0.035 150);
  --color-danger: oklch(0.48 0.14 28);
  --color-success: oklch(0.48 0.09 155);
}
```

Usage rules:

- Backgrounds should stay warm and lightly tinted, never pure white.
- Teal is reserved for primary action, active route state, and map connection state.
- Rust marks attention, warnings, stage labels, or revision highlights.
- Gold is used sparingly for route metadata, day markers, or budget emphasis.
- Do not use gradient text.
- Do not make the interface mostly beige; pair warm paper surfaces with green-gray text, teal actions, and rust accents.

## Typography

The app is a product workspace, so typography must be readable at small sizes.

Recommended stack:

```css
--font-ui: "Aptos", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
--font-display: "Georgia", "Times New Roman", "Songti SC", serif;
--font-mono: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
```

Rules:

- Use UI sans for controls, lists, metadata, and chat messages.
- Use the display serif only for product title, section titles, and empty-state headings.
- Keep Chinese body text at 13px to 15px in compact panels.
- Use 11px to 12px uppercase English labels only as small metadata, not as primary navigation.
- Do not scale app UI text with viewport width.
- Do not use letter spacing below 0. Use widened letter spacing only for short eyebrow labels.

## Layout System

The main workspace should use three stable regions on desktop:

1. Left: conversation and user input.
2. Center: map or route workspace.
3. Right: itinerary summary, day list, warnings, and change summary.

Desktop grid:

```css
.app {
  height: 100vh;
  padding: 14px;
  display: grid;
  grid-template-columns: minmax(330px, 410px) minmax(460px, 1fr) minmax(330px, 410px);
  gap: 14px;
}
```

Responsive behavior:

- Below 1180px, stack panels vertically in this order: conversation, itinerary, map.
- Do not hide the itinerary behind tabs on mobile unless the map becomes unusable.
- Keep input controls reachable without scrolling through the full itinerary.
- Avoid nested cards. Panels are enough; inside panels, use dividers, compact groups, and list rows.

Spacing scale:

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 24px;
--space-6: 32px;
--space-7: 48px;
```

Use `gap` for sibling spacing. Avoid arbitrary margins unless the element needs optical correction.

## Interface States

The UI must make these states explicit:

### Not Started

No session, no requirement, no itinerary.

Show:

- A direct prompt: "用一句话告诉我你的旅行想法".
- Two or three high-quality example inputs.
- Empty itinerary state explaining that days, route points, and warnings will appear after generation.

Do not show backend ids as the main content.

### Collecting Requirements

Requirement exists, itinerary does not.

Show:

- Missing fields such as destination, days, budget, people, pace.
- Why the missing field matters.
- A primary action that implies the next generated output.

The composer placeholder should ask for the missing information, not repeat the generic first prompt.

### First Itinerary Generated

Itinerary exists for the first time.

Show:

- Trip title and one-sentence summary.
- Day list with theme, time blocks, places, and notes.
- Warnings and assumptions.
- Quick revision actions: "轻松一点", "压低预算", "增加拍照点", "减少路程", "下雨重排".

### Revising

Existing itinerary plus new user instruction.

Show:

- The revision goal.
- A loading state that says the current plan is being adjusted, not regenerated from scratch.
- After completion, show a "本轮修改" section with changed days, budget or pace impact, and any tradeoffs.

## Components

### Primary Button

Use for one main next action per panel: send plan, generate itinerary, apply revision.

Visual:

- Teal background.
- Light text.
- 8px radius.
- Subtle lift on hover.

Do not create multiple competing primary buttons in the same visual group.

### Secondary Button

Use for load session, new session, fit route, locate, clear.

Visual:

- Light surface.
- 1px border.
- Ink text.

### Ghost Button

Use for low-risk contextual actions inside maps or itinerary rows.

Visual:

- Transparent or lightly tinted surface.
- Clear hover state.

### Composer

The composer is the main interaction surface.

Rules:

- Placeholder must reflect current stage.
- Minimum height 112px on desktop, 96px on mobile.
- Support `Ctrl/Cmd + Enter` submit.
- Status text should be direct: "正在生成行程...", "正在根据你的修改重排...", "请补充预算或出行天数。"

### Chat Messages

Messages should support planning progress, not imitate a casual messenger too strongly.

Rules:

- User message aligned right, assistant left.
- Assistant messages may include compact structured blocks.
- Long generated itinerary content should appear in the itinerary panel, not only inside chat.

### Itinerary Day Row

Each day should include:

- Day number.
- Theme.
- Main route or area.
- Time-blocked items.
- Pace or warning markers when relevant.

Avoid oversized cards for each item. Use compact rows with clear separators.

### Warning

Warnings are product guidance, not errors.

Examples:

- "第 2 天路程较长，建议减少一个远距离景点。"
- "预算未填写，餐饮和交通费用为估算。"
- "当前路线依赖地图服务结果，实际时间可能受交通影响。"

Visual:

- Rust or warm amber text/accent.
- Light tinted surface.
- No thick left border.

### Debug Metadata

Session ID, Requirement ID, Itinerary ID, raw JSON, and generator type are useful for development.

Rules:

- Keep them collapsed or in a low-priority debug section.
- Never place raw ids above the user's itinerary.
- Translate generator type for users if shown: "智能生成", "规则生成", "手动调整".

## Map Design

The map is a planning aid, not decoration.

Rules:

- Route markers should be numbered and match itinerary day/item order.
- A selected itinerary row should highlight the matching marker.
- Map controls should be compact and predictable.
- 2D/3D toggle should use an icon or short label with tooltip when possible.
- Search results should not erase the generated route unless the user explicitly clears or replaces it.

Map color relationship:

- Route line: teal.
- Active marker: teal with light inner ring.
- Warning or changed route point: rust.
- Neutral place marker: paper surface with ink text.

## Motion

Use restrained motion to show state changes:

- Message entry: 160ms to 240ms fade/rise.
- Button hover: small translateY and shadow change.
- Itinerary updated: brief background pulse on changed rows.
- Map marker selection: small scale or ring change.

Avoid long decorative animations. Do not animate layout in a way that moves the composer while the user is typing.

## Accessibility

- Maintain readable contrast on paper surfaces.
- All buttons and inputs must have visible focus states.
- Do not rely on color alone for warnings or status; include text.
- Keep clickable targets at least 36px high in dense desktop panels and 44px on mobile.
- Ensure Chinese text never overflows buttons or pills.

## Content Rules

Preferred Chinese labels:

- "行程工作台"
- "开始规划"
- "继续修改"
- "生成初版行程"
- "本轮修改"
- "行程看板"
- "路线点位"
- "待补充信息"
- "风险提醒"

Avoid:

- "Travel Intelligence Console" as the main product label.
- "Session", "Requirement", "Itinerary" as primary headings for users.
- Raw technical copy in empty states.
- Long onboarding instructions.

## Implementation Checklist

Before shipping a UI change, check:

- Does the page clearly show the current planning stage?
- Can the user submit a first travel request without reading instructions?
- After generation, is the itinerary easier to read in the side panel than in chat?
- During revision, can the user see what changed?
- Are backend ids and raw JSON visually de-emphasized?
- Does the mobile layout preserve input, itinerary, and map access?
- Are colors still balanced across paper, teal, rust, sage, and ink rather than drifting into a one-note beige UI?
