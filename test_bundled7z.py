# -*- coding: utf-8 -*-
"""离线验证：模拟单文件 exe 运行时的内置 7z 解析与 open_archive 路由。
不创建任何 Tk 窗口，仅测试压缩包读取逻辑。
"""
import os
import sys
import shutil
import tempfile
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'comic_viewer.py')

# 导入 comic_viewer（导入期只 import tkinter，不创建窗口）
spec = importlib.util.spec_from_file_location('cv_test', SRC)
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)

tmp = tempfile.mkdtemp(prefix='cv7z_')
# 模拟 PyInstaller 单文件解压目录：内置 7z.exe + 7z.dll 同处一目录
shutil.copy(r'C:\Program Files\7-Zip\7z.exe', os.path.join(tmp, '7z.exe'))
shutil.copy(r'C:\Program Files\7-Zip\7z.dll', os.path.join(tmp, '7z.dll'))

# 关键：模拟 _MEIPASS，验证 find_7z 优先返回内置 7z
sys._MEIPASS = tmp  # noqa

print('TK_AVAILABLE   =', cv.TK_AVAILABLE)
print('HAS_PY7ZR      =', cv.HAS_PY7ZR)
print('find_7z()      =', cv.find_7z())
assert cv.find_7z() == os.path.join(tmp, '7z.exe'), '内置 7z 未被优先选中！'

# 构造测试 zip 与 7z（用内置 7z 生成，文件用图片扩展名以免被过滤）
za = cv.find_7z()
os.chdir(tmp)
open('p1.png', 'wb').write(b'page1-img')
open('p2.png', 'wb').write(b'page2-img')
os.system('"%s" a -tzip t.zip p1.png p2.png >nul 2>&1' % za)
os.system('"%s" a -t7z t.7z p1.png p2.png >nul 2>&1' % za)
assert os.path.isfile(os.path.join(tmp, 't.zip')), 't.zip 未生成'
assert os.path.isfile(os.path.join(tmp, 't.7z')), 't.7z 未生成'

# 测试 zip -> ZipArchive
z = cv.open_archive(os.path.join(tmp, 't.zip'))
print('zip names      =', z.names())
assert z.names() == ['p1.png', 'p2.png'], z.names()
assert b'page1-img' in z.read('p1.png')

# 测试 7z -> SevenZipPyArchive (py7zr 内置)
s = cv.open_archive(os.path.join(tmp, 't.7z'))
print('7z names       =', s.names())
assert s.names() == ['p1.png', 'p2.png']

# 测试 rar 通路 -> 内置 7z 命令行（核心：无需本机 7-Zip）
# 用 zip 代替 rar 验证 SevenZipCliArchive 在 find_7z 命中时能被正确驱动
rar_cls = cv.SevenZipCliArchive
inst = rar_cls(os.path.join(tmp, 't.zip'), za)
print('cli names      =', inst.names())
assert inst.names() == ['p1.png', 'p2.png']
assert b'page1-img' in inst.read('p1.png')

print('\nALL_HEADLESS_TESTS_PASSED')
shutil.rmtree(tmp, ignore_errors=True)
