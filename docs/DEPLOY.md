# 云端部署 — 单服务 Railway（推荐）

一个 Railway 服务跑前端+后端，**无需 Docker，无需 Vercel，无需配 CORS**。
和本地 `npm run dev` 一样简单。

```
浏览器 → Railway (一个服务)
           ├── Next.js  (对外 $PORT，代理 /api/*)
           └── uvicorn  (内部 127.0.0.1:8000)
```

---

## 1. 创建并部署

1. 打开 [railway.app](https://railway.app)，用 GitHub 登录。
2. **New Project** → **Deploy from GitHub repo** → 选择本仓库 `claude_science`。
3. **Settings** → **Root Directory** 留空（使用仓库根目录）。
4. **Settings** → **Networking** → **Generate Domain**。

Railway 会自动用 `nixpacks.toml` 构建（安装 Python + Node），用 `start.sh` 启动。

## 2. 环境变量

**Variables** → 添加：

| 变量 | 必填 | 说明 |
|------|------|------|
| `ENCRYPTION_SECRET` | 建议 | 加密 API Key 的密钥（`openssl rand -hex 32`） |
| `ANTHROPIC_API_KEY` | 按需 | 用 Claude 时填 |
| `OPENAI_API_KEY` | 按需 | 用 OpenAI 时填 |
| `DEEPSEEK_API_KEY` | 按需 | 用 DeepSeek 时填 |
| `GITHUB_TOKEN` | 可选 | GitHub 导出功能 |

不需要 `FRONTEND_URL`、`CORS_ORIGINS`、`BACKEND_URL` — 前后端同源，自动搞定。

默认 SQLite（重启丢数据）。需持久化可添加 Railway PostgreSQL 插件并设 `DATABASE_URL`。

## 3. 验证

浏览器打开 `https://<你的域名>/api/health`，看到 JSON 即后端正常。
打开 `https://<你的域名>/` 即可使用完整应用。

## 4. 原理

| 文件 | 作用 |
|------|------|
| `nixpacks.toml` | 告诉 Railway 装 Python 3.13 + Node 22，安装依赖，构建前端 |
| `start.sh` | 启动 uvicorn (内部 8000) + next start (对外 $PORT) |
| `railway.json` | Railway 部署配置 |
| `frontend/next.config.ts` | rewrites 把 `/api/*` 代理到 `localhost:8000` |

---

## 本地开发

```bash
cd local && npm run dev
```

和云端架构一模一样：Next.js 代理 API 请求到后端。
