"""v13.6 离线逻辑验证：页码标签 + Ctrl+滚轮缩放（headless 真实 tkinter）。"""
import sys, types

# 提供假的 tkinterdnd2 / PIL 之外的依赖在 buildenv 中已具备
import comic_viewer as cv

# 用虚拟 root 构造（不进入主循环）
import tkinter as tk
root = tk.Tk()
root.withdraw()

app = cv.ComicViewer(root)
print('[OK] ComicViewer 构造成功')

def is_packed(w):
    try:
        return bool(w.pack_info())
    except Exception:
        return False

# --- 1) 页码标签存在，初始 0 / 0 ---
assert hasattr(app, 'page_label'), 'page_label 未创建'
assert app.page_label.cget('text') == '0 / 0', '初始页码标签应为 0 / 0'
print('[OK] 页码标签初始:', app.page_label.cget('text'))

# --- 2) 顶部工具栏：页码标签在右侧（spacer 撑开）---
app.toolbar_pos = 'top'
app._pack_toolbar_widgets()
info = app.page_label.info()
assert info.get('side') == 'left', '顶部模式页码应 side=left(靠右)'
sp = app._tb_spacer
# spacer 应在 page_label 之前被 pack（expand 占位）
assert is_packed(sp), '顶部模式 spacer 应被 pack'
print('[OK] 顶部模式: page_label.side=%s, spacer 已 pack' % info.get('side'))

# --- 3) 左侧工具栏：页码标签在最底部 ---
app.toolbar_pos = 'left'
app._pack_toolbar_widgets()
info = app.page_label.info()
assert info.get('side') == 'bottom', '左侧模式页码应 side=bottom'
assert not is_packed(sp), '左侧模式 spacer 不应被 pack'
print('[OK] 左侧模式: page_label.side=%s, spacer 未 pack' % info.get('side'))

# --- 4) _update_page_label 随翻页更新 ---
app.toolbar_pos = 'top'
app._pack_toolbar_widgets()
app._update_page_label('5', 100)
assert app.page_label.cget('text') == '5 / 100', app.page_label.cget('text')
print('[OK] 页码更新为:', app.page_label.cget('text'))

# --- 5) _update_status 无归档时页码归零 ---
app._update_status()
assert app.page_label.cget('text') == '0 / 0', app.page_label.cget('text')
print('[OK] 无归档时页码归零:', app.page_label.cget('text'))

# --- 6) Ctrl+滚轮 = 缩放；普通滚轮 = 翻页 ---
class Ev:
    def __init__(self, delta, state):
        self.delta = delta
        self.state = state

zoomed_in = {'n': 0}
prev = {'n': 0}

orig_zin = app.zoom_in
orig_zout = app.zoom_out
orig_prev = app.prev_page
orig_next = app.next_page

def zin():
    zoomed_in['n'] += 1
def zout():
    zoomed_in['n'] -= 1
def pprev():
    prev['n'] += 1
def pnext():
    prev['n'] -= 1

app.zoom_in = zin
app.zoom_out = zout
app.prev_page = pprev
app.next_page = pnext

# Ctrl+滚轮上 -> zoom_in
app.on_wheel(Ev(120, 0x4))
assert zoomed_in['n'] == 1, 'Ctrl+滚轮上应放大'
# Ctrl+滚轮下 -> zoom_out
app.on_wheel(Ev(-120, 0x4))
assert zoomed_in['n'] == 0, 'Ctrl+滚轮下应缩小'
# 普通滚轮上 -> prev_page
app.on_wheel(Ev(120, 0x0))
assert prev['n'] == 1, '普通滚轮上应上一页'
# 普通滚轮下 -> next_page
app.on_wheel(Ev(-120, 0x0))
assert prev['n'] == 0, '普通滚轮下应下一页'
print('[OK] Ctrl+滚轮=缩放, 普通滚轮=翻页 联动正确')

# 恢复
app.zoom_in = orig_zin
app.zoom_out = orig_zout
app.prev_page = orig_prev
app.next_page = orig_next

print('\n==== v13.6 逻辑验证全部通过 ====')
root.destroy()
