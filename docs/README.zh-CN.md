# Intervals.icu Plugin

[![CI](https://github.com/askeer25/intervals-icu-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/askeer25/intervals-icu-plugin/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](../pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](../LICENSE)

**在与本地 AI 助手的对话中查看训练、分析恢复、安排课程。**

本插件将 Codex 和其他本地 MCP 客户端连接到你的 [Intervals.icu](https://intervals.icu) 个人账户，支持训练汇总、活动比较、恢复趋势、计划预览与课程文件导出。

[English](../README.md) · [快速开始](#快速开始) · [使用示例](examples.md) · [文档导航](README.md)

这是基于 [`intervals-icu-mcp`](https://github.com/hhopke/intervals-icu-mcp) 的**非官方社区插件**。使用你的个人 API Key，在本机运行。1.1.0 版本提供 **68 个工具、5 个 MCP 资源、9 个提示词和 4 个工作流技能**，删除功能关闭。

## 主要功能

- **训练汇总**：按日、周、月统计训练，支持运动类型与室内外筛选。
- **活动比较**：比较 2–10 次训练的距离、时间、配速、心率、功率与负荷，明确缺失指标和环境差异。
- **恢复趋势**：查看睡眠、HRV、静息心率、疲劳及训练负荷，提供有效样本数和观测日期。
- **计划执行回顾**：依据实际活动的明确配对关系，对照计划与完成情况。
- **预览后写入**：查看新增、更新、重复项与冲突，再提交并逐项核验。
- **课程导出**：将计划或课程库中的训练导出为 FIT、ZWO、MRC、ERG，不覆盖已有文件。

上游已有的活动、间歇、曲线、日历、课程库、装备和运动设置工具继续保留。具体范围见 [能力矩阵](capabilities.md)。

## 快速开始

### 1. 获取项目

安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，然后克隆仓库：

```bash
git clone https://github.com/askeer25/intervals-icu-plugin.git
cd intervals-icu-plugin
uv sync --locked --no-dev
```

也可以从 [Releases](https://github.com/askeer25/intervals-icu-plugin/releases) 下载源码 ZIP，并在解压后的项目根目录执行后续命令。

### 2. 连接账户

在 [Intervals.icu 设置](https://intervals.icu/settings) 中找到 **Developer Settings**，获取个人 API Key。在本机终端输入，不要粘贴到聊天中：

```bash
uv run --locked --no-dev intervals-icu-plugin setup
uv run --locked --no-dev intervals-icu-plugin doctor
```

`setup` 先只读验证账户，再保存至操作系统安全凭据库。运动员 ID 输入 `0` 即表示当前账户。无可用安全凭据库时，使用 [环境变量配置](configuration.md#environment-variables)。

### 3. 安装到 Codex

```bash
codex plugin marketplace add .
codex plugin add intervals-icu@intervals-icu-community --json
```

刷新或重启宿主，在新聊天中尝试：

> 汇总我最近七天的训练，并说明哪些指标缺失。

支持 Plugins 界面的宿主也可以从已登记的 `intervals-icu-community` marketplace 安装。宿主启动环境必须能够找到 `uv`。其他本地 MCP 客户端的配置见 [英文 README](../README.md#quick-start)。首版不提供托管连接器或多人公共服务器。

## 使用示例

| 目标 | 示例提示 |
|---|---|
| 回顾训练周期 | “按周汇总本月跑步，区分室内和户外训练。” |
| 比较两次训练 | “比较这两次跑步的配速、心率、持续时间和训练负荷。” |
| 查看恢复观测 | “查看最近 28 天的睡眠和 HRV，并列出有效样本数。” |
| 回顾计划执行 | “对照上周计划与已明确配对的实际活动。” |
| 安排下一周 | “草拟下周课程，先预览日历变更和冲突，再写入。” |
| 导出课程 | “将明天的计划课程导出为 FIT 文件。” |

完整工具输入与预期行为见 [使用示例](examples.md)。

### 计划如何写入

1. **预览**：检查课程输入，列出新增、更新、未变更项与冲突。此时只保存本地预览文件。
2. **审阅**：核对具体变更。用户已经明确授权写入该计划时，不重复询问。
3. **提交**：检查远端日历是否变化，通过稳定 UID 更新或创建课程，再逐项回读核验。

重试或修改同一逻辑课程时，保持 `plan_id` 与 `event_key` 不变；更换事件键会创建不同课程。预览有效期为 24 小时，日历变化后需要重新预览。部分成功会逐项报告，不执行删除回滚。

**保留的上游写入工具仍为直接写入。**编排训练计划时，应使用随插件提供的规划技能或新增预览/提交工具。

## 运行要求

| 项目 | 要求 |
|---|---|
| 运行环境 | Python 3.11+、uv，依赖由 `uv.lock` 锁定 |
| 账户 | 个人 Intervals.icu 账户及 API Key |
| 客户端 | Codex 或本地 stdio MCP 客户端 |
| 系统 | Windows、macOS、Linux；验证状态见 [验收记录](validation.md) |

首次安装需要网络。插件在本机运行，查询训练和健康数据时仍会连接 Intervals.icu。Windows 安装与 stdio 启动已完成本地验证，跨平台检查状态以 CI 为准。

## 数据准确性与支持边界

适配后的活动与健康数据读取保留 `0` 和 `false`，明确强度单位，并使用运动员本地日期。汇总分别说明读取是否完整、指标是否缺失，不将缺失值当作零值。

- **网站可见不代表 API 可读**：Strava 活动可能返回受限占位数据。[2026-10-09 官方说明](https://forum.intervals.icu/t/api-access-to-intervals-icu/609) 提示 Garmin 数据可能随后受限，但不能仅凭设备品牌判断已经受限。
- **会员边界仍然适用**：不绕过网站付费功能。
- **恢复结果是观测摘要**：不编造恢复总分，不诊断过度训练。
- **兼容范围明确**：未替换的上游工具保留其格式化、日期与请求行为。活动下载默认返回本地路径，而非 Base64。

详细说明见 [能力矩阵](capabilities.md)、[审计报告](audit.md) 和 [隐私说明](privacy.md)。

## 文档

| 文档 | 内容 |
|---|---|
| [配置说明](configuration.md) | 凭据、环境变量、时区和本地文件 |
| [使用示例](examples.md) | 提示词、结构化计划输入和课程导出 |
| [能力矩阵](capabilities.md) | 网站、公开 API 与插件的覆盖范围 |
| [故障排查](troubleshooting.md) | 鉴权、缺失数据、日历冲突和导出错误 |
| [验收记录](validation.md) | 已验证行为与尚未验证的范围 |
| [发布指南](releasing.md) | 安装包构建与校验 |

## 开发与贡献

```bash
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked pyright
uv run --locked python scripts/build_release.py
```

发布脚本验证清单、扫描分发文件，并生成附带 SHA-256 的插件源码 ZIP；凭据、预览、导出文件和虚拟环境不会进入发布包。

欢迎通过 [Issue](https://github.com/askeer25/intervals-icu-plugin/issues) 提交可复现的问题，或按 [贡献指南](../CONTRIBUTING.md) 提交改进。涉及敏感信息的问题请参阅 [SECURITY.md](../SECURITY.md)。

## 致谢与许可证

本项目的 MCP 基础能力来自 [`hhopke/intervals-icu-mcp`](https://github.com/hhopke/intervals-icu-mcp)，以固定版本依赖安装，不复制上游源码。署名见 [NOTICE](../NOTICE)。

项目采用 [MIT 许可证](../LICENSE)，与 Intervals.icu、Garmin、Strava、OpenAI 无隶属或背书关系。
