import os
import sys
import json
import shutil
import tempfile
import subprocess

# ===== 路径（从环境变量解析，兼容不同 Termux 前缀） =====
HOME = os.environ.get("HOME") or "/data/data/com.termux/files/home"
PREFIX = os.environ.get("PREFIX") or "/data/data/com.termux/files/usr"
MIMO_BINARY = os.path.join(HOME, "an", "mimo")
GRUN = next((c for c in (os.path.join(PREFIX, "bin", "glibc-runner"),
                         shutil.which("glibc-runner"), shutil.which("grun"))
             if c and os.path.exists(c)),
            os.path.join(PREFIX, "bin", "glibc-runner"))
FDS = "https://mimocode.cnbj1.mi-fds.com/mimocode/mimocode/releases"
CFG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "mimocode")
PZWJ = os.path.join(CFG_DIR, "mimocode.jsonc")
STATE_DIR = os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state")
MODEL_JSON = os.path.join(STATE_DIR, "mimocode", "model.json")

# 干净环境：不污染子进程（bash、termux-api 等）
clean_env = os.environ.copy()
clean_env.pop("LD_LIBRARY_PATH", None)
clean_env.pop("LD_PRELOAD", None)
clean_env["HOME"] = HOME


_grun_broken = False


def run_mimo(args, capture=False):
    """通过 glibc-runner 运行 MiMoCode（该二进制是 glibc 版，直接跑不起来）。
    glibc-runner 未安装/损坏时不抛异常，返回 127 让菜单继续可用。"""
    global _grun_broken
    try:
        return subprocess.run([GRUN, MIMO_BINARY] + args, env=clean_env,
                              capture_output=capture, text=True)
    except OSError:
        _grun_broken = True
        return subprocess.CompletedProcess([GRUN] + args, 127, "", "")


def upgrade(target=""):
    # 解析目标版本：没有指定就取官方最新
    target = (target or "").strip().lstrip("v")
    if not target:
        import urllib.request
        try:
            with urllib.request.urlopen(FDS + "/latest", timeout=30) as r:
                target = r.read().decode().strip().lstrip("v")
        except Exception as e:
            print("mimo: 获取最新版本失败（检查网络）：%s" % e)
            return
        if not target:
            print("mimo: 无法获取最新版本号")
            return
    url = "%s/v%s/mimocode-linux-arm64.tar.gz" % (FDS, target)
    # 先确认该版本存在
    code = subprocess.run(["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", url],
                          capture_output=True, text=True).stdout.strip()
    if code != "200":
        print("mimo: 版本 v%s 不存在 (HTTP %s)" % (target, code))
        sys.exit(1)
    cur = run_mimo(["--version"], capture=True).stdout.strip() or "unknown"
    if cur == target:
        print("mimocode %s 已是当前版本" % target)
        return
    print("正在升级 mimocode %s -> %s ..." % (cur, target))
    tmp = tempfile.mkdtemp()
    try:
        gz = os.path.join(tmp, "mimo.tar.gz")
        subprocess.run(["curl", "-fsSL", "-o", gz, url], check=True)
        subprocess.run(["tar", "-xzf", gz, "-C", tmp], check=True)
        new = os.path.join(tmp, "mimo")
        if not os.path.exists(new):
            print("mimo: 压缩包里没有找到 mimo 可执行文件")
            sys.exit(1)
        os.chmod(new, 0o755)
        staged = MIMO_BINARY + ".new.%d" % os.getpid()
        shutil.move(new, staged)
        os.replace(staged, MIMO_BINARY)  # 原子替换
        print("mimocode 已升级到 %s" % target)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ver = run_mimo(["--version"], capture=True).stdout.strip()
    print("当前版本：%s" % (ver or "未知（glibc-runner 未安装？）"))


def uninstall():
    # 只卸载本整合包的文件，配置/技能/会话数据保留
    for p in (MIMO_BINARY, os.path.join(HOME, "mimocode.py")):
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        os.rmdir(os.path.join(HOME, "an"))
    except OSError:
        pass
    print("mimocode 整合包已卸载（an/、mimocode.py 已删除）。")
    print("配置与技能仍保留在 ~/.config/mimocode，如需一并删除：")
    print("  rm -rf ~/.config/mimocode ~/.local/share/mimocode ~/.local/state/mimocode ~/.cache/mimocode")


def duqu():
    """读取当前默认模型"""
    try:
        with open(PZWJ, "r") as f:
            return json.load(f).get("model")
    except Exception:
        return None


def gengxin_recent(pid, mx):
    """把新模型加进 TUI 最近使用列表（保留原有收藏/顺序）"""
    data = {"recent": [], "favorite": [], "variant": {}}
    try:
        if os.path.exists(MODEL_JSON):
            with open(MODEL_JSON, "r") as f:
                old = json.load(f)
            for k in old:
                data[k] = old[k]
    except Exception:
        pass
    recent = [r for r in data.get("recent", [])
              if not (r.get("providerID") == pid and r.get("modelID") == mx)]
    recent.insert(0, {"providerID": pid, "modelID": mx})
    data["recent"] = recent[:10]
    os.makedirs(os.path.dirname(MODEL_JSON), exist_ok=True)
    with open(MODEL_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def shezhi(pid, mc, npm, url, api_key, mxmz):
    """写入 provider 配置并设为默认模型"""
    try:
        with open(PZWJ, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {"$schema": "https://mimo.xiaomi.com/mimocode/config.json"}
    except ValueError:
        print("=======================")
        print("\033[1;31m配置文件不是标准 JSON，请手动检查 %s\033[0m" % PZWJ)
        print("=======================")
        return
    config.setdefault("provider", {})[pid] = {
        "name": mc,
        "npm": npm,
        "only_configured_models": True,
        "models": {mxmz: {"name": mxmz}},
        "options": {"baseURL": url, "apiKey": api_key},
    }
    config["model"] = "%s/%s" % (pid, mxmz)
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(PZWJ, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    gengxin_recent(pid, mxmz)
    print("=======================")
    print("\033[32m配置成功！默认模型：%s/%s\033[0m" % (pid, mxmz))
    # 本地校验：确认 provider/model 注册成功（不发真实请求）
    r = run_mimo(["models", pid], capture=True)
    if ("%s/%s" % (pid, mxmz)) in (r.stdout or ""):
        print("\033[32m校验通过：mimo models 已识别该模型\033[0m")
    else:
        print("\033[33m提示：mimo models 未列出该模型，请检查配置\033[0m")
    print("=======================")


def zidingyi():
    print('''        ---接口格式---
        \033[1;94m1.OpenAI兼容（Chat Completions）\033[0m
        \033[1;38;5;208m2.OpenAI Responses\033[0m
        \033[1;38;5;93m3.Anthropic兼容\033[0m
        \033[1;38;5;42m4.Google Gemini\033[0m''')
    g = input("请输入对应数字：")
    if g == "1":
        npm = "@ai-sdk/openai-compatible"
        mc = "自定义"
    elif g == "2":
        npm = "@ai-sdk/openai"
        mc = "自定义Responses"
    elif g == "3":
        npm = "@ai-sdk/anthropic"
        mc = "自定义Anthropic"
    elif g == "4":
        npm = "@ai-sdk/google"
        mc = "自定义Gemini"
    else:
        print("\033[41;30m仅支持1-4！\033[0m")
        return
    u = input("Base_URL：")
    if u[:8] != "https://":
        print("⚠️ \033[31m请输入以 https:// 开头的 URL\033[0m")
        return
    key = input("API_key：")
    mxmz = input("主模型名字：")
    p = input("\033[1m是否确认修改？(y/n)：\033[0m")
    if p == "y":
        shezhi("custom", mc, npm, u, key, mxmz)
    else:
        print("已取消")


_huancun = {}


def banben():
    """查询 MiMoCode 版本号（缓存，升级后自动失效）"""
    if "v" not in _huancun:
        _huancun["v"] = run_mimo(["--version"], capture=True).stdout.strip() or "未知"
    return _huancun["v"]


# glibc 二进制在 grun 下 /proc/self/exe 会指向 glibc 加载器，
# 原生 upgrade/uninstall 会自错位，故在这里拦截处理
if len(sys.argv) > 1 and sys.argv[1] == "upgrade":
    upgrade(sys.argv[2] if len(sys.argv) > 2 else "")
    sys.exit(0)
if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
    uninstall()
    sys.exit(0)

while True:
    os.system("clear")
    try:
        dqpz = duqu()
    except Exception:
        dqpz = None
    dppz = "无模型配置"
    print(f'''\033[38;5;208m
███╗   ███╗██╗███╗   ███╗ ██████╗
████╗ ████║██║████╗ ████║██╔═══██╗
██╔████╔██║██║██╔████╔██║██║   ██║
██║╚██╔╝██║██║██║╚██╔╝██║██║   ██║
██║ ╚═╝ ██║██║██║ ╚═╝ ██║╚██████╔╝
╚═╝     ╚═╝╚═╝╚═╝     ╚═╝ ╚═════╝  code
\033[0m
\033[38;5;214m╔═══════════════════════════════════╗
║    MiMo code 整合包 v{banben()}       ║
╚═══════════════════════════════════╝\033[0m
当前模型：{dqpz if dqpz is not None else dppz}
1.安装依赖
\033[32m2.配置模型\033[0m
\033[31m3.启动agent\033[0m
\033[36m4.更新MiMoCode\033[0m
\033[90m5.退出\033[0m''')
    if _grun_broken or not os.path.exists(GRUN) or not os.path.exists(MIMO_BINARY):
        print("\033[1;31m⚠ glibc-runner 或 an/mimo 缺失，请先执行「1.安装依赖」\033[0m")
        _grun_broken = False
    a = input("\033[1m请选择对应数字：\033[0m")
    if a == "1":
        print("\033[33m[更新] 更新软件源...\033[0m")
        os.system("pkg update -y >/dev/null 2>&1")
        print("\033[32m[更新] 软件源更新完成\033[0m")
        pkgs = ["python", "glibc-repo", "glibc", "glibc-runner", "openssl-glibc"]
        total = len(pkgs)
        for i, p in enumerate(pkgs, 1):
            if os.system(f"pkg list-installed 2>/dev/null|grep -q '^{p}/'"):
                print(f"\033[33m[{i}/{total}] 安装 {p}...\033[0m")
                os.system(f"pkg install {p} -y >/dev/null 2>&1")
                print(f"\033[32m[{i}/{total}] {p} 安装完成\033[0m")
            else:
                print(f"\033[32m[{i}/{total}] ✓ {p}\033[0m 已安装")
        print("\033[32m依赖检查完成！\033[0m")
    elif a == "2":
        print('''        ---配置模型---
        \033[1;38;5;208m1.MiMo官方登录(OAuth)\033[0m
        \033[1;38;5;218m2.MiMo(API_key)\033[0m
        \033[1;94m3.DeepSeek\033[0m
        \033[1;38;5;93m4.智谱GLM\033[0m
        \033[1;38;5;214m5.豆包AI\033[0m
        \033[1m6.自定义模型\033[0m''')
        b = input("请输入对应数字：")
        if b == "1":
            run_mimo(["providers", "login"])
        elif b == "2":
            api = input("\033[1m请输入API_key：\033[0m")
            shezhi("mimo", "MiMo", "@ai-sdk/anthropic",
                   "https://api.xiaomimimo.com/anthropic/v1", api, "mimo-v2.5-pro[1m]")
        elif b == "3":
            api = input("\033[1m请输入API_key：\033[0m")
            shezhi("deepseek", "DeepSeek", "@ai-sdk/anthropic",
                   "https://api.deepseek.com/anthropic/v1", api, "deepseek-v4-pro[1m]")
        elif b == "4":
            api = input("\033[1m请输入API_key：\033[0m")
            shezhi("glm", "智谱GLM", "@ai-sdk/anthropic",
                   "https://open.bigmodel.cn/api/anthropic/v1", api, "glm-5.2[1m]")
        elif b == "5":
            api = input("\033[1m请输入API_key：\033[0m")
            shezhi("doubao", "豆包AI", "@ai-sdk/openai-compatible",
                   "https://ark.cn-beijing.volces.com/api/compatible", api, "doubao-seed-2.1-pro")
        elif b == "6":
            zidingyi()
        else:
            print("\033[41;30m仅支持1-6！\033[0m")
    elif a == "3":
        try:
            run_mimo([])
        except KeyboardInterrupt:
            print("\n[!] Exited.")
        if _grun_broken:
            print("[!] glibc-runner 未安装或损坏，请先执行「1.安装依赖」")
            _grun_broken = False
    elif a == "4":
        upgrade()
        _huancun.clear()  # 升级后重新查询版本号
    elif a == "5":
        sys.exit()
    else:
        print("\033[41;30m仅支持1-5！\033[0m")
    input("\033[1m回车键返回菜单>\033[0m")
