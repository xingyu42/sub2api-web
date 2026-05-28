# sub2api 用量查看 Web

用 sub2api 的管理员 API Key 远程查看自建实例的「上游账号用量」和「API Key 用量」。

- 后端：FastAPI + httpx（async）
- 模板：Jinja2 + Tailwind CDN + Chart.js CDN
- 鉴权：单密码登录 + 签名 cookie（admin key 仅在服务器进程内，绝不进浏览器）
- 数据：纯只读调用 sub2api 的 `/api/v1/admin/*`

## 功能

- **仪表盘**：总用户/总 Key/总账号、今日 token & 费用、累计 token & 费用、RPM/TPM、7 日趋势、模型分布
- **上游账号**：列表（支持平台/状态/关键字筛选）+ 今日请求 / token / 费用；详情页含 30 日折线图
- **API Keys**：跨用户聚合 Key 列表，按累计费用降序

不做写操作（不创建/删除账号、不改余额、不重置 quota），降低 admin key 泄漏风险面。

## 准备

需要一个 sub2api 实例和一个 admin API Key：

1. 登录 sub2api 管理后台
2. 系统设置 → 生成 Admin API Key
3. 复制到本项目的 `.env`

## 本地运行

```bash
cp .env.example .env
# 编辑 .env 填入：
#   SUB2API_BASE_URL   你的 sub2api 实例（不含尾部 /）
#   SUB2API_ADMIN_KEY  上一步生成的 admin key
#   LOGIN_PASSWORD     你设定的 Web 登录密码
#   SESSION_SECRET     openssl rand -hex 32

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

打开 http://localhost:8000 → 输入 `LOGIN_PASSWORD` 登录。

## Docker 部署

```bash
cp .env.example .env  # 同上编辑
docker compose up -d --build
docker compose logs -f sub2api-web
```

容器监听 `8000`，建议前面挂 Caddy / Nginx 做 TLS（HTTPS 后将 `app/security.py` 的 cookie `secure=True`）。

## 配置项

| 变量 | 说明 | 必填 |
|---|---|---|
| `SUB2API_BASE_URL` | sub2api 实例地址（不含尾部 `/`） | ✓ |
| `SUB2API_ADMIN_KEY` | sub2api 管理员 API Key | ✓ |
| `LOGIN_PASSWORD` | 本 Web 的访问密码 | ✓ |
| `SESSION_SECRET` | 签名 cookie 密钥（`openssl rand -hex 32`） | ✓ |
| `SUB2API_VERIFY_SSL` | 自建实例用自签证书时设 `false` | 否 |
| `REQUEST_TIMEOUT` | 上游请求超时（秒，默认 30） | 否 |

## 排错

- 401 / 403 → admin key 错误或权限不足，检查 `SUB2API_ADMIN_KEY`
- 网络/连接错误 → 检查 `SUB2API_BASE_URL` 能否从本机/容器访问
- 5xx → sub2api 服务自身异常，看其日志
- 仪表盘图表为空 → 实例近期没有用量数据
