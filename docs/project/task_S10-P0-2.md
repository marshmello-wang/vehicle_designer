# Task任务模版

**对应task ID**: [S10-P0-2]

## 背景信息
本任务聚焦“Agent Workflow”能力落地：在统一模型（Seedream 4.0，`doubao-seedream-4-0-250828`）下，定义与实现四类核心接口，提供模板驱动与自定义两种提示词模式，并一次性产出4–6张候选图（并行/批量）。输入图片以本地路径传入，由现有 CLI 负责本地文件→base64→data URL 的编码。Ark 参数透传规范与输出/元数据写入规范沿用 S10-P0-1，不新增元数据字段。

接口清单（对齐项目主场景，命名与范围已确认）：
- 0 TextToImage：完全基于文本生成图片。
- 1 SketchTo3D：线稿→高保真3D概念图（主图必填）。
- 2 FusionRandomize：主参考+若干辅助参考，随机融合生成多候选（可无prompt）。
- 3 RefineEdit：主参考+若干辅助参考，结合prompt做编辑微调。

## 任务目标
- 定义上述4个接口的输入/输出契约与运行参数（含并发数量、种子策略）。
- 提供 Prompt 模板占位（Python 字符串常量，仅含占位符，不编写具体文案）；同时支持自定义 Prompt 直通模式。
- 基于现有 `src/ark_image_cli.py` 完成批量/并发产出：每接口单次执行产出 `num_candidates`（目标1–6）张候选，并保存输出与元数据（沿用 S10-P0-1 结构）。
- 提供最小复现实例命令与运行说明，便于本地验证与演示。

## 技术路线前置讨论
- 模型/SDK：统一使用 Seedream 4.0（`doubao-seedream-4-0-250828`），Ark Python SDK 接入方式沿用 S10-P0-1。
- 图片输入：工作流层接收本地路径列表，传递给 CLI 的 `--images`；CLI 内部完成 base64+data URL 编码。暂不启用权重字段（仅在元数据中记录由 S10-P0-1 决定的内容，本任务不新增字段）。
- 参数透传：保留并仅限 Ark 文档中已存在字段（如 `size`、`seed`、`guidance_scale`、`sequential_image_generation`、`response_format`、`watermark` 等）；额外通过 `--param/--json-params` 透传时同样遵循“仅传文档字段”的约束。默认值：`size=4K`、`sequential_image_generation=disabled`、`response_format=url`、`watermark=false`。
- 模板形态：以 Python 字符串模板占位（如 `{brand}`, `{style_adjectives}`, `{colorway}`, `{lighting}`, `{era}`, `{notes}`, `{negative}` 等），仅定义键名与占位符签名；实际文案由产品侧稍后提供。本任务不自行补充文案内容。
- 自定义直通：`prompt_mode=custom` 时忽略模板，直接使用自定义 Prompt。
- 并行/数量：`num_candidates` 由参数传入（建议默认4，可配置4–6）。实现上可采用：
  - 方式A（更快）：工作流层并发触发多次 `--count 1` 调用；
  - 方式B（更简）：使用 CLI 的 `--count N` 串行重复（非严格并行）。
- 种子策略：
  - `FusionRandomize` 默认使用“varying seeds”（为每次调用分配不同 `seed` 以增加多样性）；
  - 其他接口默认固定 `seed` 以增强可复现性；如未显式给定 `seed`，可按时间或伪随机分配并记录在运行日志（不修改元数据结构）。

## 代码结构调整
- 新增包：`src/workflow/`（仅封装编排逻辑，不改动 Ark SDK 调用细节）
  - `src/workflow/interfaces.py`
    - 定义接口名常量：`TextToImage`、`SketchTo3D`、`FusionRandomize`、`RefineEdit`
    - 定义每个接口的输入规则（是否需要 `primary_image`、是否允许 `ref_images`、prompt 必需性）与种子策略（fixed/varying）
  - `src/workflow/templates.py`
    - 定义模板键与占位符签名（Python 字符串模板形式），不写具体文案
    - 例如：`sketch_to_concept_v1`、`material_variant_v1` 等键名与其所需占位符列表
  - `src/workflow/runner.py`
    - 核心编排：`run_interface(...)` 将四类接口的输入规范化为 `ark_image_cli` 参数
    - 处理 Prompt 模式：`template|custom`；模板模式下仅做占位符插值，不写具体文案
    - Ark 透传默认值在此层统一设置：`sequential_image_generation=false`、`response_format=url`、`watermark=false`（可被显式参数覆盖）
    - 并行策略：
      - 默认使用单次 CLI 调用 + `--count num_candidates`（串行但单一 `metadata.json`）
      - 可选启用并发模式：并发触发 `num_candidates` 次 `--count 1` 调用（更快）；该模式将产生多个 `metadata.json`（不合并、不新增字段）
    - 种子策略：按接口映射决定 `fixed|varying`；未显式给定时自动分配并记录到运行日志
  - `src/workflow/cli.py`
    - 提供统一入口：`python -m src.workflow.cli`，参数包括：`--interface`、`--prompt-mode`、`--template-key`、`--template-params`、`--custom-prompt`、`--primary-image`、`--ref-images`、`--num-candidates`、Ark 透传参数与 `--concurrency` 开关
    - 该 CLI 仅调用 `runner.run_interface`，真实调用仍由 `src/ark_image_cli.py` 完成

- 现有代码最小改动：
  - `src/ark_image_cli.py` 不必修改逻辑与默认值；若后续需要，也可新增非破坏性参数（如 `--interface` 用于日志标识），但本任务不做强制修改
  - 依赖与配置均沿用 `config.toml` 与 S10-P0-1 的安装说明

- 示例命令（将补充到 `examples/commands.txt`）
  - 文生图（4张，默认串行 `--count 4`）：
    - `python -m src.workflow.cli --interface TextToImage --prompt-mode custom --custom-prompt "蓝色金属漆，现代感" --num-candidates 4 --response-format url --watermark false`
  - 线稿转3D（并发4次，每次 `--count 1`）：
    - `python -m src.workflow.cli --interface SketchTo3D --prompt-mode custom --custom-prompt "以线稿为基础生成高保真3D" --primary-image examples/草稿.jpg --num-candidates 4 --concurrency true`

## 核心验收标准
- 四个接口均可通过单次触发产出 `num_candidates`（1–6）张候选；运行成功后图片与一次请求的元数据写入 `outputs/`，结构与字段沿用 S10-P0-1（本任务不新增元数据字段）。
- 模板/自定义两种 Prompt 模式均可用：
  - 模板占位齐全、缺参时报错；
  - 自定义模式下直通文本，不依赖模板。
- 仅使用文档存在的 Ark 参数名；对错误/超时给出明确信息；支持 `config.toml` 配置。
- 复现性：同一输入（含种子、模板参数）、同一版本下可重跑得到一致结果（受模型随机性与平台更新影响的可接受波动除外）。

## 接口契约（I/O与处理规则）
- 通用输入：
  - `interface_name` ∈ {`TextToImage`, `SketchTo3D`, `FusionRandomize`, `RefineEdit`}
  - `prompt_mode` ∈ {`template`, `custom`}
  - `template_key: str`、`template_params: Dict[str, Any]`（模板模式时必需）
  - `custom_prompt: str`（自定义模式时必需）
  - `primary_image: str`、`ref_images: List[str]`（按接口需要）
  - `num_candidates: int`（建议默认4，范围4–6）
  - Ark 透传：`size|seed|guidance_scale|sequential_image_generation|response_format|watermark|...`
- TextToImage：不传入图片；仅文本生成。
- SketchTo3D：`primary_image` 必填；如传入多图仅采用主图，其余忽略（在运行日志中提示）。
- FusionRandomize：`primary_image` 必填，`ref_images` 0–2 张；可无 prompt。
- RefineEdit：`primary_image` 必填，`ref_images` 0–2 张；结合 prompt 做微调导向。

输出：
- 图片与 `metadata.json` 写入 `outputs/`，命名与结构沿用 S10-P0-1；本任务不新增元数据字段。
- 若需记录模板键/展开后的最终 Prompt，可在工作流层另行生成运行日志（如 `.runlog` 或控制台输出），不写入 `metadata.json`。

## 执行步骤（step by step）
- [AI] 梳理四类接口的入参与规则，定义模板键名与占位符签名（不写文案）。
- [AI] 设计工作流并发策略：并发触发多次 CLI（`--count 1`）或使用串行 `--count N`；确定默认 `num_candidates=4`、并发上限（建议≤4）、重试（建议1次）。
- [AI] 提供最小示例命令与复现说明；必要时输出运行日志以便对齐模板键与最终 Prompt。
- [Human] 提供样例图片与模板文案；在本地填写 `config.toml`，运行示例并确认接口字段与文档一致。
- [AI] 根据实际返回字段与稳定性反馈，微调参数/并发/重试配置（不修改元数据结构）。

## 依赖/风险
- 依赖：Ark SDK 安装与 API Key；本地 I/O 权限与并发策略可用性。
- 风险：
  - “随机融合/编辑”的可控性依赖模型能力；
  - 并发与配额/QPS/超时策略可能影响稳定性；
  - 负面提示无专用字段时需并入主 Prompt 文本（模板由产品侧最终定稿）。

## 复现说明
1) 安装依赖与配置同 S10-P0-1（`volcengine-python-sdk[ark]`、`requests`、`toml`；复制 `config.toml.example` 并填入 API Key）。
2) 以 TextToImage 为例（单次产出4张）：
   - 并发方式：并行触发4次 `src/ark_image_cli.py --count 1`（不同 `seed` 或相同 `seed` 视接口策略），或串行 `--count 4`。
3) 以 SketchTo3D 为例（线稿+prompt，产出N张）：
   - 传入 `--images <path_to_sketch>` 与 `--prompt`，其余同上。
4) FusionRandomize/RefineEdit：
   - 传入主图与0–2张辅助参考图（顺序 `[primary, *ref_images]`），`FusionRandomize` 默认使用“varying seeds”。
5) 运行完成后，输出与 `metadata.json` 写入 `outputs/`，结构沿用 S10-P0-1。

## 验收结论（已完成）
- 状态：完成（工作流封装与默认值生效；示例可运行）
- 范围：四接口定义+模板占位+批量/并发产出链路；不新增元数据字段
- 统一模型：`doubao-seedream-4-0-250828`
- 默认参数：`size=4K`、`sequential_image_generation=disabled`、`response_format=url`、`watermark=false`

备注：模板实际文案由产品侧最终提供；当 Ark 文档新增字段（如权重等）后，可通过 CLI 的 `--param/--json-params` 透传，无需修改元数据结构。
