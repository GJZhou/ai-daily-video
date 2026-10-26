# build_runtime.py 操作手册

用途：维护者从已验证 Windows x64 CPython 3.12 环境与既有模型构建配音包。不安装依赖、不联网、不复制原 Python 的第三方全局包；保留依赖自带许可和模型许可。

```powershell
python -B .\scripts\build_runtime.py --venv 'D:\来源\qwen_env' --base-python 'D:\来源\python' --model 'D:\来源\Qwen3-TTS-12Hz-1.7B-Base' --vc-redist 'D:\VS\VC\Redist\MSVC\14.40.33807\x64\Microsoft.VC143.CRT' --output 'D:\发布\voice-v1' --dry-run
# 核对后去掉 --dry-run 正式构建
```

必填参数：`--venv` 已验证虚拟环境；`--base-python` 匹配的完整 CPython 根目录；`--model` 清单指定 Base 模型目录；`--vc-redist` 已获许可的 Visual Studio 2022 x64 CRT 可再分发目录（本版 14.40.33810.0）；`--output` Skill 外尚不存在的新目录。`--dry-run` 校验路径与模型文件尺寸，展示复制范围，不写文件。无额外环境变量。退出 0 成功，非 0 为输入/复制/校验错误。

输出：`payload/` 独立解释器与依赖、完整模型、许可和逐文件摘要；`voice-runtime.zip`；每卷小于 2 GiB 的 `voice-runtime.zip.partNNN`；`msvc-applocal.zip` 应用本地 C++ 依赖附件；固定 Release 地址和摘要清单 `portable-runtime.json`。只复制模型来源清单内文件，排除缓存、环境文件、测试工程和目录联接；来源只读。

失败会留下不完整的新输出目录，不自动删除；定位后换新目录重新构建。回退时先核对绝对路径确属本次 `--output` 且无用户新文件，再手动删除该构建目录；来源不变。发布前在隔离目录实际安装、离线生成音频并检验摘要，再同步清单到 Skill，脚本普通 Git 提交，分卷上传对应 Release；不上传 payload 逐文件目录或历史测试。
