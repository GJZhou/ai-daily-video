# check_runtime.py 操作手册

安装器内部只读探针，无参数、无额外环境变量。用包内 `python.exe -X utf8 -I -B scripts/check_runtime.py` 运行，检查独立解释器前缀、禁用用户包、依赖来源及已加载 C++ DLL 的真实路径。成功退出 0 并输出 JSON；非 0 表示环境泄漏、依赖缺失或导入失败，不写文件、不生成音频。安装和失败恢复统一见[安装手册](install-runtime.md)，不要用全局 Python 代替探针所在运行包。
