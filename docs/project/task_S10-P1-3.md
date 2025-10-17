# Task任务模版

**对应task ID**: [S10-P1-3]

## 背景信息
本任务交付“最小演示链路（仅后端 API）”，为前端提供 Project/Version 与四类编辑接口的统一后端服务：
- 框架：Python + FastAPI（本地可运行，支持部署到 Zeabur）。
- 数据存储：Supabase（Postgres）。本期简化为将生成图片以 base64 字符串存在数据库表（MVP）；后续可迁移到 Storage。
- Project 概念：每个 Project 负责管理一条图片版本链；创建 Project 后，用户可通过“文本生图”或“直接提交一张图片”为首版（v1）。
- 版本管理：每次编辑都会产生新版本，支持列出与回退；前端负责候选图选择与回退操作触发。
- 鉴权：本任务不包含鉴权；未来 TODO 为 Bearer 鉴权（见 task_map 的 Planned）。

## 任务目标
- 提供 Project/Version 基础 CRUD：创建空项目、查询项目/版本列表、获取单版本详情、回退。
- 实现四类编辑接口定义（与 S10-P0-2 对齐）：TextToImage、SketchTo3D、FusionRandomize、RefineEdit。
- 生成候选阶段：直接返回 N 张 base64 图片给前端（不入库）。
- 提交版本阶段：前端选择一张候选图后，调用“提交为版本”接口，将该图写入数据库并形成新版本（返回版本号）。
- Ark 参数与字段：严格使用文档存在的字段名与语义；统一以 `ark` 对象透传，不更名不改义。

## 技术路线前置讨论
- 框架与运行：FastAPI + Uvicorn；本地运行与 Zeabur 部署以相同入口；通过环境变量注入配置。
- Supabase 访问：使用服务端 Service Role Key 直连 Postgres（SQL/REST 任一均可，MVP 选 SQL 直连驱动/官方 Python 客户端）。
– Schema 策略：映射 Project/Version 关系；将图片以 base64 文本存在 `version.image_base64`，并保留 `image_mime`。为保持最小字段集合，本期不在数据库保存 Ark/seed/模板等生成参数（仅在响应中返回给前端）。
- 四类接口与输入规则：遵循 S10-P0-2；`FusionRandomize` 默认 varying seeds；`SketchTo3D`/`RefineEdit`/`FusionRandomize` 需 `primary_image`；`TextToImage` 仅文本。
- 候选与提交解耦：四类“generate/*”端点只产出候选（不入库）；由 `POST /versions` 完成“提交为版本”。
- 返回格式：生成与读取默认返回 base64 字符串；可选 `?format=url` 留作后续扩展（迁移至 Storage 后启用）。
- 不改变 Ark 字段命名与语义：`ark` 中的 `size|seed|guidance_scale|sequential_image_generation|response_format|watermark|...` 原样透传。

## 核心验收标准
- 功能与接口
  - `POST /api/projects/create` 仅创建空项目（无版本），返回 `version_count=0`。
  - 四类生成接口可返回 `num_candidates`（默认4）张 base64 图片；不入库。
  - `POST /api/projects/{project_id}/versions/create` 可将任意 base64 图提交为新版本（可作为首版或基于 `base_version_id` 创建下一版）。
  - 列表与详情接口可读取版本链，`index` 自1递增，含 `parent_version_id`。
  - `POST /api/projects/{project_id}/versions/{version_id}/revert` 创建一个新版本，其内容复制自目标历史版本。
- Ark 参数
  - 仅使用文档存在字段；`ark` 对象字段名与含义不变；`seed` 可同步记录在单独列。
- 数据一致性与可复现
  - 同一输入（含 `seed`、模板/自定义、图片与参数）在相同模型版本下结果可复现（平台随机性允许轻微波动）。
- 最小运行闭环
  - 本地通过 `uvicorn` 可启动并完成端到端：创建项目→生成候选→提交版本→查看/回退。

## 接口契约（I/O 与处理规则）

通用说明
- 本期无鉴权；未来增加 Bearer。
- 图片输入一律以 base64 传入；`mime` 支持 `image/png` / `image/jpeg`。
- 四类接口命名对齐 S10-P0-2：`TextToImage`、`SketchTo3D`、`FusionRandomize`、`RefineEdit`。
- Ark 参数统一置于 `ark` 对象中（字段名与语义保持与 Ark 文档一致）。

1) 创建/查询项目
- POST `/api/projects/create`
  - Body: `{ "name"?: string }`
  - 200: `{ "project_id": string, "name": string|null, "created_at": string, "version_count": 0 }`
- GET `/api/projects`
  - 200: `[{ "project_id": string, "name": string|null, "created_at": string, "version_count": number }]`
- GET `/api/projects/{project_id}`
  - 200: `{ "project_id": string, "name": string|null, "created_at": string, "version_count": number }`

2) 生成候选（不入库）
- 通用请求体字段（四类接口共享）：
  - `prompt_mode: "template"|"custom"`
  - 当 `template`：`template_key: string`, `template_params: object`
  - 当 `custom`：`custom_prompt: string`
  - `primary_image?: { base64: string, mime?: "image/png"|"image/jpeg" }`
  - `ref_images?: Array<{ base64: string, mime?: string }>`（0–2）
  - `num_candidates?: number`（默认 4）
  - `ark: { size?, seed?, guidance_scale?, sequential_image_generation?, response_format?, watermark?, ... }`
- 端点：
  - POST `/api/projects/{project_id}/generate/text-to-image`（无需图片）
  - POST `/api/projects/{project_id}/generate/sketch-to-3d`（`primary_image` 必填）
  - POST `/api/projects/{project_id}/generate/fusion-randomize`（`primary_image` 必填，`ref_images` 0–2；默认 varying seeds）
  - POST `/api/projects/{project_id}/generate/refine-edit`（`primary_image` 必填，`ref_images` 0–2）
- 200 响应：
  - `{ "candidates": [{ "base64": string, "mime": string }...], "metadata": { "model": string, "ark": object, "seeds": number[]|number, "prompt_mode": string, "template_key"?: string, "template_params"?: object, "interface_name": string } }`

3) 提交为版本（入库）
- POST `/api/projects/{project_id}/versions/create`
  - Body：
    - `image: { base64: string, mime: "image/png"|"image/jpeg" }`
    - `interface_name: "TextToImage"|"SketchTo3D"|"FusionRandomize"|"RefineEdit"`
    - `base_version_id?: string`（如为空则为项目首版）
    - `prompt_mode: "template"|"custom"`
    - 当 `template`：`template_key: string`, `template_params: object`
    - 当 `custom`：`custom_prompt: string`
    - `ark: { ... }`（用于记录生成该图的 Ark 参数；字段名不改）
    - `seed?: number`
  - 200: `{ "project_id": string, "version": { "id": string, "index": number }, "image": { "base64": string, "mime": string }, "interface_name": string }`

4) 版本读取与回退
- GET `/api/projects/{project_id}/versions`
  - 200: `[{ "id": string, "index": number, "parent_version_id": string|null, "interface_name": string, "created_at": string }]`
- GET `/api/projects/{project_id}/versions/{version_id}`
  - 支持 `?format=base64`（默认 base64）
  - 200: `{ "id": string, "index": number, "parent_version_id": string|null, "interface_name": string, "image": { "base64": string, "mime": string } }`
- POST `/api/projects/{project_id}/versions/{version_id}/revert`
  - Body: `{}`
  - 200: `{ "version": { "id": string, "index": number }, "image": { "base64": string, "mime": string } }`

5) 初始化首版的两种路径
- 路径 A（文本生图）：
  - 创建项目 → `generate/text-to-image` 获取候选 → 前端选一张 → `POST /versions`（不填 `base_version_id`）。
- 路径 B（直接上传首图）：
  - 创建项目 → 直接 `POST /versions`（不填 `base_version_id`，`image.base64` 为客户端上传的首图）。

## 数据模型（Supabase / Postgres）

建议 DDL（在 Supabase SQL Editor 执行）：

```sql
-- 若尚未启用，启用 pgcrypto 以使用 gen_random_uuid()
create extension if not exists pgcrypto;

create table if not exists project (
  id uuid primary key default gen_random_uuid(),
  name text,
  created_at timestamptz not null default now()
);

create table if not exists version (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references project(id) on delete cascade,
  parent_version_id uuid references version(id) on delete set null,
  index int not null,
  interface_name text not null,
  image_mime text not null,
  image_base64 text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_version_project_id_index on version(project_id, index);
create index if not exists idx_version_created_at on version(created_at);
```

数据约束与约定
- `version.index`：项目内自 1 递增；由后端以事务确保唯一性与递增。
- `parent_version_id`：记录直接父版本，用于回退/可视化。
- `image_base64`：存储 base64 字符串（MVP 简化）。

## 环境变量与配置

必须配置（本地与 Zeabur 一致，通过环境变量注入，不写入代码库）：
- `SUPABASE_URL="https://xzozkhutcryayfskrtkm.supabase.co"`
- `SUPABASE_SERVICE_ROLE_KEY="<由你提供的 service_role_key>"`  // 切勿提交到仓库
- `ARK_BASE_URL`、`ARK_API_KEY`
- 可选：`PORT`（Zeabur 提供）、`LOG_LEVEL`

本地运行（占位说明，代码实现后可用）
- `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### 启用真实 Ark（可选）
- 安装依赖：`pip install 'volcengine-python-sdk[ark]'`
- 设置环境变量：
  - `export ARK_API_KEY='<你的 Ark API Key>'`
  - 可选：`export ARK_BASE_URL='https://ark.cn-beijing.volces.com/api/v3'`
  - 关闭假实现：`export ARK_FAKE_MODE=false`
- 调用方式：保持现有四类 `generate/*` 接口不变，服务端将通过 Ark SDK 真实生成图片并以 base64 返回。

## 执行步骤（step by step）
- [AI] 起草 FastAPI 项目骨架与配置读取（不含鉴权中间件）。
- [AI] 定义 Pydantic Schema 与四类生成端点，请求体验证与 Ark 参数透传。
- [AI] 实现“提交为版本/读取/回退/列表/创建项目”接口与事务性写入（自增 index）。
- [AI] 适配 `FusionRandomize` 的 varying seeds；其他接口默认固定/透传 seed。
- [AI] 编写 pytest 测试（FastAPI TestClient/httpx），覆盖项目/生成候选/提交版本/读取/回退及错误用例。
- [AI] 输出最小复现实例（cURL/HTTPie）与本地运行说明（不含任何密钥）。
- [Human] 提供/确认 Zeabur 环境变量与 Supabase 密钥注入；在 Supabase 执行 DDL。
- [Human] 本地/Zeabur 启动服务，联调前端候选选择与版本提交流程。

## 依赖/风险
- 依赖：Supabase Postgres 与 Service Role Key；Ark API Key 与 Base URL；Zeabur 环境变量注入。
- 风险：
  - base64 存数据库会增大体积与 IO（可接受于 MVP；后续迁移 Storage）。
  - 并发/超时/QPS 需根据 Ark 平台策略调优；
  - 模板文案仍由产品侧提供（`template_*` 仅占位）。
  - 本期无鉴权，演示环境需注意访问控制（后续接 Bearer）。

## 复现说明（待代码实现后生效）
1) 在 Supabase 执行上述 DDL；
2) 设置环境变量：`SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`、`ARK_BASE_URL`、`ARK_API_KEY`；
3) 启动服务：`uvicorn app.main:app --host 0.0.0.0 --port 8000`；
4) 流程：创建项目 → 调用 `generate/*` 获取候选（base64 列表）→ 前端选图 → `POST /versions` 提交为版本 → `GET /versions`/`GET /versions/{id}` 查看；
5) 回退：`POST /versions/{version_id}/revert` 创建新版本复制历史内容。

## 验收结论（待完成）
- 状态：进行中（API 契约与 Schema 已固化，等待实现）。
- 范围：后端 API 最小链路 + Supabase 表结构 + 本地/Zeabur 配置说明；不含鉴权。

## 测试计划与用例

测试目标
- 验证最小后端 API 闭环可用与契约稳定（请求校验、必填项、返回结构）。
- 保证四类生成候选接口的输入规则与 S10-P0-2 一致；提交为版本链路稳定；版本读取/回退正确。

测试方式
- 框架：pytest + FastAPI TestClient（或 httpx.AsyncClient）。
- 隔离：通过依赖注入或开关变量对 Ark 调用进行假实现（`ARK_FAKE_MODE=true`），返回固定 1x1 PNG base64；数据库可使用事务回滚或临时 schema，或以仓储层 mock 方式替换。
- 伪图片：使用 1x1 PNG base64 示例：
  - `iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axuE9sAAAAASUVORK5CYII=`（`image/png`）

覆盖清单（按端点）
- 项目管理
  - POST /api/projects/create：返回 200，`version_count=0`，`project_id` 为有效 UUID。
  - GET /api/projects：包含新建项目；字段齐全。
  - GET /api/projects/{project_id}：返回单项详情；不存在时 404。
- 生成候选（不入库）
  - text-to-image：`prompt_mode=custom` 且 `custom_prompt` 提供，返回 `candidates` 数量=默认4，`mime=image/png`；缺少 `custom_prompt` 返回 422。
  - sketch-to-3d：缺少 `primary_image` 返回 422；提供最小 base64 时返回 200。
  - fusion-randomize：`primary_image` 必填；`ref_images` 可 0–2；默认 seeds 数量=候选数。
  - refine-edit：`primary_image` 必填；`ref_images` 可选。
- 提交为版本（入库）
  - 首版：POST /api/projects/{id}/versions/create（仅 `image` 与 `interface_name`），返回 `index=1`。
  - 续版：指定 `base_version_id`，返回 `index=2` 且 `parent_version_id` 指向上一版。
- 版本读取与回退
  - 列表：GET /api/projects/{id}/versions：返回按 `index` 递增的数组。
  - 详情：GET /api/projects/{id}/versions/{vid}`：返回 base64 与 mime。
  - 回退：POST /api/projects/{id}/versions/{vid}/revert：新建版本，`index` 递增，图片内容与目标版本一致。
- 错误用例
  - 非法 UUID → 422（路径参数校验）或 404（资源不存在）。
  - 非法 base64 / 不支持的 mime → 422。
  - `template` 模式缺少 `template_params` 或 `template_key` → 422。
  - 需要 `primary_image` 的端点缺失主图 → 422。

建议目录与命名（占位）
- `tests/test_projects.py`：创建/列表/详情。
- `tests/test_generate.py`：四类候选生成（含负例）。
- `tests/test_versions.py`：提交版本/列表/详情/回退。

运行方式（占位）
- `pytest -q`
