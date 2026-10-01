#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Headless 逻辑测试：不依赖图形界面，验证压缩文档读取与自然排序。"""
import io
import os
import sys
import zipfile
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comic_viewer as cv
from PIL import Image

def make_png(path, w, h, color):
    im = Image.new('RGB', (w, h), color)
    im.save(path, 'PNG')

def test_natural_sort():
    names = ['page10.png', 'page2.png', 'page1.png', 'page20.png', 'cover.png']
    names.sort(key=cv.natural_sort_key)
    assert names == ['cover.png', 'page1.png', 'page2.png', 'page10.png', 'page20.png'], names
    print('[OK] natural_sort_key')

def test_zip(tmp):
    d = os.path.join(tmp, 'images')
    os.makedirs(d)
    make_png(os.path.join(d, 'page2.png'), 200, 300, (200, 50, 50))
    make_png(os.path.join(d, 'page1.png'), 200, 300, (50, 200, 50))
    make_png(os.path.join(d, 'page10.png'), 200, 300, (50, 50, 200))
    zpath = os.path.join(tmp, 'comic.cbz')
    with zipfile.ZipFile(zpath, 'w') as z:
        for f in sorted(os.listdir(d)):
            z.write(os.path.join(d, f), f)
    arch = cv.open_archive(zpath)
    names = arch.names()
    assert names == ['page1.png', 'page2.png', 'page10.png'], names
    data = arch.read(names[0])
    im = Image.open(io.BytesIO(data))
    assert im.size == (200, 300)
    arch.close()
    print('[OK] zip/cbz read + sort + image decode')

def test_dir(tmp):
    d = os.path.join(tmp, 'folder')
    os.makedirs(d)
    make_png(os.path.join(d, 'img3.jpg'), 100, 100, (10, 10, 10))
    make_png(os.path.join(d, 'img1.jpg'), 100, 100, (10, 10, 10))
    arch = cv.open_archive(d)
    assert arch.names() == ['img1.jpg', 'img3.jpg'], arch.names()
    arch.close()
    print('[OK] folder read')

def test_find_7z():
    # 仅验证函数不抛异常（找不到返回 None 也可接受）
    r = cv.find_7z()
    print('[OK] find_7z ->', r)

def test_7z(tmp):
    if not cv.HAS_PY7ZR:
        print('[SKIP] py7zr 未安装，跳过 7z 测试')
        return
    d = os.path.join(tmp, 'im7')
    os.makedirs(d)
    make_png(os.path.join(d, 'p1.png'), 80, 80, (1, 2, 3))
    make_png(os.path.join(d, 'p2.png'), 80, 80, (4, 5, 6))
    zpath = os.path.join(tmp, 'comic.7z')
    import py7zr
    with py7zr.SevenZipFile(zpath, 'w') as z:
        z.writeall(d, arcname='')
    arch = cv.open_archive(zpath)
    names = arch.names()
    assert names == ['p1.png', 'p2.png'], names
    im = Image.open(io.BytesIO(arch.read(names[0])))
    assert im.size == (80, 80)
    arch.close()
    print('[OK] 7z read (py7zr)')

def main():
    tmp = tempfile.mkdtemp(prefix='cvtest_')
    try:
        test_natural_sort()
        test_zip(tmp)
        test_dir(tmp)
        test_7z(tmp)
        test_find_7z()
        print('\n全部逻辑测试通过 ✅')
    finally:
        import shutil as sh
        sh.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    main()
