# 会议页面与议程体验优化

## 1. AI 生成议程时一并生成会议标题

**后端**

- **[`backend/app/core/agenda_proposer.py`](backend/app/core/agenda_proposer.py)**
  - 在 `auto_generate` 中，在发给 LLM 的 user_message 里增加要求：返回的 JSON 中增加 **`title`**（简短会议标题，一行）。
  - 在 `_parse_agenda_json` 中解析 `data.get("title", "")` 并加入返回的 dict。
  - 在 `chain_recommend` 中同样在 prompt 里要求返回 `title`，并确保解析结果中包含 `title`。
- **[`backend/app/schemas/meeting.py`](backend/app/schemas/meeting.py)**
  - 在 **AgendaAutoResponse** 中增加字段：`title: str = ""`。

**前端**

- **前端类型定义**（如 `frontend/src/types/index.ts` 中与 AgendaAutoResponse 对应的类型）：增加 `title?: string`。
- **[`frontend/src/components/NewMeetingDialog.tsx`](frontend/src/components/NewMeetingDialog.tsx)**
  - 在 `handleGenerateAgenda` 里，用接口返回的 `result` 更新表单时，若存在 `result.title` 则写入 `form.title`（避免空字符串覆盖用户已填标题）。

**测试**

- 在 **[`backend/tests/test_enhanced_meetings.py`](backend/tests/test_enhanced_meetings.py)**（或现有 mock 议程生成的测试）中，让 mock 返回的 JSON 包含 `"title": "..."`，并断言接口返回中包含 title。

---

## 2. 按轮次分块显示会议消息（每轮一个区块）

**前端 - 会议详情页**

- **[`frontend/src/app/[locale]/(main)/teams/[teamId]/meetings/[meetingId]/page.tsx`](frontend/src/app/[locale]/(main)/teams/[teamId]/meetings/[meetingId]/page.tsx)**
  - 用 `useMemo` 将 `allMessages` 按 `round_number` 分组，得到 `byRound`（如 `Map<number, MeetingMessage[]>` 或 `[roundNum, msgs][]`，按轮次排序）。
  - 在「聊天」Tab 内不再对 `allMessages` 做单列表循环，改为按轮次渲染：
    - 对每一轮 `[roundNum, msgs]` 渲染一个**区块**，区块标题为「第 N 轮」（`roundNum === 0` 可显示为「会前/上下文」等）。
    - 每个区块内沿用当前的消息卡片样式（头像、姓名、角色、内容等）。
  - 保持现有 `speaking`、`liveMessages`、滚动到底等逻辑；确保 `liveMessages` 已合并进 `allMessages`并参与分组（它们已有 `round_number`）。

**体验细节**

- 轮次区块用标题区分即可；若轮次较多，可用 **Collapsible** 折叠历史轮次，仅展开当前轮。
- 顺序：round 0（若有）在前，再 1、2、…，保证最新一轮在底部，便于滚动定位。

---

## 3. 会议页展示「会议目标」与「预期成果」

**前端 - 会议详情页**

- **[`frontend/src/app/[locale]/(main)/teams/[teamId]/meetings/[meetingId]/page.tsx`](frontend/src/app/[locale]/(main)/teams/[teamId]/meetings/[meetingId]/page.tsx)**
  - 在页面头部区域（例如现有议程行下方或轮次/描述行下方）增加一块**目标与预期成果**：
    - **会议目标**：`meeting.agenda || meeting.description`，有则显示并加标签（如「目标」）。
    - **预期成果**：`meeting.output_type`（如「代码」「报告」「论文」）加标签。
    - **待回答问题**（可选）：若 `meeting.agenda_questions?.length > 0`，显示「需回答的问题」并列出。
  - 样式与现有头部一致（如 `text-sm`、`text-muted-foreground`），可单行或小卡片，不喧宾夺主。

**文案与 i18n**

- 在 **[`frontend/src/messages/en.json`](frontend/src/messages/en.json)**（及 `zh.json` 等）的 meeting 命名空间下增加：「目标」「预期成果」「待回答问题」「第 N 轮」「会前」等 key，并在组件中使用。

---

## 涉及文件一览

| 类别 | 文件 | 修改内容 |
|------|------|----------|
| 后端 | [backend/app/core/agenda_proposer.py](backend/app/core/agenda_proposer.py) | prompt 与返回值增加 `title`；`_parse_agenda_json` 解析并返回 `title`。 |
| 后端 | [backend/app/schemas/meeting.py](backend/app/schemas/meeting.py) | AgendaAutoResponse 增加 `title: str = ""`。 |
| 前端 | 类型定义（如 frontend/src/types/index.ts） | 议程自动生成响应类型增加 `title?: string`。 |
| 前端 | [frontend/src/components/NewMeetingDialog.tsx](frontend/src/components/NewMeetingDialog.tsx) | 生成议程后若有 result.title 则回填到表单 title。 |
| 前端 | [frontend/.../meetings/[meetingId]/page.tsx](frontend/src/app/[locale]/(main)/teams/[teamId]/meetings/[meetingId]/page.tsx) | 消息按轮分组渲染；增加目标/预期成果区块；使用上述 i18n key。 |
| 前端 | [frontend/src/messages/en.json](frontend/src/messages/en.json) 及 zh | 新增：目标、预期成果、待回答问题、第 N 轮、会前 等。 |
| 测试 | [backend/tests/test_enhanced_meetings.py](backend/tests/test_enhanced_meetings.py) 等 | 断言议程接口在 mock 返回 title 时响应包含 title。 |

---

## 可选增强

- **chain_recommend**：若前端有「基于上次会议推荐下次议程」的流程，后端 chain_recommend 同样请求并解析 `title`，弹窗可预填标题。
- **轮次折叠**：轮次很多时，可将各轮做成可折叠区块，默认展开最新一轮，减少滚动量。
