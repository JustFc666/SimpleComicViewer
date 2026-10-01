#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 mock 的 tkinter 驱动 ComicViewer 控制器逻辑，捕获编译期无法发现的
运行期错误（拼写、未定义方法、属性等）。不依赖真实显示。
"""
import io
import os
import sys
import types
import tempfile
import shutil as sh

# ---------- 构造 mock tkinter ----------
class MWidget:
    def __init__(self, *a, **k):
        self._v = ''
        self.children = []

    def get(self, *a, **k):
        return self._v

    def set(self, v, *a, **k):
        self._v = v
        return None

    def __getattr__(self, n):
        if n.startswith('__'):
            raise AttributeError(n)

        def f(*a, **k):
            if n in ('winfo_width',):
                return 800
            if n in ('winfo_height',):
                return 600
            if n in ('winfo_pointerxy',):
                return (0, 0)
            if n == 'after':
                return 1  # 不真正调度，避免回调循环
            if n == 'after_cancel':
                return None
            if n == 'focus_get':
                return None
            return None
        return f


def _make_mod(ns):
    m = types.ModuleType(ns)
    return m


tk_mod = _make_mod('tkinter')
ttk_mod = _make_mod('tkinter.ttk')
fd_mod = _make_mod('tkinter.filedialog')
mb_mod = _make_mod('tkinter.messagebox')
sd_mod = _make_mod('tkinter.simpledialog')
it_mod = _make_mod('PIL.ImageTk')

for name in ('Tk', 'Toplevel', 'Frame', 'Canvas', 'Label', 'Menu', 'StringVar', 'Entry'):
    setattr(tk_mod, name, MWidget)
ttk_mod.Frame = ttk_mod.Button = ttk_mod.Combobox = ttk_mod.Scrollbar = \
    ttk_mod.Checkbutton = ttk_mod.Separator = ttk_mod.Label = ttk_mod.Entry = MWidget
fd_mod.askopenfilename = lambda *a, **k: None
fd_mod.askdirectory = lambda *a, **k: None
mb_mod.showerror = mb_mod.showinfo = lambda *a, **k: None
sd_mod.askinteger = lambda *a, **k: None
it_mod.PhotoImage = MWidget

tk_mod.ttk = ttk_mod
tk_mod.filedialog = fd_mod
tk_mod.messagebox = mb_mod
tk_mod.simpledialog = sd_mod

sys.modules['tkinter'] = tk_mod
sys.modules['tkinter.ttk'] = ttk_mod
sys.modules['tkinter.filedialog'] = fd_mod
sys.modules['tkinter.messagebox'] = mb_mod
sys.modules['tkinter.simpledialog'] = sd_mod
sys.modules['PIL.ImageTk'] = it_mod

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comic_viewer as cv
from PIL import Image


def make_png(path, w, h, color):
    Image.new('RGB', (w, h), color).save(path, 'PNG')


def make_gif(path, frames=3):
    imgs = [Image.new('RGB', (60, 60), (i * 40 % 255, 0, 0)) for i in range(frames)]
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=120, loop=0, format='GIF')


def main():
    tmp = tempfile.mkdtemp(prefix='cvgui_')
    try:
        d = os.path.join(tmp, 'manga')
        os.makedirs(d)
        for i in range(5):
            make_png(os.path.join(d, 'page%02d.png' % (i + 1)), 200, 300, (i * 30, 50, 80))
        make_gif(os.path.join(d, 'anim.gif'), 3)

        root = tk_mod.Tk()
        app = cv.ComicViewer(root)
        print('[OK] ComicViewer.__init__ 无异常')

        app.open_path(d)
        print('[OK] open_path(文件夹) -> 图片数=%d' % len(app.archive.names()))

        app.render()
        print('[OK] render() 单页')

        app.next_page(); app.prev_page(); app.next_page()
        print('[OK] 翻页 下一/上一/下一')

        app._set_mode('double')
        app.render()
        print('[OK] 双页 render, 显示=%s' % app._displayed)

        app._set_dir('rtl')
        app.render()
        print('[OK] 从右到左 render, 顺序=%s' % app._displayed)

        app._set_mode('single')
        app._set_dir('ltr')

        app._set_zoom('fith')
        app.render()
        print('[OK] 适应高度 render')

        app.zoom_in(); app.zoom_out()
        print('[OK] 放大/缩小 手动 zoom=%.2f' % app.zoom)

        app.jump_var.set('3')
        app.jump_page()
        print('[OK] 跳转 -> index=%d' % app.index)

        app._set_tbpos('left')
        print('[OK] 工具栏切到左侧')

        app._set_menubar_pos('left')
        app._popup_menu(app.file_menu)
        app._popup_menu(app.view_menu)
        app._popup_menu(app.help_menu)
        print('[OK] 菜单栏切到左侧 + 弹出菜单 无异常')
        app._set_menubar_pos('top')

        app._toggle_statusbar()
        print('[OK] 信息栏显示切换 -> status_visible=%s' % app.status_visible)
        app._toggle_statusbar()

        # 拖拽打开：路径解析逻辑（Win32 解析部分仅 Windows 生效）
        app._open_dropped_paths([d, 'not_exist_xyz'])
        print('[OK] 拖拽路径解析并打开首个有效路径 -> 图片数=%d' % len(app.archive.names()))

        app.toggle_fullscreen()
        app.toggle_fullscreen()
        print('[OK] 全屏切换往返')

        # GIF 动画调度不抛异常
        app.open_path(d)
        names = app.archive.names()
        gif = [n for n in names if n.lower().endswith('.gif')][0]
        app.index = names.index(gif)
        app._set_mode('single')
        app.render()
        # 手动推进一帧（模拟定时器）
        for nm in app._anim_names:
            entry = app.load_page(nm)
            app._gif_frame[nm] = (app._gif_frame.get(nm, 0) + 1) % len(entry['frames'])
        app._draw()
        print('[OK] GIF 帧推进与重绘 无异常')

        app._save_settings()
        print('[OK] 设置持久化 -> %s' % os.path.basename(app._settings_path))

        print('\nGUI 控制器逻辑测试全部通过 ✅')
    finally:
        sh.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
