# 云端部署（Vercel + Railway）

前端部署到 Vercel，后端部署到 Railway。**无需 Docker**，和 [claude_science_cs](../claude_science_cs) 一样简单。

---

## 1. 后端上 Railway

### 1.1 创建并部署

1. 打开 [railway.app](https://railway.app)，用 GitHub 登录。
2. **New Project** → **Deploy from GitHub repo** → 选择本仓库 `claude_science`。
3. 在该 Service：**Settings** → **Root Directory** 设为 **`backend`**（Railway 只从 backend 目录构建和运行）。
4. **Settings** → **Networking** → **Generate Domain**。记下生成的 URL（如 `https://xxx.up.railway.app`）。

### 1.2 环境变量

同一 Service 里：**Variables** → 添加：

| 变量 | 说明 | 示例 |
|------|------|------|
| `FRONTEND_URL` | 前端地址，用于 CORS（部署好前端后填 Vercel 地址） | `https://xxx.vercel.app` |
| `ENCRYPTION_SECRET` | 加密存储 API Key 的密钥（建议生产环境必填） | 用 `openssl rand -hex 32` 生成 |
| `OPENAI_API_KEY` | 可选，用 OpenAI 时填 | `sk-...` |
| `ANTHROPIC_API_KEY` | 可选，用 Claude 时填 | `sk-ant-...` |
| `DEEPSEEK_API_KEY` | 可选，用 DeepSeek 时填 | |
| `GITHUB_TOKEN` | 可选，用于 GitHub 导出 | |

默认使用 SQLite（数据在实例内，重启可能丢失）。若要持久化，可在 Railway 添加 **PostgreSQL** 插件，并设置 `DATABASE_URL`。

### 1.3 验证

浏览器打开 `https://<你的-railway-域名>/health`，应看到 `{"status":"healthy", "checks": {...}, "version": "1.0.0"}` 之类的 JSON。

---

## 2. 前端上 Vercel

### 2.1 创建项目

1. 打开 [vercel.com](https://vercel.com)，用 GitHub 登录。
2. **Add New** → **Project** → 导入本仓库 `claude_science`。
3. **Root Directory** 设为 **`frontend`**（点 Edit 后设置并保存）。

### 2.2 环境变量

在项目 **Settings** → **Environment Variables** 中添加：

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_URL` | 后端 API 根地址（需带 `/api`），如 `https://xxx.up.railway.app/api` |

### 2.3 部署

保存后部署（或 push 触发部署）。用 Vercel 给的 URL 打开应用。

---

## 3. 前后端打通

在 Railway 的 **Variables** 里把 **`FRONTEND_URL`** 设为你的 Vercel 地址（如 `https://你的项目.vercel.app`），这样 CORS 会放行前端来源。

如有 Vercel 预览域名（如 `*-git-*.vercel.app`），需要同样加入 CORS：在 **Variables** 里设置  
`CORS_ORIGINS` 为 JSON 数组，例如：`["https://你的项目.vercel.app","https://xxx-git-xxx.vercel.app"]`。  
只用一个生产域名时，只设 **`FRONTEND_URL`** 即可。

---

## 4. 小结

| 组件 | 平台 | 根目录 | 关键环境变量 |
|------|------|--------|--------------|
| 后端 | Railway | `backend` | `FRONTEND_URL`、`ENCRYPTION_SECRET`、各 API Key |
| 前端 | Vercel | `frontend` | `NEXT_PUBLIC_API_URL` = Railway 后端 URL |

本仓库已包含：

- **`backend/railway.json`**：Railway 使用 Nixpacks 构建，启动命令用 `$PORT`。
- **`backend/Procfile`**：与 railway.json 一致的启动命令，兼容其他支持 Procfile 的 PaaS。
