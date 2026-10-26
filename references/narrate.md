# narrate.ps1 / narrate.py 操作手册

Windows 入口 `scripts/narrate.ps1`：`-Check` 检查而不生成；或同时给 `-TextFile <UTF-8台词文件>`、`-Output <新WAV路径>`。可选 `-BundleDirectory <本地分卷目录>` 用于首次离线安装；已有运行包时忽略。不要求全局 Python。缺失时自动调用固定版本安装器，失败即停。

底层 `scripts/narrate.py`：`--check` 或 `--text-file <文件> --output <新WAV>`；可选 `--config <完整配置JSON>`，默认 Skill 声音配置。相对资源按 Skill 根目录解析，只用包内 Python。空行分段，段间约 0.5 秒；输出在 Skill 外，不能覆盖已有文件。`--help` 查看参数。

强制本地推理、禁遥测，无密钥或付费调用。CPU、float32、eager attention、6 个计算线程，保留确认的原声、原文、seed、temperature 和完整 ICL，不改音高或后期加速。`--check` 核对参考摘要、模型尺寸、绑定和依赖可见性，不等于模型加载或听审通过。

退出 0 成功，非 0 看 stderr。已有输出、空台词、参考摘要不符或模型损坏会停止，不覆盖旧文件。正常生成只写指定新 WAV；写出中途失败可检查后手动删除未完成的新文件，换版本名重试。运行包回退用[remove-runtime.ps1](remove-runtime.md)。方案与使用示例见[配音运行](配音运行.md)。
