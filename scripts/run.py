# -*- coding: utf-8 -*-
"""项目统一入口（唯一需要记住的命令）。

为什么需要它
------------
这台机器上有两个 Python，而且 conda 环境不在默认位置：

  * E:\\python\\python.exe                        3.12.3，只有 numpy/pandas/matplotlib/pillow
  * C:\\Users\\yuantai\\.conda\\envs\\adedge-patchcore\\python.exe   3.10.22 + torch 2.6.0+cu124

如果直接用 `python xxx.py`，很可能用的是前一个，然后报 ModuleNotFoundError: torch。
本入口会自动找到"研究用解释器"（装了 torch 的那个）来跑 Python 任务，
并用 `powershell -ExecutionPolicy Bypass` 来跑 .ps1 任务。

用法
----
    python scripts\\run.py            # 列出所有可用任务
    python scripts\\run.py list       # 同上
    python scripts\\run.py figures    # 生成图表
    python scripts\\run.py all        # 跑一遍所有"当前可跑"的任务

    # 强制指定解释器
    python scripts\\run.py figures --python C:\\path\\to\\python.exe

注意
----
凡是从别的程序捕获子进程输出的写法在受限环境下会失败（EPERM），
所以这里一律用 stdio 继承（subprocess.call），不做输出捕获。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "project" / "src"

# ---------------------------------------------------------------- 解释器发现
CANDIDATES = [
    os.environ.get("ADEDGE_PYTHON"),
    str(Path.home() / ".conda" / "envs" / "adedge-patchcore" / "python.exe"),
    r"C:\Users\yuantai\.conda\envs\adedge-patchcore\python.exe",
    r"E:\anaconda\envs\adedge-patchcore\python.exe",
]


def has_torch(py: str) -> bool:
     try:
        r = subprocess.run([py, "-c", "import torch"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def find_python(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    for c in CANDIDATES:
        if c and Path(c).exists() and has_torch(c):
            return c
    # 退一步：当前解释器或候选里存在的第一个
    if has_torch(sys.executable):
        return sys.executable
    for c in CANDIDATES:
        if c and Path(c).exists():
            return c
    return sys.executable


# ---------------------------------------------------------------- 任务定义
# kind: py  -> 用研究解释器跑 Python 脚本
#       ps1 -> 用 powershell -ExecutionPolicy Bypass 跑
#       seq -> 依次跑多个子任务
PY = "py"
PS1 = "ps1"
SEQ = "seq"

TASKS = {
    "env": dict(kind=PS1, script="check_env.ps1",
                extra=["-Python", "{PY}", "-EnvName", "adedge-patchcore", "-Root", str(ROOT)],
                desc="环境验收：GPU 冒烟 + 分辨率上限 + 导出 pip freeze（patchcore 环境）",
                needs=[]),
    "env-dino": dict(kind=PS1, script="check_env.ps1",
                     extra=["-Python", os.path.join(str(Path.home()), ".conda", "envs",
                                                    "adedge-anomalydino", "python.exe"),
                            "-EnvName", "adedge-anomalydino", "-Root", str(ROOT)],
                     desc="环境验收（anomalydino 环境，numpy 1.26）",
                     needs=[]),
    "anchors": dict(kind=PS1, script="fetch_sources.ps1",
                    extra=["-Root", str(ROOT)],
                    desc="把三个上游源码按 commit 重新锚定（ZIP + 树指纹）",
                    needs=["网络"]),
    "bounds": dict(kind=PY, script=str(SRC / "w1_bounds_example.py"), extra=[],
                   desc="A14-3：六向量/两中心手算例子（区间与决策核对）", needs=[]),
    "distance": dict(kind=PY, script=str(SRC / "w1_distance_checks.py"), extra=[],
                     desc="A14-2：人造向量距离检查 + 分块/暴力核对 + GPU 计时", needs=[]),
    "vram": dict(kind=PY, script=str(SRC / "w1_vram_limit.py"), extra=[],
                 desc="显存安全上限与溢出警戒实测（会占用 GPU 数分钟）", needs=["GPU 空闲"]),
    "manifests": dict(kind=PY, script=str(SCRIPTS / "make_manifests.py"),
                      extra=["--self-test"],
                      desc="三角色清单：合成自检（不需要数据集）", needs=[]),
    "manifests-real": dict(kind=PY, script=str(SCRIPTS / "make_manifests.py"),
                           extra=["--data-root", str(ROOT / "data" / "mvtec_ad"),
                                  "--categories", "bottle", "tile", "screw"],
                           desc="三角色清单：真实数据（需要 MVTec AD 已就位）",
                           needs=["MVTec AD 数据"]),
    "figures": dict(kind=PY, script=str(SCRIPTS / "make_figures.py"), extra=[],
                    desc="生成图表（PDF+PNG+manifest，位级可复现）", needs=[]),
    "all": dict(kind=SEQ, tasks=["bounds", "distance", "manifests", "figures"],
                desc="跑一遍所有当前可跑的任务（不含 GPU 扫描与真实数据）", needs=[]),
}


def run_task(name: str, py: str) -> int:
    t = TASKS[name]

    if t["kind"] == SEQ:
        rc = 0
        for sub in t["tasks"]:
            print(f"\n{'='*72}\n[{name}] -> {sub}\n{'='*72}")
            rc |= run_task(sub, py)
        return rc

    if t["kind"] == PS1:
        script = SCRIPTS / t["script"]
        if not script.exists():
            print(f"[ERROR] 找不到 {script}")
            return 2
        extra = [a.replace("{PY}", py) for a in t.get("extra", [])]
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", str(script)] + extra
    else:
        script = Path(t["script"])
        if not script.exists():
            print(f"[ERROR] 找不到 {script}")
            return 2
        cmd = [py, str(script)] + t.get("extra", [])

    print(f"[run] {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True, description="adedge 项目统一入口")
    ap.add_argument("task", nargs="?", default="list")
    ap.add_argument("--python", default=None, help="强制指定研究用解释器")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    py = find_python(args.python)

    if args.task in ("list", "help", "--help") or args.list:
        print(f"仓库根目录 : {ROOT}")
        print(f"研究解释器 : {py}")
        print(f"当前解释器 : {sys.executable}")
        print()
        print(f"{'任务':<16}{'需要':<16}说明")
        print("-" * 96)
        for name, t in TASKS.items():
            print(f"{name:<16}{('、'.join(t['needs']) or '—'):<16}{t['desc']}")
        print()
        print("例：python scripts\\run.py figures")
        return 0

    if args.task not in TASKS:
        print(f"[ERROR] 未知任务 {args.task!r}；用 `python scripts\\run.py list` 查看全部任务")
        return 2

    print(f"仓库根目录 : {ROOT}")
    print(f"研究用解释器: {py}")
    needs = TASKS[args.task]["needs"]
    if needs:
        print(f"该任务需要 : {'、'.join(needs)}")
    print("-" * 96)
    return run_task(args.task, py)


if __name__ == "__main__":
    sys.exit(main())
