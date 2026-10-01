"""v13.7 离线逻辑验证：2% 缩放步进 + 左侧工具栏页码居中置底（headless 真实 tkinter）。"""
import tkinter as tk
import comic_viewer as cv

root = tk.Tk()
root.withdraw()
app = cv.ComicViewer(root)
print('[OK] ComicViewer 构造成功')


def is_packed(w):
    try:
        return bool(w.pack_info())
    except Exception:
        return False


def anchor_of(w):
    # ttk 控件的 cget 可能返回 Tcl index 对象，configure('anchor')[-1] 才是当前值（需转 str）
    return str(w.configure('anchor')[-1])


# ===== 1) 缩放步进为 2%（不再是 ×1.2 ≈ 20%）=====
def zset(v):
    app.zoom_mode = 'manual'
    app.zoom = v

# 从 100% 放大一级 -> 102%
zset(1.0)
app.zoom_in()
assert abs(app.zoom - 1.02) < 1e-9, '放大一级应为 1.02，实得 %r' % app.zoom
# 再放大一级 -> 104%
app.zoom_in()
assert abs(app.zoom - 1.04) < 1e-9, '再放大一级应为 1.04，实得 %r' % app.zoom
# 缩小一级 -> 102%
app.zoom_out()
assert abs(app.zoom - 1.02) < 1e-9, '缩小一级应为 1.02，实得 %r' % app.zoom
# 边界：封顶 800%
zset(8.0)
app.zoom_in()
assert abs(app.zoom - 8.0) < 1e-9, '封顶 8.0，实得 %r' % app.zoom
# 边界：保底 5%
zset(0.05)
app.zoom_out()
assert abs(app.zoom - 0.05) < 1e-9, '保底 0.05，实得 %r' % app.zoom
print('[OK] 缩放步进 = 2%（100->102->104->102，封顶 800% / 保底 5%）')


# ===== 2) 顶部工具栏：页码标签靠右 (anchor=e) =====
app.toolbar_pos = 'top'
app._pack_toolbar_widgets()
assert anchor_of(app.page_label) == 'e', '顶部模式页码应右对齐(anchor=e)'
print('[OK] 顶部模式页码 anchor=%s（右对齐）' % anchor_of(app.page_label))


# ===== 3) 左侧工具栏：页码置底 + 居中 (anchor=center)，工具栏填满整列 =====
app.toolbar_pos = 'left'
app.layout()  # 走完整 layout：left_panel expand 填满整列
info = app.page_label.info()
tinfo = app.toolbar.pack_info()
assert info.get('side') == 'bottom', '左侧模式页码应 side=bottom，实得 %r' % info.get('side')
assert anchor_of(app.page_label) == 'center', '左侧模式页码应居中(anchor=center)'
assert str(tinfo.get('expand')) == '1', '左侧模式工具栏应 expand=1 填满整列，实得 %r' % tinfo.get('expand')
print('[OK] 左侧模式: 页码 side=%s, anchor=%s(居中), 工具栏 expand=%s(填满整列)' % (
    info.get('side'), anchor_of(app.page_label), tinfo.get('expand')))


# ===== 4) 切换回顶部后 anchor 复位为 e =====
app.toolbar_pos = 'top'
app._pack_toolbar_widgets()
assert anchor_of(app.page_label) == 'e', '切回顶部页码应复位右对齐'
print('[OK] 切回顶部后页码 anchor 复位为 %s' % anchor_of(app.page_label))


# ===== 5) Ctrl+滚轮=缩放(2%)，普通滚轮=翻页（联动不变）=====
class Ev:
    def __init__(self, delta, state):
        self.delta = delta
        self.state = state

zoomed = {'n': 0}
paged = {'n': 0}
app.zoom_in, app.zoom_out = (lambda: zoomed.__setitem__('n', zoomed['n'] + 1),
                              lambda: zoomed.__setitem__('n', zoomed['n'] - 1))
app.prev_page, app.next_page = (lambda: paged.__setitem__('n', paged['n'] + 1),
                                 lambda: paged.__setitem__('n', paged['n'] - 1))

app.on_wheel(Ev(120, 0x4))
assert zoomed['n'] == 1, 'Ctrl+滚轮上应放大'
app.on_wheel(Ev(-120, 0x4))
assert zoomed['n'] == 0, 'Ctrl+滚轮下应缩小'
app.on_wheel(Ev(120, 0x0))
assert paged['n'] == 1, '普通滚轮上应上一页'
app.on_wheel(Ev(-120, 0x0))
assert paged['n'] == 0, '普通滚轮下应下一页'
print('[OK] Ctrl+滚轮=缩放, 普通滚轮=翻页 联动正确')


print('\n==== v13.7 逻辑验证全部通过 ====')
root.destroy()
