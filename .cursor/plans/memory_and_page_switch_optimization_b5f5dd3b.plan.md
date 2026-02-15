---
name: Memory and page switch optimization
overview: "Reduce local memory usage (currently ~1GB+) and page switch delay by: (1) dynamically loading the editor page so Monaco and React Flow load only when opening the editor; (2) adding route-level loading UI so navigation feels instant; (3) optional backend and dev script tweaks."
todos: []
isProject: false
---

# 内存与页面切换延迟优化

## 现状与原因

### 内存 (~1GB+)

- **前端**：`next dev`（Node + Turbopack）通常占 400–800MB；且 **(main)** 下的所有页面会参与构建，编辑器页引入了 **Monaco Editor** 和 **@xyflow/react**，体积和运行时内存都很大，即使用户不打开编辑器也会被算进 dev 的上下文。
- **后端**：`uvicorn app.main:app --reload` 单进程约 100–250MB。
- 若用 **Docker** 跑本地（`local/docker-compose.yml`），还有容器与镜像开销。

### 页面切换延迟

- **没有路由级 loading**：未使用 `loading.tsx`，切换路由时需等新页面 chunk 下载并执行完才渲染，中间没有占位，体感“卡一下”。
- **编辑器页过重**：`[frontend/src/app/[locale]/(main)/teams/[teamId]/editor/page.tsx](frontend/src/app/[locale]/(main)`/teams/[teamId]/editor/page.tsx) 直接静态 import `@xyflow/react` 和 `@monaco-editor/react`，该 chunk 很大；若被预加载或放在大 bundle 里，会拖慢其他页面切换。
- **整站 (main) 共享同一 layout**：每次切换页面都会 re-render 一次 MainLayoutClient + Sidebar + Header，但主要延迟来自 chunk 加载和重组件，而非 layout 本身。

---

## 优化方案

### 1. 编辑器页改为动态加载（减内存 + 减切换延迟）

**目标**：Monaco 和 React Flow 只在用户进入编辑器时加载，不进入则不占内存、不拖慢其他路由。

**做法**：用 `next/dynamic` 把编辑器**整页**或**内部重组件**做 dynamic import（`ssr: false` 可选，因编辑器纯客户端）。

- 在 `**[frontend/src/app/[locale]/(main)/teams/[teamId]/editor/page.tsx](frontend/src/app/[locale]/(main)`/teams/[teamId]/editor/page.tsx)** 中：
  - 要么将当前 `EditorPage` 抽到单独组件文件（如 `EditorPageContent.tsx`），再在 `page.tsx` 里用 `dynamic(() => import("./EditorPageContent"), { ssr: false, loading: () => <EditorPageSkeleton /> })` 渲染；
  - 要么在 `editor/page.tsx` 内把使用 React Flow 和 Monaco 的那块 UI 抽成一个子组件，对该子组件做 `dynamic(..., { ssr: false })`，页面其余部分（标题、返回按钮等）保留静态。
- 增加一个简单的 **EditorPageSkeleton**（例如左侧列表骨架 + 右侧空白或条纹），在 `loading` 时显示，避免白屏。

**效果**：首屏和未打开编辑器时的 JS 体积与内存更小；进入编辑器时才有一次较大 chunk 加载，其余页面切换更快。

---

### 2. 为 (main) 增加 loading.tsx（减轻“卡一下”的体感）

**目标**：路由切换时立即显示占位，而不是等新页面 chunk 跑完才出内容。

**做法**：在 `**[frontend/src/app/[locale]/(main)/loading.tsx](frontend/src/app/[locale]/(main)`/loading.tsx)** 新建文件，导出一个简单的 loading UI（例如与 MainLayout 一致的左侧边栏占位 + 右侧内容区骨架或 spinner）。Next 会在 (main) 下任意子路由切换时先显示该 loading，再替换为实际页面。

**效果**：点击导航后立刻有反馈，体感延迟明显下降。

---

### 3. 可选：其他重页面的轻量动态加载

若仍觉得会议详情等页面切换慢，可对 `**[frontend/src/app/[locale]/(main)/teams/[teamId]/meetings/[meetingId]/page.tsx](frontend/src/app/[locale]/(main)`/teams/[teamId]/meetings/[meetingId]/page.tsx)** 做类似处理：把主体内容抽成 `MeetingDetailContent`，用 `dynamic(..., { loading: () => <MeetingDetailSkeleton /> })` 包裹。优先级可放在编辑器优化之后，按需做。

---

### 4. 可选：后端与本地脚本（控制内存与进程）

- **后端**：当前单 worker，无需改。若将来有多 worker，本地可只开 1 个。
- **本地 dev 脚本**：在 `**[local/package.json](local/package.json)**` 的 `dev:frontend` 里可加 `NODE_OPTIONS=--max-old-space-size=512`（或 768）以限制 Node 堆内存，避免 dev 无上限涨到 1GB+；若构建或热更时报 OOM，再适当调大或去掉。
- **Docker**：若用 `**[local/docker-compose.yml](local/docker-compose.yml)**` 部署，前端服务可设置 `NODE_OPTIONS=--max-old-space-size=512`（环境变量），同样起到上限作用。生产镜像已是 `output: "standalone"`，生产通常用 `next start`，内存相对可控。

---

## 实施顺序建议


| 步骤  | 内容                                                               | 预期                        |
| --- | ---------------------------------------------------------------- | ------------------------- |
| 1   | (main) 下新增 `loading.tsx`                                         | 页面切换立即有占位，体感更流畅           |
| 2   | 编辑器页 Monaco + React Flow 改为 dynamic import，并加 EditorPageSkeleton | 降低常驻内存，其他路由切换更快           |
| 3   | 可选：会议详情页 dynamic + skeleton                                      | 进一步减少大 chunk 对切换的影响       |
| 4   | 可选：`dev:frontend` 或 Docker 中设置 `NODE_OPTIONS`                    | 限制 Node 内存，避免 dev 占满 1GB+ |


---

## 涉及文件


| 文件                                                                                 | 变更                                                         |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `frontend/src/app/[locale]/(main)/loading.tsx`                                     | 新建：路由级 loading 组件                                          |
| `frontend/src/app/[locale]/(main)/teams/[teamId]/editor/page.tsx`                  | 使用 `next/dynamic` 加载编辑器内容，并增加 loading 占位                   |
| （可选）`frontend/src/app/[locale]/(main)/teams/[teamId]/editor/EditorPageContent.tsx` | 若整页动态加载：从 page 抽出的编辑器主体                                    |
| （可选）`local/package.json`                                                           | `dev:frontend` 中增加 `NODE_OPTIONS=--max-old-space-size=512` |
| （可选）`local/docker-compose.yml`                                                     | 为 frontend 服务增加 `NODE_OPTIONS` 环境变量                        |


---

## 注意事项

- 使用 `dynamic(..., { ssr: false })` 时，编辑器页在服务端不渲染该块，对 SEO 无影响（编辑器本身是后台能力）。
- 若 next-intl 的 locale 在 `[locale]` 中，loading 组件无需单独取 locale，沿用 layout 即可；若 loading 里需要文案，可用简单占位或与现有 i18n 一致。
- 调整 `max-old-space-size` 后若出现 OOM，可改为 768 或 1024，或仅在 Docker 中限制、本地 dev 不限制。

