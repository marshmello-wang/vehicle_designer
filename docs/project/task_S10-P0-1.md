# Task任务模版

**对应task ID**: [S10-P0-1]

## 背景信息
本任务旨在打通方舟/豆包图像生成能力在本地脚本的最小接入，支持：
- 接入模型：Seedream 4.0（`doubao-seedream-4-0-250828`）与 Seededit 3.0 I2I（`doubao-seededit-3-0-i2i-250628`）。
- 使用 Ark Python SDK（`volcenginesdkarkruntime`）直连 Ark v3 接口（`https://ark.cn-beijing.volces.com/api/v3`）。
- 在本地以 CLI 方式提供“文本+多参考图”生图与“单源图编辑”能力，并保留完整元数据。

该能力用于 Sprint 的 E2E 演示链路：上传线稿/参考 → prompt → 生成候选图，用于验证上下文工程与参数控制可复现性。输入图片以本地文件为主，读取后按文档要求编码为 base64，并以 data URL 形式传入（例如：`data:image/png;base64,<base64_image>`）。

## 任务目标
- 提供一个本地可运行的 Python CLI 脚本，支持在两种模型之间切换；
- 支持输入文本 prompt、最多3张参考图（本地文件→base64→以 data URL 形式提交）；
- 支持 Ark SDK 文档中已定义的全部参数透传（不杜撰参数名）；
- 每次调用保存生成图片（或其URL）与一次请求的完整元数据（JSON）到本地；
- 支持通过 `config.toml` 配置 base_url、API Key 等。

## 技术路线前置讨论
- 接入方式：采用 Ark Python SDK（`volcenginesdkarkruntime`），按你提供的示例调用 `client.images.generate`；
- 模型标识以你提供的具体版本为准：
  - Seedream 4.0：`doubao-seedream-4-0-250828`
  - Seededit 3.0 I2I：`doubao-seededit-3-0-i2i-250628`
- 图片输入（本地→base64→data URL）：
  - 统一使用 data URL 形式：`image=["data:image/<mime>;base64,<base64_image>", ...]`，其中 `<mime>` 依据文件类型（png/jpeg 等）。
  - Seedream 4.0：明确支持多图融合，最多3张；以 data URL 列表提交（`image=[...]`）。
  - Seededit 3.0 I2I：以第1张为源图（必需），其余忽略（并在日志中提示）。
- 多图权重：仅在 API 原生支持时启用。CLI 允许 `path[:weight]` 语法；若 API 不支持，忽略权重但不报错（并在元数据中记录）。
- 生成数量：默认 `count=1`；若 API 不提供相应字段，可通过客户端参数 `--count` 重复调用得到多张图（避免伪造 API 参数）。

## 核心验收标准
- 功能
  - CLI 支持 `--model {doubao-seedream-4-0-250828, doubao-seededit-3-0-i2i-250628}` 切换；
- 支持 `--prompt` 与最多3个 `--images`（本地文件路径，内部读取→base64→拼接为 data URL 列表提交）。Seededit 模式下仅使用第1张作为源图；
  - 支持 Ark 文档中存在的参数名（如 `size`、`seed`、`guidance_scale`、`sequential_image_generation`、`response_format`、`watermark` 等），并通过 `--param k=v` 与 `--json-params` 透传；
  - 支持 `--count` 客户端层重复调用获取多张结果。
- 稳定性
  - 对超时/HTTP错误提供明确信息与可配置的超时；
  - 不使用未在文档中的参数名；
  - 元数据 JSON 完整记录请求参数（含本地文件名）、模型、响应体与输出文件名（不记录明文 base64）。
- 产出
  - 代码位于 `src/ark_image_cli.py` 与 `src/config.py`；
  - 提供 `config.toml.example`（含 `base_url` 与 `api_key` 字段）；
  - `examples/commands.txt` 提供至少3条复现实验命令；
  - 生成内容与元数据写入 `outputs/` 目录。

## 执行步骤（step by step）
- [Human] 提供本地图片文件与典型 prompt（如线稿与风格参考）；
- [AI] 设计CLI参数与透传策略，起草代码骨架；
- [AI] 接入 Ark SDK，分别实现 Seedream（多图融合）与 Seededit（单图编辑）分支；
- [AI] 实现`--count` 客户端多次调用、下载/保存生成结果与元数据输出；
- [AI] 编写示例与最小复现实验命令；
- [Human] 在本地填写 `config.toml`，运行示例并确认接口字段与文档一致；
- [AI] 根据实际返回字段名调整/固化参数映射（如需）。

## 依赖/风险
- 依赖：Ark SDK 安装与 API Key 权限；
- 风险：
  - base64 的字段名与封装格式以文档为准；需在实现时严格对齐，避免自定义；
  - 多图权重取值的真实字段需以文档为准，未明确前仅在元数据中记录而不传给API；
  - `response_format` 以文档示例的 `url` 为主，其他取值在文档确认后再开放。

## 复现说明
1) 安装依赖：`pip install 'volcengine-python-sdk[ark]' requests toml`
2) 复制 `config.toml.example` 为 `config.toml` 并填写 `api_key`
3) 运行示例命令（见 `examples/commands.txt`）
4) 生成图片/URL与 `metadata.json` 将写入 `outputs/` 目录

## 验收结论（已完成）
- 状态：完成（本地脚本可运行、参数透传、元数据保存均验证通过）
- 环境：Python 3.12（本地 `.venv`），Ark SDK 按文档安装
- 输入方式：本地文件读取后转 base64，并以 data URL（`data:image/<mime>;base64,<...>`）提交；Seedream 4.0 支持多图（≤3），Seededit 3.0 i2i 使用第1张为源图
- 多图权重：支持以 `path[:weight]` 形式输入并记录到 `metadata.json`，但不传入 API（文档未定义权重字段）
- 生成结果与元数据位置：`outputs/` 目录，例如 `outputs/20251017T013736Z_56896_metadata.json` 和对应图片文件
- 复现命令：见 `examples/commands.txt`

备注：如后续文档新增字段（如权重、非 URL 返回格式等），可在 CLI 中经 `--param/--json-params` 透传，或再行补充显式参数。
