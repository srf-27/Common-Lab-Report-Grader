"""测试入口（不依赖 pytest）：python tests/run_all.py [-k 关键字]

发现 tests/unit 与 tests/integration 下所有 test_*.py，执行其中的 test_* 函数。
"""

import importlib.util
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Windows 控制台默认 GBK：测试里全是中文，不重配就是一屏乱码
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def modules():
    for folder in ("unit", "integration"):
        for path in sorted((ROOT / "tests" / folder).glob("test_*.py")):
            spec = importlib.util.spec_from_file_location(f"t_{folder}_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            yield path, module


def main(argv):
    # 测试客户端统一豁免 CSRF（app.testing）；test_csrf.py 会临时关掉它单独验证
    from experiment_report_grader.app import app
    app.config["TESTING"] = True
    keyword = ""
    if "-k" in argv:
        keyword = argv[argv.index("-k") + 1]
    passed = failed = 0
    for path, module in modules():
        for name in sorted(n for n in dir(module) if n.startswith("test_")):
            label = f"{path.relative_to(ROOT)}::{name}"
            if keyword and keyword not in label:
                continue
            try:
                getattr(module, name)()
                passed += 1
                print(f"PASS {label}")
            except Exception:
                failed += 1
                print(f"FAIL {label}")
                traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
