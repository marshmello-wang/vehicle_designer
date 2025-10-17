# 技术现状 Technical State

---

## 1. 技术栈概览 Tech Stack

### 1.1 运行环境
- **前端**: 无（当前为本地 CLI 演示，不含前端）
- **后端**: Python 3.12（本地虚拟环境 `.venv`）
- **数据库**: 无（本地文件系统输出）
- **部署**: 本地脚本（CLI）调用 Ark v3 API（`https://ark.cn-beijing.volces.com/api/v3`）
- **监控**: 无（本地演示阶段）

### 1.2 关键依赖
| 依赖项 | 版本 | 用途 | 升级阻碍 |
|--------|------|------|----------|
| volcengine-python-sdk[ark] | - | 访问火山方舟 Ark SDK（图像生成） | ✅无 |
| requests | - | 下载生成结果（URL） | ✅无 |
| toml | - | 读取 `config.toml` | ✅无 |

---

## 2. 系统架构 Architecture

### 2.1 分层结构
| 层级 | 层名 | 核心职责 | 对外接口 | 依赖下层 |
|------|------|----------|----------|----------|
| L4 | Workflow CLI（工作流入口） | 接收接口名与参数；模板/自定义 Prompt 选择；转发到编排器 | CLI（`python -m src.workflow.cli`） | L3 |
| L3 | Runner（编排器） | 展开 Prompt；应用默认值；构造 Ark CLI 参数；控制并发与 `seed` 策略 | Python 函数 | L2 |
| L2 | Ark Image CLI | 与 Ark SDK 对接；图片编码为 data URL；落盘图片与 `metadata.json` | CLI（`python -m src.ark_image_cli`）/ 函数 | L1 |
| L1 | Config | 加载 `config.toml`（`base_url/api_key/timeout/output_dir` 等） | Python 函数 | - |

### 2.2 架构约束
- **响应时间**: 由 Ark 服务端耗时主导；单次 4K 生成耗时视负载与网络而定（本地不做 SLA 承诺）
- **并发**: 本地建议并发上限 ≤4；串行通过 `--count N`；并发通过线程池发起 N 次 `--count 1`
- **可用性**: 本地演示，不设可用性目标；失败时保留错误信息与元数据
- **安全**: 使用企业 API Key 调用 Ark；输入图片仅本地读取；输出落盘到 `outputs/`；不新增外发数据环节

---

## 3. 核心数据模型 Data Models

### 3.1 实体定义

#### `Request`
**业务含义**: 一次 Ark 生成请求（可能包含多次客户端重复调用以获得多张候选）

**核心属性**:
| 属性名 | 类型 | 必填 | 说明 | 约束 |
|--------|------|------|------|------|
| model | str | 是 | `doubao-seedream-4-0-250828` | 固定默认，可覆盖 |
| prompt | str | 是 | 最终提示词文本（模板展开或自定义） | - |
| image | str/list | 否 | data URL 或列表（由本地路径编码） | 最多3张 |
| size | str | 否 | 生成分辨率 | 默认 `4K` |
| seed | int | 否 | 随机种子 | `FusionRandomize` 缺省多样化 |
| guidance_scale | float | 否 | 控制项 | 文档存在字段 |
| sequential_image_generation | str | 否 | 顺序多图生成开关 | 默认 `disabled` |
| response_format | str | 否 | 返回格式 | 默认 `url` |
| watermark | bool | 否 | 水印开关 | 默认 `false` |
| count | int | 否 | 客户端层重复调用次数 | 串行模式使用 |

**生命周期**: 由工作流发起 → Ark CLI 执行 → 图片与 `metadata.json` 落盘 → 结束

#### `OutputImage`
**业务含义**: 一张生成的图片或其 URL 记录

**核心属性**:
| 属性名 | 类型 | 必填 | 说明 | 约束 |
|--------|------|------|------|------|
| file | str | 否 | 本地文件路径 | 下载失败时为空 |
| url | str | 否 | 图片 URL | 下载失败时记录 `download_error` |
| size | str | 否 | 生成尺寸 | - |

#### `Metadata`
**业务含义**: 一次执行的完整快照（不含明文 base64）

**核心属性**:
| 属性名 | 类型 | 必填 | 说明 | 约束 |
|--------|------|------|------|------|
| run_id | str | 是 | 本次运行标识 | - |
| timestamp | str | 是 | UTC 时间戳 | - |
| model | str | 是 | 模型标识 | - |
| input | obj | 是 | 输入摘要（prompt、本地文件名等） | 不含明文 base64 |
| request_payload_preview | obj | 是 | 请求字段预览 | `image` 字段以占位符表示 |
| responses | list | 是 | 原始响应体序列化 | - |
| outputs | list | 是 | 输出文件/URL 列表 | - |

### 3.2 实体关系

#### `Request` 与 `OutputImage`
- **关系类型**: 1:N（一次请求可对应多张输出）
- **关系描述**: `Request` 通过客户端重复/并发调用获取多张 `OutputImage`
- **约束**: 串行模式为单一 `metadata.json`；并发模式每次调用生成独立 `metadata.json`

#### `Request` 与 `Metadata`
- **关系类型**: 1:1（串行模式）或 1:N（并发模式）
- **关系描述**: 每次 CLI 调用对应一份元数据快照

### 3.3 存储方案（后端 API）

#### 3.3.1 Supabase（Postgres）表结构
用于保存 Project/Version 与版本图片（MVP：直接存 base64）。

建议 DDL（可在 Supabase SQL 编辑器执行，见 `docs/project/schema.sql`）：
```sql
-- project
create table if not exists public.project (
  id uuid primary key default gen_random_uuid(),
  name text null,
  created_at timestamptz not null default now()
);

-- version
create table if not exists public.version (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.project(id) on delete cascade,
  parent_version_id uuid null references public.version(id) on delete set null,
  index int not null,
  interface_name text not null,
  image_mime text not null,
  image_base64 text not null,
  created_at timestamptz not null default now(),
  constraint version_index_unique unique (project_id, index)
);

create index if not exists idx_version_project_index on public.version(project_id, index asc);
```

实现与约束：
- 代码中在应用层计算 `index=latest(project)+1` 并写入（`app/db.py:version_insert`）。
- `parent_version_id` 形成版本链；回退时复制目标版本内容创建新行并指向其为父。
- `image_base64`、`image_mime` 按原样存储；后续可迁移到 Supabase Storage 并仅存 URL。

环境变量：
- `SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY` 必填（服务端直连 Postgres）。
- 测试环境内置内存假实现（`tests/conftest.py` 自动注入），无需真实连接。

数据流：
- 生成候选阶段不入库，仅返回 base64 列表给前端。
- “提交为版本”阶段将所选 base64 与元字段写入 `version` 表。

#### 3.3.2 CLI 元数据与输出（可选）
工作流/CLI 路径会在本地 `outputs/` 写入元数据与图片（若启用）。

示例 meta 片段：
```json
{
  "model": "doubao-seedream-4-0-250828",
  "input": {"prompt": "...", "images": ["examples/草稿.jpg"]},
  "request_payload_preview": {"size": "4K", "watermark": false, "image": "<data_url>"},
  "outputs": [{"file": "outputs/<run_id>_1_1.png", "size": "4K"}]
}
```

---

## 4. 模块清单 Module Inventory

### 4.1 前端模块
无

### 4.2 后端模块

#### `src/workflow/cli.py`
- **状态**: ✅已完成
- **功能**: 工作流统一入口，解析接口/模板/自定义/并发与 Ark 透传，调用 Runner
- **文件**: `src/workflow/cli.py`
- **核心函数**:
  - `main(argv) -> int` - 解析参数并调用 `run_interface`
- **依赖模块**: `src/workflow/runner.py`
- **被依赖**: 外部命令行

#### `src/workflow/runner.py`
- **状态**: ✅已完成
- **功能**: 展开 Prompt、设置默认值（`size=4K`、`sequential_image_generation=disabled`、`response_format=url`、`watermark=false`）、构造参数与并发执行
- **文件**: `src/workflow/runner.py`
- **核心函数**:
  - `run_interface(...) -> int` - 编排并调用 `src.ark_image_cli.main`
- **依赖模块**: `src/workflow/interfaces.py`、`src/workflow/templates.py`、`src/ark_image_cli.py`
- **被依赖**: `src/workflow/cli.py`

#### `src/workflow/interfaces.py`
- **状态**: ✅已完成
- **功能**: 接口规格与校验，包含图片输入规则与 `seed_policy`
- **文件**: `src/workflow/interfaces.py`
- **核心类/函数**:
  - `InterfaceSpec` - 规格定义
  - `normalize_images(...) -> List[str]` - 图片输入规范化

#### `src/workflow/templates.py`
- **状态**: ✅已完成
- **功能**: 模板注册表（仅占位符，不含文案），校验必填占位符
- **文件**: `src/workflow/templates.py`
- **核心结构**:
  - `REGISTRY: Dict[str, TemplateSpec]`

#### `src/ark_image_cli.py`
- **状态**: ✅已完成（沿用 S10-P0-1）
- **功能**: Ark SDK 调用；图片编码；保存图片与元数据
- **文件**: `src/ark_image_cli.py`
- **核心函数**:
  - `main(argv: List[str]) -> int`

#### `src/config.py`
- **状态**: ✅已完成
- **功能**: 读取 `config.toml`；提供 `base_url/api_key/timeout/output_dir/default_model`
- **文件**: `src/config.py`

---

### 5. 核心接口

**src.workflow.runner.run_interface(interface_name, prompt_mode, template_key, template_params, custom_prompt, model, primary_image, ref_images, num_candidates=4, concurrency=False, max_workers=4, ark_kwargs=None) -> int**
- **用途**: 将四类工作流接口映射为 Ark CLI 调用；支持串行/并发与默认参数
- **输入**: 接口名、Prompt 模式/参数、模型、图片、本地数量与并发、Ark 参数透传
- **返回**: 进程退出码（0 成功，非 0 失败）
- **实现**: `src/workflow/runner.py`
- **调用方**: `src/workflow/cli.py`
- **注意事项**: 并发模式会产生多份 `metadata.json`；默认 `FusionRandomize` 采用 varying seeds

**src.ark_image_cli.main(argv: List[str]) -> int**
- **用途**: 直接调用 Ark SDK 生成图片并落盘
- **输入**: CLI 参数（模型、prompt、images、size/seed/...）
- **返回**: 进程退出码（0 成功）
- **实现**: `src/ark_image_cli.py`
- **调用方**: 工作流 Runner 或直接命令行
- **注意事项**: 仅透传文档存在字段；元数据不包含明文 base64

**src.workflow.cli.main(argv: List[str] | None) -> int**
- **用途**: 工作流命令入口；收集参数并调用 Runner
- **输入**: 命令行参数（接口、模板/自定义、图片、数量、并发、Ark 透传）
- **返回**: 进程退出码
- **实现**: `src/workflow/cli.py`
- **调用方**: 命令行

---

### 6. 性能与成本限制
- **分辨率开销**: 默认 `size=4K` 带来更高延时与带宽占用；必要时可降级为 `2K/1K`
- **并发限制**: 本地并发建议 ≤4；超出可能导致超时或限流；串行 `--count N` 可提供等价多图
- **下载成本**: `response_format=url` 时进行图片下载；失败将保留 URL 与错误信息
- **网络依赖**: 受外部 Ark 服务稳定性与网络状况影响；应对策略为超时、重试与失败回报
- **种子策略**: `FusionRandomize` 默认 varying seeds 增加多样性，其它接口固定 seed 提升复现性

---

## 7. 后端 API（FastAPI）

基础信息
- 服务入口：`app/main.py`（FastAPI）。
- 路由模块：`app/routes/projects.py`、`app/routes/generate.py`、`app/routes/versions.py`。
- Schema：`app/schemas.py`。
- Ark 接入：`app/ark.py`（`ARK_FAKE_MODE` 控制真假实现）。

环境变量
- `ARK_API_KEY`（必需以启用真实 Ark）、`ARK_BASE_URL`（可选，默认北京三）、`ARK_FAKE_MODE`（默认 true）。
- `SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`（版本存储，测试环境已内置内存假实现）。

项目管理
- POST `/api/projects/create`
  - Body: `{ "name"?: string }`
  - 200: `ProjectOut { project_id, name, created_at, version_count=0 }`
- GET `/api/projects`
  - 200: `ProjectOut[]`（包含 `version_count` 实时统计）
- GET `/api/projects/{project_id}`
  - 200: `ProjectOut`
  - 404: 项目不存在

生成候选（不入库）
- 通用请求体（四类共享）`GenerateCommon`
  - `prompt_mode: "template"|"custom"`
  - 当 `template`：`template_key: string`, `template_params: object`
  - 当 `custom`：`custom_prompt: string`
  - `primary_image?: { base64: string, mime?: "image/png"|"image/jpeg" }`
  - `ref_images?: Array<{ base64: string, mime?: string }>`（0–2）
  - `num_candidates?: number`（默认 4）
  - `ark?: { size?, seed?, guidance_scale?, sequential_image_generation?, response_format?, watermark?, model?, param?, json_params? }`
- 响应体 `CandidatesOut`
  - `candidates: Array<{ base64: string, mime: string }>`
  - `metadata: object`（包含接口名/模板信息/ark 透传等）
- 端点
  - POST `/api/projects/{project_id}/generate/text-to-image`
    - 仅文本，`primary_image/ref_images` 不使用
  - POST `/api/projects/{project_id}/generate/sketch-to-3d`
    - 需要 `primary_image`
  - POST `/api/projects/{project_id}/generate/fusion-randomize`
    - 需要 `primary_image`，`ref_images` 0–2；未指定 `seed` 时每张候选使用不同 `seed`
  - POST `/api/projects/{project_id}/generate/refine-edit`
    - 需要 `primary_image`，`ref_images` 可选
- 错误
  - 422：模板/自定义提示词缺失、图片必填缺失、图片数量超限等
  - 500：真实 Ark 请求失败（当 `ARK_FAKE_MODE=false`）

版本管理（入库）
- POST `/api/projects/{project_id}/versions/create`
  - Body: `SubmitVersionIn { image: {base64,mime}, interface_name, base_version_id?, ... }`
  - 200: `SubmitVersionOut { project_id, version:{id,index}, image, interface_name }`
  - 404: 项目/基线版本不存在
- GET `/api/projects/{project_id}/versions`
  - 200: `VersionOutBrief[] { id,index,parent_version_id,interface_name,created_at }`
- GET `/api/projects/{project_id}/versions/{version_id}`
  - 200: `VersionDetailOut { id,index,parent_version_id,interface_name,image }`
  - 404: 版本不存在或不属于该项目
- POST `/api/projects/{project_id}/versions/{version_id}/revert`
  - 200: `SubmitVersionOut`（复制目标版本内容形成新版本，`index` 递增）
  - 404: 项目/版本不存在

实现要点
- generate/* 仅返回候选，不入库；提交版本由 `/versions/create` 完成。
- Ark 字段名与语义保持一致，统一置于 `ark` 对象透传；服务端默认值：`size=4K`、`sequential_image_generation=disabled`、`response_format=url`、`watermark=false`。
- `FusionRandomize` 默认使用 varying seeds（未显式传 seed 时）。
