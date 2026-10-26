# install-runtime.ps1 操作手册

用途：把同仓库 Release 固定版本配音包安装到 Skill 下 `.runtime/<runtime_id>/`。支持 Windows 10/11 x64、Windows PowerShell 5.1，无需管理员、全局 Python、pip、CUDA。建议 16 GiB 以上内存，CPU 生成速度取决于机器。首次需下载数 GiB，临时空间由脚本预检，安装后可离线配音。

在实际 Skill 目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-runtime.ps1 -DryRun
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-runtime.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-runtime.ps1 -CheckOnly
```

参数：`-BundleDirectory <目录>` 从本地读取所有 `voice-runtime.zip.partNNN` 及 `msvc-applocal.zip`，完全不联网；不提供时从 `references/portable-runtime.json` 固定的 GitHub Release 地址下载。`-DryRun` 仅校验输入、空间及目标，不下载、不安装；`-CheckOnly` 仅检查已安装运行包，不自动下载。`-ResumeStage <绝对路径>` 仅用于完整解压后检查失败：必须是该 Skill 下安装器生成的 `.runtime/.install-<编号>`，重新验证整包、逐文件摘要与 C++ 附件后继续，不重复下载或解压；不完整解压不能跳过重装。没有自定义环境变量要求，不读取 API 密钥或账户文件。退出 0 成功，非 0 失败。

离线迁移：复制整个已安装 Skill（包含被 Git 忽略的 `.runtime/`）；或者在新电脑先安装 Skill，将同一 Release 的全部分卷和 `msvc-applocal.zip` 放在一个目录后执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-runtime.ps1 -BundleDirectory 'E:\AI日报运行包'
```

先核对分卷大小和 SHA256，再合并 ZIP、核对整包 SHA256、拒绝越界路径、检查解压文件尺寸，再核验并放入单独固定摘要的应用本地 C++ 依赖，最后实际导入模型依赖。C++ DLL 仅放在私有 Python 旁，不安装全局运行库。全部通过后才把新目录提交到 `.runtime/<runtime_id>` 并写入 `install-receipt.json`。不修改 PATH、注册表、系统 Python、原项目环境或参考音频；不覆盖已有运行包。已安装时检查收据与本地配音入口。

失败示例：分卷缺失/损坏、GitHub 无法访问、空间不足或导入失败。报错后停止；若已完成解压，可更新修复后的脚本再用 `-ResumeStage` 恢复，校验失败仍停止。目标未提交时仅留下 `.runtime/.install-<编号>/`；不改用原作者电脑绝对路径，也不自动反复下载。确认不再使用后可手动删除报错列出的暂存目录。校验失败应重新获取分卷，不跳过摘要。

回退：用[remove-runtime.ps1](remove-runtime.md)先 `-DryRun` 后正式移除。只删除收据确认归属的固定运行包，不触碰原项目、其他版本、参考素材和当期产物；随后可重新安装。用户文件不要存入 `.runtime/`。

分发：规则、脚本及参考进 Git；大文件是 GitHub Release 附件，不用 Git LFS 或付费推理。只下载源码 ZIP/克隆仓库不会同时取得模型，首次运行入口会自动取齐。公开仓库可匿名下载；日后改成私有仓库时先以授权方式下载附件，再用本地目录模式，不把令牌写入配置。
