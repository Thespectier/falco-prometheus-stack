# 开发指南 (Development Guide)

本文档记录了如何在开发环境中启动 Falco Prometheus Stack 的后端与前端服务。

## 1. 环境准备

### 1.1 Python 环境 (后端)
- 要求 Python >= 3.14
- 使用 `uv` 进行依赖管理

```bash
# 在项目根目录执行
uv sync
```

### 1.2 Node.js 环境 (前端)
- 要求 Node.js >= 20
- 由于系统环境限制，我们使用项目本地的 `nvm` 环境

```bash
# 进入 web 目录
cd web

# 激活本地 Node 环境 (重要: 每次新开终端都需要执行)
export PATH="$PWD/.nvm_local/versions/node/v20.19.6/bin:$PATH"

# 验证环境
node -v  # 应输出 v20.x.x
```

## 2. 启动服务

### 2.1 启动后端 API
后端服务基于 FastAPI，运行在 8000 端口。

```bash
# 在项目根目录执行
uv run uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **API 地址**: http://localhost:8000
- **Swagger 文档**: http://localhost:8000/docs

### 2.2 启动前端 Web
前端服务基于 Vite + React，运行在 8173 端口 (已配置 Proxy 转发 API 请求)。

```bash
# 在 web 目录执行 (确保已激活 Node 环境)
npm run dev -- --host 0.0.0.0 --port 8173
```
- **Web 地址**: http://<服务器IP>:8173 (例如 http://222.20.126.133:8173)

## 3. 常见问题

### Q: 前端报错 `segmentation fault`?
A: 这是由于系统默认 Node 版本过低导致的。请务必执行 `export PATH="$PWD/.nvm_local/versions/node/v20.19.6/bin:$PATH"` 来激活本地的高版本 Node 环境。

### Q: 页面无法访问?
A: 
1. 检查防火墙是否放行 8173 端口。
2. 确保启动命令中包含了 `--host 0.0.0.0`，否则只能通过 localhost 访问。
