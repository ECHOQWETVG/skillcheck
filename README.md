# SkillCheck

**简体中文** | [English](README.en.md)

[![构建与测试](https://github.com/ECHOQWETVG/skillcheck/actions/workflows/package.yml/badge.svg)](https://github.com/ECHOQWETVG/skillcheck/actions/workflows/package.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](pyproject.toml)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**发布 AI Agent Skill 前，先检查清单、文本风险与测试结果。**

SkillCheck 是一个本地命令行工具，帮助 Skill 作者和维护者发现常见问题，并生成带校验文件的发布包。可以在电脑上运行，也可以接入 GitHub Actions；运行检查无需模型 API、账号或服务器。

[下载 v0.1.0 Alpha](https://github.com/ECHOQWETVG/skillcheck/releases/tag/v0.1.0) · [查看示例](examples/hello-skill) · [反馈问题](https://github.com/ECHOQWETVG/skillcheck/issues)

> 当前为 Alpha 版本。检测采用静态规则，可能误报或漏报；Agent 兼容性检查只核对清单声明，不会启动 Agent 验证实际效果。

## 能帮你做什么

| 检查项 | 具体内容 |
| --- | --- |
| 清单校验 | 检查名称、版本、描述、许可证、入口文件与路径越界 |
| 敏感信息 | 识别部分 API Key、GitHub Token、私钥和硬编码凭据模式 |
| 危险操作 | 检查下载脚本后直接执行、删除根目录、强制推送等命令模式 |
| 提示注入 | 标记忽略既有指令、泄露系统提示、向用户隐藏行为等文本模式 |
| 文本与文件 | 检查隐藏 Unicode 字符、符号链接，提示无法扫描的文件 |
| 权限声明 | 提示文本中的 Shell、网络使用迹象与声明不一致的情况 |
| 声明式测试 | 确认指定文本存在，或禁止指定文本出现 |
| 发布与校验 | 生成压缩包、SHA-256 校验文件和来源元数据 |

适合发布 Skill 前自查、给 Skill 仓库增加 CI 检查，以及在审阅第三方 Skill 时辅助定位问题。

## 快速开始

### 1. 安装

需要 **Python 3.11 或更新版本**。通过下列 GitHub 地址安装还需要 Git。

**macOS / Linux：**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "git+https://github.com/ECHOQWETVG/skillcheck.git@v0.1.0"
```

<details>
<summary>Windows PowerShell 安装方式</summary>

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install "git+https://github.com/ECHOQWETVG/skillcheck.git@v0.1.0"
```

后续命令中的 `skillcheck` 使用 `.venv\Scripts\skillcheck.exe` 代替即可，无需激活虚拟环境。

</details>

没有 Git 时，可以从 [Release 页面](https://github.com/ECHOQWETVG/skillcheck/releases/tag/v0.1.0) 下载 wheel，在下载目录执行：

```bash
python -m pip install ./skillcheck-0.1.0-py3-none-any.whl
```

### 2. 创建并检查一个 Skill

```bash
# 创建示例 Skill，目标目录应为空或尚不存在
skillcheck init my-skill

# 检查清单与文本风险，警告也视为失败
skillcheck lint my-skill --strict

# 执行静态检查，以及存在时的声明式测试
skillcheck test my-skill --strict

# 核对清单是否声明支持 codex
skillcheck compat my-skill --agent codex
```

正常的静态检查输出为：

```text
OK: no issues found
```

`init` 生成 `skill.yaml` 和 `SKILL.md`，不生成测试文件。没有测试文件时，`test` 仍会完成静态检查，并提示未找到测试。

### 3. 打包并校验

```bash
skillcheck publish my-skill
skillcheck verify my-skill/.skillcheck/artifacts/hello-skill-0.1.0.tar.gz
```

模板中的名称是 `hello-skill`，因此产物也使用这个名称；修改清单后，请同步调整校验命令的文件名。

```text
my-skill/
├── SKILL.md
├── skill.yaml
└── .skillcheck/
    ├── SECURITY-REPORT.json
    └── artifacts/
        ├── hello-skill-0.1.0.tar.gz
        ├── hello-skill-0.1.0.tar.gz.sha256
        └── hello-skill-0.1.0.tar.gz.provenance.json
```

`publish` 会拦截错误、警告和失败的声明式测试。它只生成本地文件；把 `artifacts/` 中的三个文件上传到你自己 Skill 仓库的 GitHub Release，即可分享给使用者。

## 接入已有 Skill

`SKILL.md` 描述 Agent 应该如何执行任务；`skill.yaml` 描述供 SkillCheck 检查的元数据。已有 Skill 可以直接添加清单，无需重新初始化目录。

在 `SKILL.md` 所在目录创建 `skill.yaml`：

```yaml
schema_version: 1
name: my-skill
version: 0.1.0
description: 帮助整理项目更新说明
license: MIT
compatibility:
  agents:
    - claude-code
    - codex
    - cursor
permissions:
  shell: false
  network: false
  write_files: false
entrypoints:
  files:
    - SKILL.md
```

然后在该目录执行 `skillcheck lint . --strict`。请按 Skill 的真实用途填写描述、支持的 Agent 和权限；权限字段是声明，不会为 Skill 提供沙箱或运行时权限控制。

也支持 `skill.yml`、`skill.json` 和 `skill.toml`。一个目录只保留一份清单。YAML 使用内置的精简解析器，建议遵循上面的结构；复杂配置可以使用 JSON 或 TOML。

## 添加声明式测试

在 Skill 根目录创建可选的 `skill-tests.json`。以下内容可直接用于快速开始生成的示例：

```json
{
  "cases": [
    {
      "name": "has-title",
      "file": "SKILL.md",
      "contains": ["# Hello Skill"]
    },
    {
      "name": "no-force-push",
      "file": "SKILL.md",
      "forbid": ["git push --force"]
    }
  ]
}
```

执行 `skillcheck test my-skill --strict` 即可查看结果：`contains` 要求文本存在，`forbid` 要求文本不存在。每个用例至少填写一项断言，值为非空字符串组成的数组。

测试只读取文件，不会执行 Skill、调用模型或运行其中的命令。测试文件中的危险命令断言不会触发对应的命令规则，但仍会检查密钥和隐藏字符。

## 命令速查

| 命令 | 用途 |
| --- | --- |
| `skillcheck init my-skill` | 生成最小示例 |
| `skillcheck lint my-skill --strict` | 静态检查，警告也视为失败 |
| `skillcheck test my-skill --strict` | 静态检查与声明式测试 |
| `skillcheck compat my-skill --agent codex` | 检查 Agent 兼容性声明 |
| `skillcheck publish my-skill` | 严格检查通过后生成本地发布包 |
| `skillcheck verify <产物路径>` | 校验 SHA-256，存在来源元数据时核对其摘要 |
| `skillcheck --help` | 查看帮助 |

检查结果可以输出为 JSON 或 SARIF，便于接入其他工具。报告建议保存到被扫描目录之外：

```bash
skillcheck lint my-skill --format json > skillcheck.json
skillcheck test my-skill --strict --format sarif > skillcheck.sarif
```

`lint` 和 `test` 默认不会因警告失败，添加 `--strict` 后会。`publish` 始终采用严格检查。

## 接入 GitHub Actions

在 **你的 Skill 仓库**中添加 `.github/workflows/skillcheck.yml`。下面的配置假设清单位于仓库根目录，每次推送或提交 Pull Request 时都会检查：

```yaml
name: SkillCheck

on: [push, pull_request]

permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: 安装 SkillCheck
        run: python -m pip install "git+https://github.com/ECHOQWETVG/skillcheck.git@v0.1.0"
      - name: 检查 Skill
        run: skillcheck test . --strict
```

如果 Skill 位于子目录，将最后一行的 `.` 换成该目录。需要上传 SARIF 到 GitHub Code Scanning 时，可以参考[本项目工作流](.github/workflows/skillcheck.yml)；其中的扫描位置是 `examples/hello-skill`，接入时需要调整。

## 发布规则与当前限制

- 扫描与打包共享文件清单；构建目录、虚拟环境、缓存和内部报告默认排除，压缩包会附带本次生成的安全报告。
- 非 UTF-8 文件和超过 5 MiB 的文件会被标记为无法扫描，严格检查与发布会因此失败。
- 自定义 `publish --output` 路径应位于 Skill 目录之外，或其 `.skillcheck/artifacts/` 内，避免覆盖源文件。
- SHA-256 用于核对文件完整性，需与可信来源的摘要比较；来源元数据尚未签名，不提供发布者身份认证。
- 检测基于静态文本模式，部分自然语言规则以英文为主。扫描通过不代表绝对安全，也不代表 Skill 能在某个 Agent 中正确运行。

## 本地开发

在支持 Make 的环境中执行：

```bash
git clone https://github.com/ECHOQWETVG/skillcheck.git
cd skillcheck
make install-dev
make check
make build
```

运行时没有第三方 Python 依赖。开发环境使用 pytest、build 和 twine；GitHub CI 会在 Python 3.11、3.12、3.13 上构建并测试安装后的 wheel。

## 反馈与参与

遇到误报、漏报或使用问题，欢迎[提交 Issue](https://github.com/ECHOQWETVG/skillcheck/issues)。请附上工具版本、操作系统、执行命令和去除敏感信息后的最小示例。

安全漏洞请通过[私密报告入口](https://github.com/ECHOQWETVG/skillcheck/security/advisories/new)提交，具体说明见 [SECURITY.md](SECURITY.md)。

本项目使用 [MIT 许可证](LICENSE)。
