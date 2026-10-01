# -*- mode: python ; coding: utf-8 -*-
# ComicViewer v13 —— 文件夹模式（onedir，解压即运行，无需安装）
# 与窗口版区别：用 COLLECT 把依赖收集到同目录文件夹，而非打包进单个 exe。
# 输出：[项目]/dist/ComicViewer_v13.10/ —— 文件夹内 ComicViewer_v13.10.exe 即主程序。

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
    exclude_binaries=True,   # 二进制放到外层文件夹（onedir）
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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ComicViewer_v13.10',
)
