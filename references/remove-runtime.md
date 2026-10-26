# remove-runtime.ps1 操作手册

用途：回退本 Skill 安装的固定版本配音包。Windows PowerShell 5.1，无环境变量要求。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\remove-runtime.ps1 -DryRun
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\remove-runtime.ps1
```

唯一参数 `-DryRun`：只展示待删除路径；默认执行删除。退出 0 成功或目标不存在，非 0 表示归属/安全检查失败或删除失败。无收据、收据不符或目录联接时停止。只操作 `.runtime/<清单版本>/`，不修改全局环境、原项目、其他版本或暂存目录。

删除的是可重新下载的安装副本；恢复方法是重新执行[安装脚本](install-runtime.md)。若被占用，停止该副本配音进程后重试。未完成安装的暂存目录无收据，应人工确认报错中的完整路径再清理，不扩大到项目。
