#!/usr/bin/env python3
"""
coding-team-loop 全量验证入口。

用法：
  python3 run_all_tests.py          # 运行所有测试
  python3 run_all_tests.py -v       # 详细输出

每次修改 skill 规则、脚本或正则后，必须执行此脚本确认无回归。

测试文件约定：
  - 文件名格式：test_*.py，放在 evals/ 目录下
  - 对应关系：一个 refs/*.md 规则文档 → 一个 test_*.py
  - 新增规则文件时直接创建对应 test_*.py，无需修改此入口
"""
import subprocess
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).parent


def discover_modules():
    """自动发现 evals/ 下所有 test_*.py，按文件名排序。"""
    files = sorted(EVALS_DIR.glob("test_*.py"))
    # 用文件名（去掉 test_ 前缀和 .py 后缀）作为描述
    return [(f.name, f.stem.removeprefix("test_").replace("_", " ")) for f in files]


def main():
    verbose = "-v" in sys.argv
    modules = discover_modules()
    passed = 0
    failed = 0
    errors = []

    print(f"=== coding-team-loop 全量验证 ({len(modules)} 个模块) ===\n")

    for filename, desc in modules:
        path = EVALS_DIR / filename

        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True, text=True, cwd=str(EVALS_DIR),
        )

        if result.returncode == 0:
            passed += 1
            status = "PASS"
        else:
            failed += 1
            status = "FAIL"
            errors.append(f"  {desc} ({filename}):\n{result.stdout}{result.stderr}")

        if verbose:
            print(f"[{status}] {desc} ({filename})")
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    print(f"       {line}")
            print()
        else:
            print(f"[{status}] {desc}")

    print(f"\n结果: {passed} passed, {failed} failed, 共 {passed + failed} 个模块")

    if errors:
        print("\n--- 失败详情 ---")
        for e in errors:
            print(e)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
