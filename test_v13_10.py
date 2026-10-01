#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v13.10 离线逻辑验证：CSV 落地打包文件夹 / 末次阅读时间 / 记录对话框（自定义网格+深灰表格线+可拖拽列宽）。"""
import os, sys, csv, types, tempfile, shutil
import tkinter as tk
from tkinter import ttk
import comic_viewer as cv

# ---- 静默 GUI 相关副作用（headless 环境）----
_warn = []
cv.messagebox = types.SimpleNamespace(
    showwarning=lambda *a, **k: _warn.append(a),
    showinfo=lambda *a, **k: None,
    showerror=lambda *a, **k: None,
    askyesno=lambda *a, **k: True,
)
_orig_wait = tk.Toplevel.wait_window
_orig_grab = tk.Toplevel.grab_set
tk.Toplevel.wait_window = lambda self: None
tk.Toplevel.grab_set = lambda self: None

root = tk.Tk()
root.geometry('1200x800')   # 给定明确尺寸，供对话框 0.6× 计算
root.update_idletasks()
app = cv.ComicViewer(root)

fails = []
def check(cond, msg):
    if cond:
        print('[OK]', msg)
    else:
        print('[FAIL]', msg)
        fails.append(msg)

# ===== 1) CSV 落地"打包文件夹"（与 exe 同目录）=====
tmpdir = tempfile.mkdtemp(prefix='pkg_')
fake_exe = os.path.join(tmpdir, 'ComicViewer_v13.10.exe')
open(fake_exe, 'w').close()
saved_frozen = getattr(sys, 'frozen', None)
saved_exe = sys.executable
sys.frozen = True
sys.executable = fake_exe
try:
    hp = app._history_path()
    check(os.path.dirname(hp) == tmpdir,
          '打包模式下 CSV 落在 exe 同目录（%s）' % hp)
    # 实际能写入该目录
    app._history.clear()
    app._history['Z:/comic/a.cbz'] = {'filename': 'a.cbz', 'last_page': 3, 'last_read': '2026-08-16 10:00:00'}
    app._save_history()
    check(os.path.isfile(hp), '打包文件夹中已生成 reading_history.csv')
finally:
    sys.frozen = saved_frozen
    sys.executable = saved_exe
    shutil.rmtree(tmpdir, ignore_errors=True)

# ===== 2) 末次阅读时间：record_open / record_page 写入并持久化 =====
app._history.clear()
app.archive_path = None
app._history_path()  # 触发 makedirs
app._record_open('C:/x/one.cbz')
v = app._history['C:/x/one.cbz']
check(bool(v.get('last_read')), '打开时写入 last_read：%s' % v.get('last_read'))
check(v['last_page'] == 1, '新记录 last_page=1')

# 翻页更新时间与页数
app.archive_path = 'C:/x/one.cbz'
app.index = 4
app._record_page()
v = app._history['C:/x/one.cbz']
check(v['last_page'] == 5, '翻页后 last_page=5')
check(bool(v.get('last_read')), '翻页后刷新 last_read')

# 重新加载，时间应保留
app2 = cv.ComicViewer(root)
loaded = app2._history.get('C:/x/one.cbz')
check(loaded and loaded['last_page'] == 5, '重载 CSV 后 last_page 保留')
check(loaded and loaded['last_read'] == v['last_read'], '重载 CSV 后 last_read 保留')

# ===== 3) 删除选中记录 =====
app._history['C:/x/two.cbz'] = {'filename': 'two.cbz', 'last_page': 2, 'last_read': 'x'}
before = len(app._history)
app._history.pop('C:/x/two.cbz', None)
app._save_history()
app3 = cv.ComicViewer(root)
check('C:/x/two.cbz' not in app3._history, '删除后重载 CSV 不再包含该记录')
check(len(app3._history) == before - 1, '删除后记录数正确')

# ===== 4) 打开已删除文件：守卫提示"文件已删除"，且不调用 open_path =====
called = []
app.open_path = lambda *a, **k: called.append(a)
_warn.clear()
app._open_recent('C:/x/not_exist.cbz')
check(any('文件已删除' in (w[0] if w else '') for w in _warn),
      '文件不存在时弹出"文件已删除"提示')
check(len(called) == 0, '文件不存在时不调用 open_path（避免报错）')

# ===== 5) 阅读记录对话框（自定义网格 + 深灰表格线）=====
_created = []
_orig_tl_init = tk.Toplevel.__init__
def _cap_tl_init(self, *a, **k):
    _orig_tl_init(self, *a, **k)
    _created.append(self)
tk.Toplevel.__init__ = _cap_tl_init
app._history.clear()
app._history['C:/r/a.cbz'] = {'filename': 'a.cbz', 'last_page': 1, 'last_read': '2026-08-16 09:00:00'}
app._history['C:/r/b.cbz'] = {'filename': 'b.cbz', 'last_page': 7, 'last_read': '2026-08-16 11:00:00'}
opened = []
app._open_recent = lambda p: opened.append(p)   # 捕获双击打开目标
# 直接调用方法（wait_window 已 stub 为 no-op，立即返回）
app._open_history_dialog()
tk.Toplevel.__init__ = _orig_tl_init
dlg = _created[-1]

# 在 dlg 子树中查找网格框架（底色深灰 #555555）
def _find_grid(w):
    if isinstance(w, tk.Frame) and str(w.cget('bg')) == '#555555':
        return w
    for ch in w.winfo_children():
        r = _find_grid(ch)
        if r:
            return r
    return None
grid = _find_grid(dlg)
check(grid is not None, '找到深灰网格框架（非 Treeview）')
check(str(grid.cget('bg')) == '#555555', '网格框架底色为深灰 #555555（作为表格线）')

labels = grid.winfo_children()
headers = [lb for lb in labels if lb.grid_info().get('row') == 0]
# 表头为 Frame，内含标题 Label + 分隔条
def _hdr_text(hf):
    for ch in hf.winfo_children():
        if isinstance(ch, tk.Label):
            return ch.cget('text')
    return ''
htexts = [_hdr_text(hf) for hf in headers]
check(htexts == ['文件名', '阅读时间', '页码', '路径'],
      '列顺序为 文件名/阅读时间/页码/路径（%s）' % htexts)
check(str(headers[0].cget('bg')) == '#d9d9d9', '表头底色为浅灰（区分表头）')

# 可拖拽列宽：表头分隔条（非末列）+ 水平滚动条
seps = []
for hf in headers:
    for ch in hf.winfo_children():
        if isinstance(ch, tk.Frame) and str(ch.cget('cursor')) == 'sb_h_double_arrow':
            seps.append(ch)
check(len(seps) == 3, '表头含 3 个可拖拽分隔条（4 列，末列无）')
check(all(s.bind('<B1-Motion>') != '' for s in seps),
      '分隔条已绑定拖动事件（<B1-Motion>）')
hsb_found = False
for ch in dlg.winfo_children():
    if isinstance(ch, ttk.Frame):
        for sub in ch.winfo_children():
            if isinstance(sub, ttk.Scrollbar) and str(sub.cget('orient')) == 'horizontal':
                hsb_found = True
check(hsb_found, '含水平滚动条（列加宽后可横向滚动）')

row_labels = [lb for lb in labels if lb.grid_info().get('row', 0) > 0]
check(len(row_labels) == 8, '显示全部 2 条记录（每条 4 格，共 8 格）')
check(all(str(lb.cget('relief')) == 'flat' for lb in labels),
      '所有单元格 relief=flat（表格线由 1px 间隙露底色形成）')
check(all(set(str(lb.grid_info().get('sticky'))) == set('nsew') for lb in row_labels),
      '数据单元格 sticky=nsew（填满列宽，文字裁剪不溢出/不换行）')

# 字体一致性：表头与数据单元格均应使用 YaHei 9（与 tk.Label 默认一致）
import tkinter.font as _tkfont
def _actual_font(w):
    return _tkfont.Font(font=w.cget('font')).actual()
_hdr_lbl = None
for _ch in headers[0].winfo_children():
    if isinstance(_ch, tk.Label):
        _hdr_lbl = _ch
        break
_cell_font = _actual_font(row_labels[0])
_hdr_font = _actual_font(_hdr_lbl)
check('yahei' in _cell_font['family'].lower() and _cell_font['size'] == 9,
      '数据单元格字体=YaHei 9（与 tk 默认一致）：%s' % _cell_font)
check('yahei' in _hdr_font['family'].lower() and _hdr_font['size'] == 9,
      '表头字体=YaHei 9（与 tk 默认一致）：%s' % _hdr_font)
def _pad_has1(v):
    if isinstance(v, (tuple, list)):
        return 1 in v
    try:
        return '1' in str(v)
    except Exception:
        return False
check(all(_pad_has1(lb.grid_info().get('padx')) and _pad_has1(lb.grid_info().get('pady'))
          for lb in labels),
      '单元格含 1px 间隙（生成深灰表格线）')

check(row_labels[0].bind('<Double-1>') != '', '已绑定双击事件（双击打开并跳末页）')
check(row_labels[0].bind('<Button-1>') != '', '已绑定单击事件（Shift/Ctrl 多选）')
check(isinstance(app._hd_sel, set), '选中状态容器已初始化（set）')
check(len(app._hd_paths) == 2, '路径列表含 2 条记录')

dlg_w = dlg.winfo_width(); dlg_h = dlg.winfo_height()
root_w = root.winfo_width(); root_h = root.winfo_height()
check(dlg_w >= int(root_w * 0.6) - 5,
      '对话框宽 ≥ 主窗口×0.6（dlg=%d, root×0.6=%d）' % (dlg_w, int(root_w * 0.6)))
check(dlg_h >= int(root_h * 0.6) - 5,
      '对话框高 ≥ 主窗口×0.6（dlg=%d, root×0.6=%d）' % (dlg_h, int(root_h * 0.6)))

bf_children = []
for ch in dlg.winfo_children():
    if isinstance(ch, ttk.Frame):
        bf_children.extend(ch.winfo_children())
btn_texts = [str(b.cget('text')) for b in bf_children if isinstance(b, ttk.Button)]
check('删除选中记录' in btn_texts, '含"删除选中记录"按钮')
check('删除全部记录' in btn_texts, '含"删除全部记录"按钮')
check('关闭' in btn_texts, '含"关闭"按钮')

dlg.destroy()

tk.Toplevel.wait_window = _orig_wait
tk.Toplevel.grab_set = _orig_grab

# ===== 6) 工具栏旋转下拉框（不旋转/逆时针90°/旋转180°/顺时针90°）=====
check(hasattr(app, 'rot_cb'), '工具栏含旋转下拉框 rot_cb')
check(list(app.rot_cb['values']) == ['不旋转', '逆时针90°', '旋转180°', '顺时针90°'],
      '旋转下拉框选项为 不旋转/逆时针90°/旋转180°/顺时针90°（%s）' % list(app.rot_cb['values']))
app.rot_cb.set('逆时针90°'); app._on_rotate()
check(app.rotation == 90, '选择 逆时针90° 后 rotation=90（当前值 %d）' % app.rotation)
app.rot_cb.set('旋转180°'); app._on_rotate()
check(app.rotation == 180, '选择 旋转180° 后 rotation=180')
app.rot_cb.set('顺时针90°'); app._on_rotate()
check(app.rotation == -90, '选择 顺时针90° 后 rotation=-90')
app.rot_cb.set('不旋转'); app._on_rotate()
check(app.rotation == 0, '选择 不旋转 后 rotation=0')
# PIL 旋转 expand 行为 sanity：90° 应交换宽高
from PIL import Image as _PImage
_rim = _PImage.new('RGB', (200, 100)).rotate(90, expand=True)
check(_rim.size == (100, 200), 'PIL rotate(90, expand=True) 交换宽高：%s' % (_rim.size,))

print('\n==== 结果：%d 项失败 ====' % len(fails))
sys.exit(1 if fails else 0)
