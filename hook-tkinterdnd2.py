# PyInstaller 钩子：把 tkinterdnd2 的 tkdnd 原生二进制（含 Windows 的
# win-x64 / win-x64-tcl9 等）一并收集进打包结果，使冻结后仍能 package require tkdnd。
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('tkinterdnd2')
