# -*- mode: python ; coding: utf-8 -*-
# ComicViewer v13 —— 窗口版（无控制台）
# 相比 v12：额外把 7-Zip 命令行 (7z.exe + 7z.dll) 一起打包，
# 使 rar / cbr 等格式无需本机安装 7-Zip 即可解压。

# 7-Zip 二进制（完整版 7z.exe + 7z.dll 即可解压 rar/zip/7z 等）
SEVENZIP_DIR = r'C:\Program Files\7-Zip'

a = Analysis(
    ['comic_viewer.py'],
    pathex=[],
    binaries=[
        (SEVENZIP_DIR + r'\7z.exe', '.'),
        (SEVENZIP_DIR + r'\7z.dll', '.'),
    ],
    datas=[],
    hiddenimports=['tkinterdnd2', 'PIL._imagingtk'],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ComicViewer_v13.10',
    icon='comic_viewer.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
