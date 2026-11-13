# MiMoCode Termux 整合包

在 Android 的 Termux 上一键运行官方 **MiMoCode** 的整合包：Python 菜单 + glibc 启动器 + 多模型配置 + 28 个开箱即用的技能。与 `Claude_.zip`（Claude Code 整合包）同构，全部改动只依赖 Termux 官方源和 MiMoCode 官方发布物。

---

## 架构

### 目录结构

```
MiMoCode_/
├── an/mimo                 # 官方 MiMoCode 单文件二进制（linux-arm64，glibc 版）
├── mimocode.py             # 唯一入口：中文菜单 + 启动器 + 升级 + 卸载
├── .config/mimocode/
│   ├── mimocode.jsonc      # 全局配置：provider / 默认模型 / skills.paths / instructions
│   ├── AGENTS.md           # 全局行为准则（经 instructions 注入所有会话）
│   └── skills/             # 28 个技能（SKILL.md + YAML frontmatter）
├── README.md               # 本文档
└── 使用说明.txt             # 面向终端用户的简要说明
```

安装 = 把全部内容（含 `.config` 隐藏目录）复制到 Termux 用户目录 `~/`。

### 运行链路

```
Termux（Android / Bionic libc）
   │
   ▼
mimocode.py ── 菜单循环（Python，仅标准库）
   │
   ├─ 1.安装依赖 ──► pkg install python glibc-repo glibc glibc-runner openssl-glibc
   ├─ 2.配置模型 ──► 写 ~/.config/mimocode/mimocode.jsonc（provider + 默认 model）
   │                 └─ 写 ~/.local/state/mimocode/model.json（TUI 最近模型）
   │                 └─ `mimo models <pid>` 本地校验（不发付费请求）
   ├─ 3.启动agent ─► glibc-runner → an/mimo（TUI）
   ├─ 4.更新MiMoCode ► FDS 官方源下载 tar.gz → 原子替换 an/mimo
   └─ upgrade / uninstall（命令行参数，同上逻辑）
   │
   ▼
glibc-runner（grun）提供 glibc 运行时
   │
   ▼
an/mimo ──► MiMoCode TUI / run / 各子命令
```

### 关键设计

1. **必须经 glibc-runner 启动**  
   Termux 是 Android/Bionic libc，官方二进制是 glibc 版，直接执行会报 `cannot execute: required file not found`；用 `ld-linux --library-path` 方式加载该二进制会报 `libc.so: invalid ELF header`。因此统一走 `glibc-runner`，并在启动前剥离 `LD_LIBRARY_PATH`/`LD_PRELOAD`、固定 `HOME`，避免污染子进程（bash、termux-api 等）。`HOME`/`PREFIX` 从环境变量解析（兼容不同前缀的 Termux），glibc-runner 缺失时菜单降级为警告提示而不是崩溃。

2. **单脚本入口**  
   菜单、启动、升级、卸载合并进 `mimocode.py`。`upgrade`/`uninstall` 在进入菜单前按参数拦截——因为二进制在 grun 下 `/proc/self/exe` 指向的是 glibc 加载器，原生自升级/自卸载会定位错文件。

3. **升级是原子替换**  
   从官方 FDS 源 `releases/latest` 解析版本 → HEAD 校验存在 → 下载 `mimocode-linux-arm64.tar.gz` → 解压 → `os.replace` 原子换入 `an/mimo`。菜单顶部的版本号每次启动运行时读取（带缓存，升级后失效），不会显示过期版本。

4. **配置与校验闭环**  
   选完模型写入 `mimocode.jsonc`，随即用 `mimo models <provider>` 做本地注册校验，并把模型追加进 TUI 最近列表，保证进 TUI 就能切到刚配的模型。

5. **技能与准则全局注入**  
   技能目录通过配置 `skills.paths` 加载，行为准则通过 `instructions` 注入，对所有项目生效；技能是标准 `SKILL.md`（name + description frontmatter），与 MiMoCode 内置技能格式通用。

---

## 语言与技术栈

| 组件 | 语言 / 格式 | 说明 |
|---|---|---|
| 菜单 + 启动器 `mimocode.py` | **Python 3** | 仅用标准库（os/sys/json/shutil/tempfile/subprocess/urllib），零第三方依赖 |
| 被启动的主体 `an/mimo` | 官方二进制 | MiMoCode（OpenCode 的 fork，TypeScript/Bun 编译的单文件 ELF，glibc） |
| 配置 | JSONC | `~/.config/mimocode/mimocode.jsonc`，schema 见 `mimo.xiaomi.com/mimocode/config.json` |
| 技能 | Markdown + YAML frontmatter | `SKILL.md`，28 个 |
| 行为准则 | Markdown | `AGENTS.md` |
| 下载/压缩 | curl + tar | 升级用；zip 打包用 Python `zipfile` |

---

## 特点

- **一键依赖安装**：菜单内自动装齐 `python / glibc-repo / glibc / glibc-runner / openssl-glibc`。
- **单文件入口**：装依赖、配模型、启动、升级、卸载全在 `mimocode.py` 一个脚本里，无其他脚本依赖。
- **多模型开箱配置**：MiMo 官方 OAuth 登录、MiMo(API key)、DeepSeek、智谱 GLM、豆包 五个预设，外加自定义模型。
- **自定义接口四种协议**（均经本地 mock 服务器实测请求路径，不靠猜）：
  - OpenAI 兼容（Chat Completions）→ `@ai-sdk/openai-compatible` → `POST /v1/chat/completions`
  - OpenAI Responses → `@ai-sdk/openai` → `POST /v1/responses`
  - Anthropic 兼容 → `@ai-sdk/anthropic` → `POST /v1/messages`
  - Google Gemini → `@ai-sdk/google` → `POST /v1beta/models/<model>:streamGenerateContent`
- **28 个技能随包即用**：安全、架构、前端/后端、数据、QA 等，全局加载。
- **版本号动态显示**：运行时读 `--version`，升级后自动刷新，永不过期。
- **原子升级**：下载校验 → 原子换入，中断不会留下半截文件。
- **与已有 mimo 命令共存**：本包固定用 `~/an/mimo`，与系统里其他安装互不影响。
- **卸载保留数据**：`uninstall` 只删包内文件，配置、技能、会话保留（提示里给出彻底清理命令）。

---

## 使用方法

### 环境要求

- Android 上的 Termux，`aarch64` 架构
- 能访问 Termux 软件源与 MiMoCode 官方 FDS 下载源的网络

### 安装

把 `MiMoCode_` 全部内容（**含隐藏目录 `.config`**）复制到 Termux 用户目录：

```sh
cp -r MiMoCode_/* ~/ && cp -r MiMoCode_/.config ~/
```

（MT 管理器等文件管理器直接全选复制到 `/data/data/com.termux/files/home/` 也可以。）

### 菜单

```sh
python mimocode.py
```

| 选项 | 作用 |
|---|---|
| `1.安装依赖` | 更新软件源并安装运行所需包 |
| `2.配置模型` | 选择模型/接口，写入配置并本地校验 |
| `3.启动agent` | 直接打开 MiMo Code（无需任何选择） |
| `4.更新MiMoCode` | 从官方源下载最新版并原子替换 `an/mimo` |
| `5.退出` | 退出菜单 |

### 配置模型示例（自定义 Responses 接口）

1. 菜单选 `2` → 子菜单选 `6.自定义模型`
2. 接口格式选 `2.OpenAI Responses`
3. 依次输入 `Base_URL`（须以 `https://` 开头）、`API_key`、模型名，确认 `y`
4. 看到「配置成功 + 校验通过」即完成，菜单顶部「当前模型」会同步更新

### 命令行用法

```sh
python mimocode.py upgrade            # 升级到官方最新版
python mimocode.py upgrade 0.1.17     # 升级到指定版本
python mimocode.py uninstall          # 卸载（保留配置与技能）
```

### 卸载

菜单没有卸载项，用上面的命令行；或手动删 `~/an` 和 `~/mimocode.py`。

---

## 常见问题

- **启动报 `cannot execute: required file not found`**  
  依赖没装齐，跑菜单 `1.安装依赖`。
- **菜单顶部出现「⚠ glibc-runner 或 an/mimo 缺失」/ 版本显示"未知"**  
  同样是依赖没装齐（常见于刚复制到另一个 Termux 环境）。缺依赖时菜单仍可正常操作，直接选 `1.安装依赖` 即可，不会崩溃。
- **更新后菜单还显示旧版本号**  
  不会出现——版本号是运行时读的；若仍异常，删掉菜单脚本里的缓存或重开菜单即可。
- **想换模型又不想走菜单**  
  直接编辑 `~/.config/mimocode/mimocode.jsonc`，或用 MiMoCode 自带的 `mimo providers login` / TUI 内 `/connect`。

---

## 声明

- `an/mimo` 为 **MiMoCode 官方发布物**，版权归原作者/官方所有；本包仅做原样分发与启动封装。
- 本包的脚本、配置模板与技能集合可自由使用、修改、再分发；开源时建议为脚本部分选择 MIT 或 Apache-2.0 许可证，二进制按官方许可另行声明。
- 所有 API key 只保存在本地 `mimocode.jsonc`，不上传、不外发；预置接口地址为常见官方网关，仅供填空参考。


QQ群:602384593
