#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comic Archive Viewer —— 漫画压缩文档浏览器 (Windows)
====================================================
支持直接浏览 rar / zip / 7z / cbz / cbr / cb7 等压缩包，以及普通图片文件夹。

功能：
  * 单页 / 双页显示，可选 从左到右 或 从右到左 阅读方向
  * 缩放：手动调整 / 自动适应宽度 / 自动适应高度
  * 空格显示下一页；也可翻到上一页
  * GIF 自动播放（动画）
  * 跳转到指定页面
  * 全屏显示
  * 文件 / 视图 / 帮助 功能全部集成到工具栏（无独立菜单栏）
  * 工具栏可在“上方 / 左侧”间切换（在浏览页面右键选取）
  * 信息栏固定在底部，支持右键菜单隐藏/再次显示
  * 支持将漫画压缩文件直接拖入浏览页面打开
  * 内置 7-Zip 命令行（7z.exe + 7z.dll），无需本机安装即可解压 rar 等格式
  * 也可自动检测系统中的 7-Zip 作为补充

依赖（源码运行所需；打包后的 exe 均已内置）：
  * Python 3.8+（tkinter 随官方 Windows 版 Python 自带）
  * Pillow        -> pip install Pillow
  * py7zr         -> pip install py7zr   处理 .7z / .cb7
  * 7-Zip         -> 已随 exe 打包（7z.exe + 7z.dll），用于 rar / cbr

运行：
  python comic_viewer.py [压缩文件路径]
"""

import io
import os
import re
import sys
import shutil
import zipfile
import subprocess
import configparser
import csv
import datetime
from pathlib import Path

try:
    import py7zr
    HAS_PY7ZR = True
except Exception:
    HAS_PY7ZR = False

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    from PIL import ImageTk
    TK_AVAILABLE = True
except Exception:
    # 无图形环境（如部分精简 Python）时，仅影响 GUI，不影响压缩包读取逻辑
    tk = ttk = filedialog = messagebox = simpledialog = ImageTk = None
    TK_AVAILABLE = False

# 文件拖放：业界唯一可靠的方案是 tkinterdnd2（TkDnD Tcl/Tk 扩展的 Python 封装）。
# tkinter 原生不支持操作系统级文件拖放；ctypes 子类化 / WM_DROPFILES 覆盖窗口方案
# 在 Windows 上会导致闪退或“禁止放置”光标，已彻底弃用。
DND_FILES = None
TkinterDnD = None
DND_AVAILABLE = False
if TK_AVAILABLE:
    try:
        from tkinterdnd2 import DND_FILES as _DND_FILES, TkinterDnD
        DND_FILES = _DND_FILES
        DND_AVAILABLE = True
    except Exception:
        DND_FILES = None
        TkinterDnD = None
        DND_AVAILABLE = False

from PIL import Image, ImageSequence


# ---------------------------------------------------------------------------
# 崩溃日志：把“静默闪退”变成可见的弹框 + 落盘日志，便于定位（冻结 exe 无 stderr）
# ---------------------------------------------------------------------------
def _crash_log_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'crash.log')


def _log_crash(where, text):
    try:
        with open(_crash_log_path(), 'a', encoding='utf-8') as fh:
            fh.write('[%s] %s\n%s\n%s\n' % (
                where, _now_str(), text, '-' * 60))
    except Exception:
        pass


def _now_str():
    try:
        return __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''


def _install_exception_logging(root):
    """重写 Tk 的回调异常钩子 + 进程级 excepthook，让任何未捕获异常都弹框并落盘。"""
    import traceback as _tb

    def handler(exc, val, tb):
        text = ''.join(_tb.format_exception(exc, val, tb))
        _log_crash('report_callback_exception', text)
        try:
            messagebox.showerror(
                '程序异常',
                '发生未捕获的异常（已记录到 crash.log）：\n\n' + text[:3000])
        except Exception:
            pass

    try:
        root.report_callback_exception = handler
    except Exception:
        pass

    def excepthook(exc, val, tb):
        text = ''.join(_tb.format_exception(exc, val, tb))
        _log_crash('sys.excepthook', text)
        try:
            messagebox.showerror(
                '程序异常',
                '发生未捕获的异常（已记录到 crash.log）：\n\n' + text[:3000])
        except Exception:
            pass

    sys.excepthook = excepthook


IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif')
CB_EXT_MAP = {'.cbz': '.zip', '.cbr': '.rar', '.cb7': '.7z', '.cbt': '.tar'}

# 说明：文件拖放已改用 tkinterdnd2（见上方 DND_AVAILABLE）。
# 原 ctypes 子类化 / WM_DROPFILES 覆盖窗口方案的相关常量与结构已移除。

# ---------------------------------------------------------------------------
# 自然排序：让 page2 < page10
# ---------------------------------------------------------------------------
def natural_sort_key(s):
    """自然排序键：数字部分零填充为定长字符串，避免 int/str 混合比较崩溃。"""
    return [t.zfill(10) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', s) if t]


# ---------------------------------------------------------------------------
# 7-Zip 自动检测
# ---------------------------------------------------------------------------
def find_7z():
    """优先返回随包内置的 7z，其次本机已安装的 7-Zip。

    打包为单文件 exe 时，7z.exe / 7z.dll 会被 PyInstaller 解压到
    sys._MEIPASS 临时目录；与 exe 同目录手动放置 7z.exe 亦可。
    """
    # 1) 单文件 exe 解压后的临时目录（7z.exe 与 7z.dll 同在此处）
    base = getattr(sys, '_MEIPASS', None)
    if base:
        cand = os.path.join(base, '7z.exe')
        if os.path.isfile(cand):
            return cand
    # 1b) onedir（文件夹模式）依赖收集在 _internal 子目录
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        cand = os.path.join(exe_dir, '_internal', '7z.exe')
        if os.path.isfile(cand):
            return cand
    except Exception:
        pass
    # 2) 与可执行文件同目录（便于手动放置 / 非打包场景）
    try:
        local = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                             '7z.exe')
        if os.path.isfile(local):
            return local
    except Exception:
        pass
    # 3) 系统 PATH 中的 7z / 7za / 7zr
    for c in ('7z', '7za', '7zr'):
        p = shutil.which(c)
        if p:
            return p
    # 4) 常见安装位置
    for cand in (
        r'C:\Program Files\7-Zip\7z.exe',
        r'C:\Program Files (x86)\7-Zip\7z.exe',
        r'C:\Program Files\7-Zip Extra\7za.exe',
        r'C:\Users\%s\AppData\Local\Programs\7-Zip\7z.exe' % os.environ.get('USERNAME', ''),
    ):
        if os.path.isfile(cand):
            return cand
    return None


# ---------------------------------------------------------------------------
# 统一压缩文档接口
# ---------------------------------------------------------------------------
class Archive:
    def __init__(self, path):
        self.path = path
        self._open()

    def _open(self):
        raise NotImplementedError

    def names(self):
        raise NotImplementedError

    def read(self, name):
        raise NotImplementedError

    def close(self):
        pass


class DirArchive(Archive):
    def _open(self):
        self.dir = self.path

    def names(self):
        items = [f for f in os.listdir(self.dir)
                 if f.lower().endswith(IMAGE_EXTS)
                 and os.path.isfile(os.path.join(self.dir, f))]
        return sorted(items, key=natural_sort_key)

    def read(self, name):
        with open(os.path.join(self.dir, name), 'rb') as fh:
            return fh.read()


class SingleImageArchive(Archive):
    """把单张图片当作只有一页的“压缩包”打开，便于直接浏览图片文件。"""

    def _open(self):
        self._name = os.path.basename(self.path)

    def names(self):
        return [self._name]

    def read(self, name):
        with open(self.path, 'rb') as fh:
            return fh.read()


class ZipArchive(Archive):
    def _open(self):
        self.zf = zipfile.ZipFile(self.path, 'r')

    def names(self):
        items = [n for n in self.zf.namelist()
                 if n.lower().endswith(IMAGE_EXTS) and not n.endswith('/')]
        return sorted(items, key=natural_sort_key)

    def read(self, name):
        return self.zf.read(name)

    def close(self):
        try:
            self.zf.close()
        except Exception:
            pass


class SevenZipPyArchive(Archive):
    def _open(self):
        self.szf = py7zr.SevenZipFile(self.path, 'r')

    def names(self):
        items = [n for n in self.szf.getnames()
                 if n.lower().endswith(IMAGE_EXTS) and not n.endswith('/')]
        return sorted(items, key=natural_sort_key)

    def read(self, name):
        data = self.szf.read(targets=[name])
        buf = data[name]
        if hasattr(buf, 'getvalue'):
            return buf.getvalue()
        return buf

    def close(self):
        try:
            self.szf.close()
        except Exception:
            pass


class SevenZipCliArchive(Archive):
    """借助 7-Zip 命令行，统一处理 zip/7z/rar/tar 等多种格式。"""

    def __init__(self, path, exe):
        self.exe = exe
        super().__init__(path)

    def _open(self):
        out = subprocess.run([self.exe, 'l', '-slt', self.path],
                             capture_output=True, text=True, errors='ignore')
        names = []
        for line in out.stdout.splitlines():
            if line.startswith('Path = '):
                p = line[len('Path = '):].strip()
                if p.lower().endswith(IMAGE_EXTS):
                    names.append(p)
        self._names = sorted(names, key=natural_sort_key)

    def names(self):
        return self._names

    def read(self, name):
        proc = subprocess.run([self.exe, 'e', '-so', '-y', self.path, name],
                              capture_output=True)
        return proc.stdout


def open_archive(path):
    """根据路径打开一个 Archive 对象。所有格式均可在无外部安装时工作。"""
    if os.path.isdir(path):
        return DirArchive(path)

    ext = os.path.splitext(path)[1].lower()
    # 单张图片：当作只有一页的“压缩包”直接打开
    if ext in IMAGE_EXTS:
        return SingleImageArchive(path)
    ext = CB_EXT_MAP.get(ext, ext)

    # zip / cbz：Python 内置 zipfile，零依赖
    if ext == '.zip':
        return ZipArchive(path)
    # 7z / cb7：随包内置的 py7zr
    if ext == '.7z':
        if HAS_PY7ZR:
            return SevenZipPyArchive(path)
        exe = find_7z()
        if exe:
            return SevenZipCliArchive(path, exe)
        raise RuntimeError('打开 .7z 需要 py7zr（pip install py7zr）。')
    # rar / cbr：使用内置（或系统）7-Zip 命令行
    if ext == '.rar':
        exe = find_7z()
        if exe:
            return SevenZipCliArchive(path, exe)
        raise RuntimeError('打开 .rar 需要 7-Zip（程序已内置，请勿删除 7z.exe）。')
    raise RuntimeError('不支持的压缩格式：%s' % ext)


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------
class ComicViewer:
    MODES = ['单页', '双页']
    DIRS = ['从左到右', '从右到左']
    ZOOMS = ['适应宽度', '适应高度', '手动']
    ROTATIONS = ['不旋转', '逆时针90°', '旋转180°', '顺时针90°']
    VERSION = 'v13.10'

    def __init__(self, root):
        self.root = root
        self.root.title('漫画压缩文档浏览器')
        self.root.geometry('1100x800')

        # 状态
        self.archive = None
        self.archive_path = None
        self.index = 0
        self.mode = 'single'        # single / double
        self.direction = 'ltr'      # ltr / rtl
        self.zoom_mode = 'fitw'     # fitw / fith / manual
        self.zoom = 1.0
        self.toolbar_pos = 'top'    # top / left
        self.status_visible = True  # 信息栏是否显示（右键可切换）
        self.fullscreen = False
        self.rotation = 0           # 当前图片旋转角度（0 / 90 / 180 / -90）

        self.img_cache = {}
        self._displayed = []
        self._gif_frame = {}
        self._anim_names = []
        self._anim_job = None
        self._photo_refs = []
        self._resize_job = None
        self._vbar_shown = None
        self._hbar_shown = None
        self._settings_path = self._settings_file()

        self._load_settings()
        self._history = self._load_history()  # 阅读历史（CSV 数据库，内存缓存）
        self._build_ui()
        self._sync_controls()
        self._bind_keys()
        self._enable_drag_drop()
        self.layout()
        self._update_zoom_label()
        self._render_empty('请打开漫画压缩包（zip / 7z / rar / cbz / cbr / cb7），或直接拖入图片文件 / 压缩包，也可以打开图片文件夹。')

    # ---- 设置持久化 ----
    def _settings_file(self):
        # 冻结成 exe 后脚本位于临时目录，配置应落在用户可写位置
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
        d = os.path.join(base, 'ComicViewer')
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            d = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(d, 'settings.ini')

    # ---- 阅读历史（CSV 数据库：路径 / 文件名 / 最后阅读页数 / 最后阅读时间）----
    def _history_path(self):
        # 落地在“打包文件夹”（与 exe 同目录）：onedir 模式为 dist/ComicViewer_v13.10/，
        # onefile 模式为 dist/；源码运行或无写入权限时回退到 %APPDATA%/ComicViewer/
        if getattr(sys, 'frozen', False):
            d = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base = os.environ.get('APPDATA') or os.path.expanduser('~')
            d = os.path.join(base, 'ComicViewer')
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            d = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(d, 'reading_history.csv')

    def _load_history(self):
        p = self._history_path()
        hist = {}
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8', newline='') as f:
                    for row in csv.DictReader(f):
                        path = (row.get('path') or '').strip()
                        if not path:
                            continue
                        try:
                            lp = int(row.get('last_page') or 1)
                        except Exception:
                            lp = 1
                        hist[path] = {
                            'filename': (row.get('filename') or '').strip() or os.path.basename(path),
                            'last_page': lp,
                            'last_read': (row.get('last_read_time') or '').strip(),
                        }
            except Exception:
                pass
        return hist

    def _save_history(self):
        # 将内存中的 self._history 写回 CSV（插入顺序=阅读先后，末尾为最近阅读）
        p = self._history_path()
        try:
            with open(p, 'w', encoding='utf-8', newline='') as f:
                w = csv.writer(f)
                w.writerow(['path', 'filename', 'last_page', 'last_read_time'])
                for path, v in self._history.items():
                    w.writerow([path, v.get('filename', ''),
                                v.get('last_page', 1), v.get('last_read', '')])
        except Exception:
            pass

    def _record_open(self, path):
        # 打开漫画时登记：新条目才新增（不覆盖已有进度）；已存在则移到末尾标记为最近
        if not path:
            return
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if path in self._history:
            self._history[path]['last_read'] = now
            self._history[path] = self._history.pop(path)  # 移到末尾=最近阅读
            return
        self._history[path] = {'filename': os.path.basename(path),
                               'last_page': 1, 'last_read': now}
        self._save_history()

    def _record_page(self):
        # 翻页时记录当前阅读进度（覆盖式 upsert，并移到末尾=最近），同时刷新最后阅读时间
        if not self.archive_path:
            return
        p = self.archive_path
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._history.pop(p, None)  # 先移除再赋值，确保移到末尾（最近阅读）
        self._history[p] = {
            'filename': os.path.basename(p),
            'last_page': self.index + 1,
            'last_read': now,
        }
        self._save_history()

    def _open_recent(self, path):
        # 从“阅读记录”打开：找不到文件则提示“文件已删除”；否则打开并跳到最后阅读页
        if not os.path.isfile(path):
            messagebox.showwarning('文件已删除',
                                   '找不到该漫画文件，可能已被删除或移动：\n%s' % path)
            return
        self.open_path(path)
        if not self.archive:
            return
        info = self._history.get(path)
        if info:
            n = len(self.archive.names())
            self.index = max(0, min(info['last_page'] - 1, n - 1))
            self.render()
            self._record_page()

    def _open_history_dialog(self):
        """阅读记录对话框（自定义网格 + 深灰表格线 + 可拖拽列宽）：双击打开并跳末页；
        Shift / Ctrl 多选后删除选中或全部。内容充满窗口、单行不换行、列宽可手动调整。无提示音。"""
        dlg = tk.Toplevel(self.root)
        dlg.title('阅读记录')
        self.root.update_idletasks()           # 先刷新主窗口布局，确保拿到真实尺寸
        try:
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            w = max(int(rw * 0.6), 640)
            h = max(int(rh * 0.6), 400)
        except Exception:
            w, h = 720, 480
        dlg.geometry('%dx%d' % (w, h))
        dlg.transient(self.root)
        dlg.grab_set()

        # 滚动画布 + 垂直/水平滚动条
        outer = ttk.Frame(dlg)
        outer.pack(fill='both', expand=True)
        canvas = tk.Canvas(outer, bg='white', highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        hsb = ttk.Scrollbar(outer, orient='horizontal', command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side='bottom', fill='x')
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # 网格框架：底色 = 深灰（作为表格线颜色），单元格之间留 1px 间隙露出此色
        grid = tk.Frame(canvas, bg='#555555')
        cwin = canvas.create_window((0, 0), window=grid, anchor='nw')

        HEADER_BG = '#d9d9d9'
        NORMAL_BG = '#ffffff'
        SEL_BG = '#cfe8ff'
        # 阅读记录表头与内容统一使用 YaHei 9（与 tk.Label 默认一致）
        DLG_FONT = ('Microsoft YaHei UI', 9)
        cols = [('文件名', 'w'), ('阅读时间', 'center'),
                ('页码', 'center'), ('路径', 'w')]
        ratios = [0.40, 0.18, 0.08, 0.34]      # 默认列宽比例（充满窗口）

        self._hd_paths = []
        self._hd_cells = []
        self._hd_sel = set()
        self._hd_anchor = None
        self._hd_col_w = []          # 各列像素宽（手动调整后持久）
        self._hd_user_resized = False

        def layout_cols():
            """分配各列像素宽：默认按比例充满；手动拖拽后保持用户布局。"""
            cw = canvas.winfo_width()
            if cw < 50:
                return
            if not self._hd_col_w or not self._hd_user_resized:
                self._hd_col_w = [max(int(cw * r), 50) for r in ratios]
            total = sum(self._hd_col_w)
            for ci, wv in enumerate(self._hd_col_w):
                grid.grid_columnconfigure(ci, minsize=wv, weight=0)
            canvas.itemconfigure(cwin, width=total)

        def set_bg(idx, bg):
            for lb in self._hd_cells[idx]:
                lb.configure(bg=bg)

        def refresh_sel():
            for i in range(len(self._hd_cells)):
                set_bg(i, SEL_BG if i in self._hd_sel else NORMAL_BG)

        def on_click(idx, event):
            ctrl = bool(event.state & 0x4)
            shift = bool(event.state & 0x1)
            if ctrl:
                self._hd_sel.discard(idx) if idx in self._hd_sel else self._hd_sel.add(idx)
                self._hd_anchor = idx
            elif shift and self._hd_anchor is not None:
                lo, hi = (self._hd_anchor, idx) if self._hd_anchor <= idx else (idx, self._hd_anchor)
                self._hd_sel = set(range(lo, hi + 1))
            else:
                self._hd_sel = {idx}
                self._hd_anchor = idx
            refresh_sel()

        def on_open(idx):
            path = self._hd_paths[idx]
            dlg.destroy()
            self._open_recent(path)

        def build_rows():
            for row in self._hd_cells:
                for c in row:
                    c.destroy()
            self._hd_cells = []
            self._hd_paths = []
            self._hd_sel = set()
            self._hd_anchor = None
            for ri, (p, v) in enumerate(reversed(list(self._history.items()))):
                vals = [v.get('filename', ''), v.get('last_read', ''),
                        str(v.get('last_page', 1)), p]
                row = []
                for ci, (_, anc) in enumerate(cols):
                    lb = tk.Label(grid, text=vals[ci], bg=NORMAL_BG,
                                  anchor=anc, relief='flat', borderwidth=0,
                                  font=DLG_FONT, padx=4, pady=2)
                    lb.grid(row=ri + 1, column=ci, sticky='nsew', padx=(0, 1), pady=(0, 1))
                    lb.bind('<Button-1>', lambda e, i=ri: on_click(i, e))
                    lb.bind('<Double-1>', lambda e, i=ri: on_open(i))
                    row.append(lb)
                self._hd_cells.append(row)
                self._hd_paths.append(p)
            refresh_sel()
            dlg.update_idletasks()
            layout_cols()
            canvas.configure(scrollregion=canvas.bbox('all'))

        def del_selected():
            if not self._hd_sel:
                messagebox.showinfo('提示', '请先选中要删除的记录（支持 Shift / Ctrl 多选）。')
                return
            if not messagebox.askyesno('确认', '确定删除选中的 %d 条记录？' % len(self._hd_sel)):
                return
            for idx in sorted(self._hd_sel, reverse=True):
                self._history.pop(self._hd_paths[idx], None)
            self._save_history()
            build_rows()

        def del_all():
            if not self._history:
                return
            if not messagebox.askyesno('确认', '确定删除全部阅读记录？此操作不可撤销。'):
                return
            self._history.clear()
            self._save_history()
            build_rows()

        # 表头：每列一个 Frame，内含标题 + 右侧可拖拽分隔条（非末列）
        drag = {'ci': None, 'x0': 0, 'w0': 0, 'w1': 0}

        def start_drag(ci, ev):
            drag['ci'] = ci
            drag['x0'] = ev.x_root
            drag['w0'] = self._hd_col_w[ci]
            drag['w1'] = self._hd_col_w[ci + 1]
            self._hd_user_resized = True

        def do_drag(ci, ev):
            if drag['ci'] is None:
                return
            dx = ev.x_root - drag['x0']
            nw = max(50, drag['w0'] + dx)            # 新列宽
            give = nw - drag['w0']                   # 从相邻列借/还
            if drag['w1'] - give < 50:
                return
            self._hd_col_w[ci] = nw
            self._hd_col_w[ci + 1] = drag['w1'] - give
            layout_cols()
            canvas.configure(scrollregion=canvas.bbox('all'))

        for ci, (name, anc) in enumerate(cols):
            hdr = tk.Frame(grid, bg=HEADER_BG)
            tk.Label(hdr, text=name, bg=HEADER_BG, anchor='center',
                     font=DLG_FONT, padx=4, pady=3
                     ).pack(side='left', fill='both', expand=True)
            if ci < len(cols) - 1:
                sep = tk.Frame(hdr, width=4, bg='#888888', cursor='sb_h_double_arrow')
                sep.pack(side='right', fill='y')
                sep.bind('<ButtonPress-1>', lambda e, c=ci: start_drag(c, e))
                sep.bind('<B1-Motion>', lambda e, c=ci: do_drag(c, e))
            hdr.grid(row=0, column=ci, sticky='nsew', padx=(0, 1), pady=(0, 1))

        bf = ttk.Frame(dlg)
        bf.pack(side='bottom', fill='x', padx=8, pady=8)
        ttk.Button(bf, text='删除选中记录', command=del_selected).pack(side='left', padx=4)
        ttk.Button(bf, text='删除全部记录', command=del_all).pack(side='left', padx=4)
        ttk.Label(bf, text='双击记录可直接打开并从最后阅读页开始；拖动表头分隔条可调列宽').pack(side='left', padx=10)
        ttk.Button(bf, text='关闭', command=dlg.destroy).pack(side='right', padx=4)

        def _on_configure(e):
            layout_cols()
            canvas.configure(scrollregion=canvas.bbox('all'))
        canvas.bind('<Configure>', _on_configure)
        grid.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        build_rows()
        dlg.wait_window()

    def _load_settings(self):
        cp = configparser.ConfigParser()
        if not os.path.isfile(self._settings_path):
            return
        try:
            cp.read(self._settings_path, encoding='utf-8')
            s = cp['settings']
            self.mode = s.get('mode', self.mode)
            self.direction = s.get('direction', self.direction)
            self.zoom_mode = s.get('zoom_mode', self.zoom_mode)
            self.zoom = float(s.get('zoom', self.zoom))
            self.toolbar_pos = s.get('toolbar_pos', self.toolbar_pos)
            self.status_visible = s.getboolean('status_visible', self.status_visible)
        except Exception:
            pass

    def _save_settings(self):
        cp = configparser.ConfigParser()
        cp['settings'] = {
            'mode': self.mode, 'direction': self.direction,
            'zoom_mode': self.zoom_mode, 'zoom': str(self.zoom),
            'toolbar_pos': self.toolbar_pos,
            'status_visible': str(self.status_visible),
        }
        try:
            with open(self._settings_path, 'w', encoding='utf-8') as fh:
                cp.write(fh)
        except Exception:
            pass

    # ---- UI 构建 ----
    def _build_ui(self):
        # 已取消原生菜单栏：文件 / 视图 / 帮助 全部集成到工具栏；
        # 工具栏位置（顶部 / 左侧）在内容区右键菜单中选取。

        # 左侧面板容器（工具栏在左侧时统一放置于此）
        self.left_panel = ttk.Frame(self.root)

        # 工具栏
        self.toolbar = ttk.Frame(self.root)
        self._tb_widgets = []
        self._seps = []
        # 下拉框文字居中样式（Windows 只读 Combobox 的显示文本靠 justify 控制）
        try:
            _combo_style = ttk.Style()
            _combo_style.configure('Center.TCombobox', justify='center')
        except Exception:
            pass

        def btn(text, cmd, tooltip=None):
            # 不指定 width：让按钮按文字内容自适应，避免中文标签(字宽≈2字符)被按字符数截断
            b = ttk.Button(self.toolbar, text=text, command=cmd)
            if tooltip:
                self._tooltip(b, tooltip)
            self._tb_widgets.append(b)
            return b

        def sep():
            s = ttk.Separator(self.toolbar, orient='vertical')
            self._seps.append(s)
            self._tb_widgets.append(s)
            return s

        def combo(values, cb):
            c = ttk.Combobox(self.toolbar, values=values, state='readonly',
                             width=10, style='Center.TCombobox')
            c.bind('<<ComboboxSelected>>', cb)
            self._tb_widgets.append(c)
            return c

        # ---- 文件（原“文件”菜单项）----
        btn('打开压缩文件', self.open_file, '打开漫画压缩包或图片文件')
        btn('打开文件夹', self.open_folder, '打开图片文件夹')
        btn('退出', self.root.quit, '退出程序')
        sep()
        # ---- 视图（原“视图”菜单项）----
        self.mode_cb = combo(self.MODES, lambda e: self._set_mode('double' if self.mode_cb.get() == '双页' else 'single'))
        self.dir_cb = combo(self.DIRS, lambda e: self._set_dir('rtl' if self.dir_cb.get() == '从右到左' else 'ltr'))
        sep()
        self.zoom_cb = combo(self.ZOOMS, lambda e: self._set_zoom({'适应宽度': 'fitw', '适应高度': 'fith', '手动': 'manual'}[self.zoom_cb.get()]))
        btn('缩小', self.zoom_out)
        btn('放大', self.zoom_in)
        self.rot_cb = combo(self.ROTATIONS, self._on_rotate)
        self.rot_cb.set('不旋转')
        self._tooltip(self.rot_cb, '旋转当前图片（不旋转 / 逆时针90° / 旋转180° / 顺时针90°）')
        sep()
        btn('上一页', self.prev_page)
        btn('下一页', self.next_page)
        self.jump_var = tk.StringVar()
        self.jump_entry = ttk.Entry(self.toolbar, textvariable=self.jump_var, width=5)
        self.jump_entry.bind('<Return>', lambda e: self.jump_page())
        self._tb_widgets.append(self.jump_entry)
        btn('跳转', self.jump_page)
        sep()
        btn('全屏', self.toggle_fullscreen)
        btn('信息栏', self._toggle_statusbar, '显示 / 隐藏 信息栏')
        sep()
        btn('阅读记录', self._open_history_dialog, '查看 / 管理 已读漫画阅读记录')
        btn('帮助', self.show_help)
        # 页码信息（顶部工具栏时居右，左侧工具栏时居底；由 _pack_toolbar_widgets 负责摆放）
        self.page_label = ttk.Label(self.toolbar, text='0 / 0', anchor='e')
        # 放大倍率信息（随页码信息一同摆放：顶部在页码左侧，左侧在页码上方；由 _pack_toolbar_widgets 负责摆放）
        self.zoom_label = ttk.Label(self.toolbar, text='100%', anchor='e')
        self._tb_spacer = ttk.Frame(self.toolbar)  # 顶部模式下把页码推到最右（占位撑开）

        # 内容区（网格布局：画布 + 滚动条 + 预览）
        self.content = ttk.Frame(self.root)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.content, bg='#1e1e1e', highlightthickness=0, takefocus=1)
        self.vbar = ttk.Scrollbar(self.content, orient='vertical', command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(self.content, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.vbar.grid(row=0, column=1, sticky='ns')
        self.hbar.grid(row=1, column=0, sticky='ew')

        self.canvas.bind('<Configure>', self.on_resize)
        self.canvas.bind('<MouseWheel>', self.on_wheel)
        # 右键菜单：切换信息栏显示
        self.canvas.bind('<Button-3>', self._show_context)
        self.content.bind('<Button-3>', self._show_context)

        # 状态栏（固定在底部；右键可隐藏/显示）
        self.status = ttk.Label(self.root, text='就绪', relief='sunken', anchor='w')
        self.status.bind('<Button-3>', self._show_context)

    def _tooltip(self, widget, text):
        def enter(e):
            self._tip = tk.Toplevel(self.root)
            self._tip.wm_overrideredirect(True)
            x, y = e.widget.winfo_pointerxy()
            self._tip.wm_geometry('+%d+%d' % (x + 12, y + 12))
            ttk.Label(self._tip, text=text, background='#ffffe0', relief='solid', borderwidth=1).pack()
        def leave(e):
            if getattr(self, '_tip', None):
                self._tip.destroy()
                self._tip = None
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    # ---- 布局：工具栏 顶·左；信息栏 底部（可隐藏） ----
    def layout(self):
        # 先全部收起
        self.toolbar.pack_forget()
        self.content.pack_forget()
        self.status.pack_forget()
        self.left_panel.pack_forget()

        if self.toolbar_pos == 'top':
            self.toolbar.pack(side='top', fill='x')
            self._pack_toolbar_widgets()

        if self.status_visible:
            self.status.pack(side='bottom', fill='x')

        # 工具栏在左侧时收进左侧面板
        if self.toolbar_pos == 'left':
            self.left_panel.pack(side='left', fill='y')
            self.toolbar.pack(in_=self.left_panel, side='top', fill='both', expand=True, padx=2, pady=2)
            self._pack_toolbar_widgets()

        self.content.pack(side='top', fill='both', expand=True)
        self.root.update_idletasks()
        self.render()

    def _pack_toolbar_widgets(self):
        # 先全部收起，避免重复 pack 叠加
        for w in self._tb_widgets:
            w.pack_forget()
        self.page_label.pack_forget()
        self.zoom_label.pack_forget()
        self._tb_spacer.pack_forget()
        side = 'left' if self.toolbar_pos == 'top' else 'top'
        for s in self._seps:
            s.configure(orient='vertical' if self.toolbar_pos == 'top' else 'horizontal')
        for w in self._tb_widgets:
            w.pack(side=side, padx=2, pady=2)
        if self.toolbar_pos == 'top':
            # 顶部工具栏：占位把前面控件推到左；倍率标签在页码左侧，页码号最右
            self.zoom_label.configure(anchor='e')
            self.page_label.configure(anchor='e')
            self._tb_spacer.pack(side='left', fill='x', expand=True)
            self.zoom_label.pack(side='left', padx=(6, 2), pady=2, anchor='e')
            self.page_label.pack(side='left', padx=2, pady=2, anchor='e')
        else:
            # 左侧工具栏：倍率标签在页码上方，二者均在最底部并居中（工具栏已 expand 填满整列）
            self.zoom_label.configure(anchor='center')
            self.page_label.configure(anchor='center')
            self.page_label.pack(side='bottom', padx=2, pady=(2, 6), fill='x')
            self.zoom_label.pack(side='bottom', padx=2, pady=(6, 2), fill='x')

    def _show_context(self, event):
        m = tk.Menu(self.root, tearoff=0)
        # 工具栏位置：顶部 / 左侧（右键选取，替代原“工具栏位置”下拉框）
        pos = tk.Menu(m, tearoff=0)
        pos.add_command(label='顶部' + ('  ✓' if self.toolbar_pos == 'top' else ''),
                        command=lambda: self._set_tbpos('top'))
        pos.add_command(label='左侧' + ('  ✓' if self.toolbar_pos == 'left' else ''),
                        command=lambda: self._set_tbpos('left'))
        m.add_cascade(label='工具栏位置', menu=pos)
        # 信息栏显示 / 隐藏
        if self.status_visible:
            m.add_command(label='隐藏信息栏', command=self._toggle_statusbar)
        else:
            m.add_command(label='显示信息栏', command=self._toggle_statusbar)
        # 最近阅读漫画：列出已读压缩包，点击跳转到最后阅读页
        recent = tk.Menu(m, tearoff=0)
        items = [(p, v) for p, v in self._history.items() if os.path.isfile(p)]
        if items:
            for p, v in reversed(items):  # 末尾为最近阅读，反转后最近在前
                label = '%s  (页 %d)' % (v['filename'], v['last_page'])
                recent.add_command(label=label, command=lambda pp=p: self._open_recent(pp))
        else:
            recent.add_command(label='（暂无记录）', state='disabled')
        m.add_cascade(label='打开最近阅读漫画', menu=recent)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ---- 控件同步 ----
    def _update_dir_state(self):
        """单页模式下阅读方向无意义，将方向下拉框置灰禁用；双页模式恢复可用。"""
        if self.mode == 'single':
            self.dir_cb.configure(state='disabled')
        else:
            self.dir_cb.configure(state='readonly')

    def _sync_controls(self):
        self.mode_cb.set('双页' if self.mode == 'double' else '单页')
        self.dir_cb.set('从右到左' if self.direction == 'rtl' else '从左到右')
        self.zoom_cb.set({'fitw': '适应宽度', 'fith': '适应高度', 'manual': '手动'}[self.zoom_mode])
        self.rot_cb.set({0: '不旋转', 90: '逆时针90°', 180: '旋转180°',
                         -90: '顺时针90°', 270: '顺时针90°'}.get(self.rotation, '不旋转'))
        self._update_dir_state()

    # ---- 打开文件 ----
    def open_file(self):
        ft = [('漫画压缩包', '*.zip;*.7z;*.rar;*.cbz;*.cbr;*.cb7;*.tar'),
              ('图片文件', '*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.webp;*.tiff;*.tif'),
              ('ZIP', '*.zip;*.cbz'), ('7Z', '*.7z;*.cb7'),
              ('RAR', '*.rar;*.cbr'), ('全部文件', '*.*')]
        path = filedialog.askopenfilename(title='选择漫画压缩包或图片文件', filetypes=ft)
        if path:
            self.open_path(path)

    def open_folder(self):
        path = filedialog.askdirectory(title='选择图片文件夹')
        if path:
            self.open_path(path)

    def open_path(self, path):
        try:
            arch = open_archive(path)
        except Exception as ex:
            messagebox.showerror('打开失败', str(ex))
            return
        try:
            self._cancel_anim()
            if self.archive:
                try:
                    self.archive.close()
                except Exception:
                    pass
            self.archive = arch
            self.archive_path = path
            self._record_open(path)
            self.img_cache.clear()
            self.index = 0
            self.root.title('漫画浏览器 — ' + os.path.basename(path))
            self.render()
        except Exception as ex:
            import traceback as _tb
            _log_crash('open_path', _tb.format_exc())
            try:
                messagebox.showerror('渲染失败', '打开文件后渲染出错：\n%s' % ex)
            except Exception:
                pass

    # ---- 页面读取与缓存 ----
    def load_page(self, name):
        if name in self.img_cache:
            return self.img_cache[name]
        try:
            data = self.archive.read(name)
            im = Image.open(io.BytesIO(data))
            im.load()
            is_gif = (getattr(im, 'format', '') == 'GIF') and getattr(im, 'is_animated', False)
            if is_gif:
                frames, durations = [], []
                for f in ImageSequence.Iterator(im):
                    fr = f.convert('RGBA') if f.mode != 'RGBA' else f.copy()
                    frames.append(fr)
                    durations.append(f.info.get('duration', 100))
                entry = {'frames': frames, 'durations': durations, 'gif': True}
            else:
                if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
                    base = im.convert('RGBA')
                else:
                    base = im.convert('RGB')
                entry = {'frames': [base], 'durations': [0], 'gif': False}
        except Exception:
            ph = Image.new('RGB', (400, 600), (40, 40, 40))
            entry = {'frames': [ph], 'durations': [0], 'gif': False, 'error': True}
        self.img_cache[name] = entry
        # 限制缓存大小
        while len(self.img_cache) > 14:
            self.img_cache.pop(next(iter(self.img_cache)))
        return entry

    def _is_gif(self, name):
        if name not in self.img_cache:
            self.load_page(name)
        return self.img_cache.get(name, {}).get('gif', False)

    # ---- 缩放计算 ----
    def _scaled_size(self, im, avail_w, avail_h):
        w, h = im.size
        if self.zoom_mode == 'fitw':
            scale = avail_w / w if w else 1
        elif self.zoom_mode == 'fith':
            scale = avail_h / h if h else 1
        else:
            scale = self.zoom
        return max(1, round(w * scale)), max(1, round(h * scale))

    # ---- 渲染 ----
    def render(self):
        self._cancel_anim()
        if not self.archive:
            return
        names = self.archive.names()
        if not names:
            self._render_empty('压缩包中没有可识别的图片。')
            return

        n = len(names)
        step = 2 if self.mode == 'double' else 1
        self.index = max(0, min(self.index, n - 1))

        if self.mode == 'single':
            disp = [names[self.index]]
        else:
            a = names[self.index]
            b = names[self.index + 1] if self.index + 1 < n else None
            disp = [a, b] if b else [a]

        self._displayed = disp
        self._gif_frame = {nm: 0 for nm in disp if self._is_gif(nm)}
        self._draw()
        self._update_status()
        self._start_anim()
        # 将焦点移回画布，避免按钮保留焦点导致空格被重复触发
        if not self._in_entry():
            self.canvas.focus_set()

    def _draw(self):
        self.canvas.delete('all')
        self._photo_refs = []
        if not self._displayed:
            return

        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        count = len(self._displayed)
        avail_w = cw / count
        avail_h = ch

        order = list(self._displayed)
        if self.mode == 'double' and self.direction == 'rtl':
            order = list(reversed(self._displayed))

        photos, total_w, max_h = [], 0, 0
        for nm in order:
            entry = self.load_page(nm)
            fi = self._gif_frame.get(nm, 0) % len(entry['frames'])
            frame = entry['frames'][fi]
            if self.rotation:
                frame = frame.rotate(self.rotation, expand=True)
            nw, nh = self._scaled_size(frame, avail_w, avail_h)
            disp = frame.resize((nw, nh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(disp)
            photos.append((photo, nw, nh))
            total_w += nw
            max_h = max(max_h, nh)

        start_x = (cw - total_w) // 2 if total_w < cw else 0
        start_y = (ch - max_h) // 2 if max_h < ch else 0
        x = start_x
        for photo, nw, nh in photos:
            y = start_y + (max_h - nh) // 2
            self.canvas.create_image(x, y, image=photo, anchor='nw')
            x += nw
        self._photo_refs = photos
        self.canvas.configure(scrollregion=(0, 0, max(total_w, cw), max(max_h, ch)))
        # 图片不超出显示范围时自动隐藏滚动条
        self._update_scrollbars(cw, ch, total_w, max_h)

    def _update_scrollbars(self, cw, ch, total_w, max_h):
        # 仅在图片超出可视范围时显示对应滚动条；否则隐藏，避免多余占位
        if not self._displayed:
            need_v = need_h = False
        else:
            need_v = max_h > ch + 1
            need_h = total_w > cw + 1
        if need_v and not self._vbar_shown:
            self.vbar.grid()
            self._vbar_shown = True
        elif not need_v and self._vbar_shown is not False:
            self.vbar.grid_remove()
            self._vbar_shown = False
        if need_h and not self._hbar_shown:
            self.hbar.grid()
            self._hbar_shown = True
        elif not need_h and self._hbar_shown is not False:
            self.hbar.grid_remove()
            self._hbar_shown = False

    def _update_status(self):
        if not self.archive:
            self.status.configure(text='就绪')
            self._update_page_label()
            return
        names = self.archive.names()
        n = len(names)
        step = 2 if self.mode == 'double' else 1
        cur = self.index + 1
        if self.mode == 'double':
            nxt = min(self.index + 2, n)
            pg = '%d-%d' % (cur, nxt) if nxt > cur else str(cur)
        else:
            pg = str(cur)
        ztxt = '手动 %.0f%%' % (self.zoom * 100) if self.zoom_mode == 'manual' else (
            '适应宽度' if self.zoom_mode == 'fitw' else '适应高度')
        self.status.configure(
            text='第 %s / %d 页   |   显示：%s   |   方向：%s   |   缩放：%s   |   %s' % (
                pg, n,
                '双页' if self.mode == 'double' else '单页',
                '从右到左' if self.direction == 'rtl' else '从左到右',
                ztxt,
                os.path.basename(self.archive_path or '')))
        self._update_page_label(pg, n)
        self._update_zoom_label()

    def _update_page_label(self, pg=None, n=None):
        """刷新工具栏页码标签：当前页 / 总页数。"""
        if not getattr(self, 'page_label', None):
            return
        if pg is None or n is None:
            self.page_label.configure(text='0 / 0')
        else:
            self.page_label.configure(text='%s / %d' % (pg, n))

    def _update_zoom_label(self):
        """刷新工具栏放大倍率标签：手动显示百分比，适应模式显示简写。"""
        if not getattr(self, 'zoom_label', None):
            return
        if self.zoom_mode == 'manual':
            self.zoom_label.configure(text='%.0f%%' % (self.zoom * 100))
        elif self.zoom_mode == 'fitw':
            self.zoom_label.configure(text='适应宽')
        else:  # fith
            self.zoom_label.configure(text='适应高')

    # ---- GIF 动画 ----
    def _start_anim(self):
        self._cancel_anim()
        gifs = [nm for nm in self._displayed if self._is_gif(nm)]
        if not gifs:
            return
        self._anim_names = gifs
        self._schedule_anim()

    def _schedule_anim(self):
        durs = []
        for nm in self._anim_names:
            entry = self.load_page(nm)
            fi = self._gif_frame.get(nm, 0) % len(entry['durations'])
            durs.append(entry['durations'][fi] or 100)
        dur = max(durs) or 100
        self._anim_job = self.root.after(dur, self._tick_anim)

    def _tick_anim(self):
        for nm in self._anim_names:
            entry = self.load_page(nm)
            self._gif_frame[nm] = (self._gif_frame.get(nm, 0) + 1) % len(entry['frames'])
        self._draw()
        self._schedule_anim()

    def _cancel_anim(self):
        if getattr(self, '_anim_job', None):
            self.root.after_cancel(self._anim_job)
            self._anim_job = None

    # ---- 下一页预览已移除（按需求不再显示） ----

    # ---- 空状态 ----
    def _render_empty(self, msg):
        self._cancel_anim()
        self.canvas.delete('all')
        self._displayed = []
        self._update_scrollbars(0, 0, 0, 0)
        self.status.configure(text=msg)

    # ---- 导航 ----
    def next_page(self):
        if not self.archive:
            return
        n = len(self.archive.names())
        step = 2 if self.mode == 'double' else 1
        nxt = self.index + step
        if nxt < n:
            self.index = nxt
            self.render()
            self._record_page()

    def prev_page(self):
        if not self.archive:
            return
        step = 2 if self.mode == 'double' else 1
        self.index = max(0, self.index - step)
        self.render()
        self._record_page()

    def jump_page(self):
        if not self.archive:
            return
        txt = self.jump_var.get().strip()
        if not txt.isdigit():
            return
        p = int(txt) - 1
        self.index = max(0, p)
        self.render()
        self._record_page()

    # ---- 视图切换 ----
    def _set_mode(self, m):
        if self.mode != m:
            self.mode = m
            self._save_settings()
            self._sync_controls()
            self.render()

    def _set_dir(self, d):
        if self.direction != d:
            self.direction = d
            self._save_settings()
            self._sync_controls()
            self.render()

    def _set_zoom(self, z):
        if self.zoom_mode != z:
            self.zoom_mode = z
            self._save_settings()
            self._sync_controls()
            self._update_zoom_label()
            self.render()

    def _set_tbpos(self, p):
        if self.toolbar_pos != p:
            self.toolbar_pos = p
            self._save_settings()
            self._sync_controls()
            self.layout()

    def _toggle_statusbar(self):
        self.status_visible = not self.status_visible
        self._save_settings()
        if self.status_visible:
            self.status.pack(side='bottom', fill='x')
        else:
            self.status.pack_forget()
        self.root.update_idletasks()

    def zoom_in(self):
        self.zoom_mode = 'manual'
        self.zoom = min(8.0, round((self.zoom + 0.05) * 100) / 100)  # 每级 +5%
        self._sync_controls()
        self._save_settings()
        self._update_zoom_label()
        self.render()

    def zoom_out(self):
        self.zoom_mode = 'manual'
        self.zoom = max(0.05, round((self.zoom - 0.05) * 100) / 100)  # 每级 -5%
        self._sync_controls()
        self._save_settings()
        self._update_zoom_label()
        self.render()

    def _on_rotate(self, event=None):
        """旋转下拉框：不旋转 / 逆时针90° / 旋转180° / 顺时针90°，对当前图片进行旋转（跨页持久，缩放/翻页不受影响）。"""
        ang = {'不旋转': 0, '逆时针90°': 90, '旋转180°': 180,
               '顺时针90°': -90}.get(self.rot_cb.get(), 0)
        if ang == self.rotation:
            return
        self.rotation = ang
        if self.archive:
            self.render()

    # ---- 全屏 ----
    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes('-fullscreen', self.fullscreen)
        if self.fullscreen:
            self.toolbar.pack_forget()
            self.status.pack_forget()
            self.left_panel.pack_forget()
        else:
            self.layout()
        self.root.update_idletasks()
        self.render()

    # ---- 事件 ----
    def on_resize(self, event):
        if getattr(self, '_resize_job', None):
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self.render)

    def on_wheel(self, event):
        # Ctrl + 滚轮 = 缩放；普通滚轮 = 翻页
        if event.state & 0x4:  # 0x4 == Control 修饰位
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return
        if event.delta > 0:
            self.prev_page()
        else:
            self.next_page()

    # ---- 拖拽打开（tkinterdnd2 / TkDnD 扩展，业界唯一可靠方案）----
    def _enable_drag_drop(self):
        """使用 tkinterdnd2 把窗口注册为文件拖放目标。

        彻底放弃 ctypes 子类化 / WM_DROPFILES 覆盖窗口方案：
          * 子类化 Tk 窗口过程会破坏 _tkinter 内部状态，导致程序闪退/打不开；
          * WM_DROPFILES / WS_EX_ACCEPTFILES 只对顶层窗口生效且需实现 COM
            IDropTarget，自建透明覆盖窗口未实现该接口，Shell 判定“不可放置”
            而显示禁止光标。
        TkDnD 通过 Tk 标准机制注册拖放，原生融入 Tk 事件循环，无 GIL/子类化问题。
        未安装 tkinterdnd2 时降级：仅支持菜单“打开”或把文件拖到 exe 图标打开。
        """
        if not DND_AVAILABLE:
            return
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_tkdnd_drop)
            # 画布也注册：落在图像区域时同样触发（TkDnD 取最内层已注册控件）
            cv = getattr(self, 'canvas', None)
            if cv is not None:
                try:
                    cv.drop_target_register(DND_FILES)
                    cv.dnd_bind('<<Drop>>', self._on_tkdnd_drop)
                except Exception:
                    pass
        except Exception as ex:
            _log_crash('_enable_drag_drop', repr(ex))

    def _on_tkdnd_drop(self, event):
        # event.data 为空格分隔的路径字符串；含空格/中文路径会被 {} 包裹。
        # 用 Tk 的 splitlist 解析最稳妥（正确处理花括号与引号）。
        try:
            raw = (getattr(event, 'data', '') or '').strip()
            if not raw:
                return
            paths = self.root.tk.splitlist(raw)
            targets = [p for p in paths
                       if p and (os.path.isfile(p) or os.path.isdir(p))]
            if targets:
                self.open_path(targets[0])
        except Exception as ex:
            _log_crash('_on_tkdnd_drop', repr(ex))
            try:
                messagebox.showerror('拖拽打开失败', str(ex))
            except Exception:
                pass

    def _in_entry(self):
        w = self.root.focus_get()
        return isinstance(w, (tk.Entry, ttk.Entry))

    def _bind_keys(self):
        # 在输入框（跳转框）中按键时不触发全局快捷键
        g = lambda fn: (lambda e: None if self._in_entry() else fn())
        self.root.bind('<space>', g(lambda: self.next_page()))
        self.root.bind('<BackSpace>', g(lambda: self.prev_page()))
        self.root.bind('<Right>', g(lambda: self.next_page()))
        self.root.bind('<Left>', g(lambda: self.prev_page()))
        self.root.bind('<Prior>', g(lambda: self.prev_page()))   # PageUp
        self.root.bind('<Next>', g(lambda: self.next_page()))    # PageDown
        self.root.bind('<Home>', g(lambda: self._goto(0)))
        self.root.bind('<End>', g(lambda: self._goto_end()))
        self.root.bind('<Control-equal>', g(lambda: self.zoom_in()))
        self.root.bind('<Control-minus>', g(lambda: self.zoom_out()))
        self.root.bind('<Control-KP_Add>', g(lambda: self.zoom_in()))
        self.root.bind('<Control-KP_Subtract>', g(lambda: self.zoom_out()))
        self.root.bind('<KeyPress-f>', g(lambda: self.toggle_fullscreen()))
        self.root.bind('<KeyPress-F>', g(lambda: self.toggle_fullscreen()))
        self.root.bind('<KeyPress-w>', g(lambda: self._set_zoom('fitw')))
        self.root.bind('<KeyPress-h>', g(lambda: self._set_zoom('fith')))
        self.root.bind('<KeyPress-1>', g(lambda: self._set_mode('single')))
        self.root.bind('<KeyPress-2>', g(lambda: self._set_mode('double')))
        self.root.bind('<KeyPress-r>', g(lambda: self._set_dir('rtl' if self.direction == 'ltr' else 'ltr')))
        self.root.bind('<KeyPress-g>', g(lambda: self.ask_jump()))
        self.root.bind('<Escape>', lambda e: (self.toggle_fullscreen() if self.fullscreen else None))

    def _goto(self, idx):
        self.index = max(0, idx)
        self.render()
        self._record_page()

    def _goto_end(self):
        if self.archive:
            self.index = len(self.archive.names()) - 1
            self.render()
            self._record_page()

    def ask_jump(self):
        if not self.archive:
            return
        n = len(self.archive.names())
        val = simpledialog.askinteger('跳转', '跳转到第几页 (1-%d)：' % n, minvalue=1, maxvalue=n)
        if val:
            self.index = val - 1
            self.render()
            self._record_page()

    # ---- 帮助 ----
    def show_help(self):
        msg = (
            '漫画压缩文档浏览器 — 快捷键\n'
            '------------------------------\n'
            '空格 / → / PageDown : 下一页\n'
            'BackSpace / ← / PageUp : 上一页\n'
            'Ctrl + = / - : 放大 / 缩小（每级 5%）\n'
            'Ctrl + 鼠标滚轮 : 放大 / 缩小（每级 5%）\n'
            'W : 适应宽度    H : 适应高度\n'
            '1 : 单页显示    2 : 双页显示\n'
            'R : 切换阅读方向(左→右 / 右→左)\n'
            'G : 跳转到指定页\n'
            'F / Esc : 全屏 / 退出全屏\n'
            'Home / End : 首页 / 末页\n'
            '鼠标滚轮 : 翻页（按住 Ctrl 滚轮为缩放）\n'
            '\n'
            '其他：可直接把漫画压缩文件或图片拖到浏览页面打开；\n'
            '在浏览页面点右键，可“隐藏 / 显示 信息栏”，\n'
            '并选择“工具栏位置”（顶部 / 左侧）。\n'
            '支持的格式：zip / 7z / rar / cbz / cbr / cb7（rar/cbr 由内置 7-Zip 解压）、\n'
            '常见图片文件（jpg / png / gif / webp 等），以及图片文件夹。\n'
            '以上布局设置均会自动记忆。\n'
            '\n'
            '阅读记录：工具栏“阅读记录”可查看已读漫画（文件名 / 阅读时间 / 页码 / 路径）；\n'
            '双击记录可直接打开并从最后阅读页开始；Shift / Ctrl 可多选后删除选中或全部记录；\n'
            '若压缩包已被删除，双击会提示“文件已删除”。'
            '\n'
            '——————————————\n'
            '版本：' + self.VERSION + '\n'
            '作者：Justin F.\n'
            '邮箱：fc666@hotmail.com'
        )
        messagebox.showinfo('帮助 / 关于', msg)


# ---------------------------------------------------------------------------
def _enable_dpi_awareness():
    """声明进程为「每显示器高 DPI 感知」，避免大图在高分屏被系统拉伸而模糊。

    不感知 DPI 时，Tk 以 96 DPI 布局，系统再把整窗按缩放比（如 150%）拉伸，
    结果是窗口里越大的图片越糊。声明感知后配合 tk scaling 设为真实 DPI，
    即可让图片以设备像素 1:1 绘制，保持清晰。
    """
    try:
        import ctypes
        # Windows 10 1703+ 的「每显示器 DPI 感知 v2」是最稳的方案
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        except Exception:
            try:
                # 旧系统回退到 shcore
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _set_tk_scaling(root):
    """把 Tk 的缩放设为真实 DPI，使 1 个 Tk 逻辑像素 = 1 个设备像素。

    这样画布 winfo_width() 返回的是设备像素，PhotoImage 按设备分辨率生成，
    绘制时不再有缩放拉伸，图片保持清晰。非 Windows 平台自动跳过。
    """
    try:
        import ctypes
        dpi = ctypes.windll.user32.GetDpiForSystem()
        if dpi and dpi > 0:
            root.tk.call('tk', 'scaling', dpi / 72.0)
    except Exception:
        pass


# ---------------------------------------------------------------------------
def main():
    if not TK_AVAILABLE:
        sys.stderr.write(
            "错误：当前 Python 环境未包含 tkinter，无法启动图形界面。\n"
            "请使用 python.org 官方 Windows 安装包重新安装 Python（默认包含 tkinter），\n"
            "或在安装时勾选 “tcl/tk and IDLE”。\n")
        sys.exit(1)
    _enable_dpi_awareness()        # 必须在创建 Tk 根窗口之前声明
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()      # TkDnD 增强的 Tk 根窗口，支持文件拖放
    else:
        root = tk.Tk()
    _set_tk_scaling(root)          # 让图片按设备像素 1:1 绘制，避免高分屏模糊
    _install_exception_logging(root)
    app = ComicViewer(root)
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        root.after(200, lambda: app.open_path(sys.argv[1]))
    root.mainloop()


if __name__ == '__main__':
    main()
