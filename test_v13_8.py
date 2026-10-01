"""v13.8 离线逻辑验证：缩放步进 5% + 工具栏放大倍率标签（顶/左侧相对页码摆放）。"""
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
    return str(w.configure('anchor')[-1])


assert hasattr(app, 'zoom_label'), 'zoom_label 未创建'
print('[OK] 放大倍率标签初始:', app.zoom_label.cget('text'))


# ===== 1) 缩放步进为 5% =====
def zset(v):
    app.zoom_mode = 'manual'
    app.zoom = v

zset(1.0)
app.zoom_in()
assert abs(app.zoom - 1.05) < 1e-9, '放大一级应为 1.05，实得 %r' % app.zoom
app.zoom_in()
assert abs(app.zoom - 1.10) < 1e-9, '再放大一级应为 1.10，实得 %r' % app.zoom
app.zoom_out()
assert abs(app.zoom - 1.05) < 1e-9, '缩小一级应为 1.05，实得 %r' % app.zoom
zset(8.0); app.zoom_in()
assert abs(app.zoom - 8.0) < 1e-9, '封顶 8.0'
zset(0.05); app.zoom_out()
assert abs(app.zoom - 0.05) < 1e-9, '保底 0.05'
print('[OK] 缩放步进 = 5%（100->105->110->105，封顶 800% / 保底 5%）')


# ===== 2) 倍率标签文本随状态更新 =====
app.zoom_mode = 'manual'; app.zoom = 1.5; app._update_zoom_label()
assert app.zoom_label.cget('text') == '150%', app.zoom_label.cget('text')
app.zoom_mode = 'fitw'; app._update_zoom_label()
assert app.zoom_label.cget('text') == '适应宽', app.zoom_label.cget('text')
app.zoom_mode = 'fith'; app._update_zoom_label()
assert app.zoom_label.cget('text') == '适应高', app.zoom_label.cget('text')
# 真实 zoom_in 也刷新标签（联动）
app.zoom_mode = 'manual'; app.zoom = 1.0; app._update_zoom_label()
app.zoom_in()
assert app.zoom_label.cget('text') == '105%', app.zoom_label.cget('text')
print('[OK] 倍率标签文本: 手动=150%, 适应宽, 适应高, 放大后=105%')


# ===== 3) 顶部工具栏：倍率标签在页码左侧，均右对齐 =====
app.toolbar_pos = 'top'
app._pack_toolbar_widgets()
zi = app.zoom_label.info()
pi = app.page_label.info()
assert zi.get('side') == 'left' and pi.get('side') == 'left', '顶部模式二者应 side=left'
assert anchor_of(app.zoom_label) == 'e' and anchor_of(app.page_label) == 'e', '顶部模式应右对齐'
assert is_packed(app.zoom_label), '顶部模式倍率标签应被 pack'
print('[OK] 顶部模式: 倍率 side=%s, 页码 side=%s, 均 anchor=e(右对齐)' % (zi.get('side'), pi.get('side')))


# ===== 4) 左侧工具栏：倍率标签在页码上方，均居中，工具栏填满整列 =====
app.toolbar_pos = 'left'
app.layout()
zi = app.zoom_label.info()
pi = app.page_label.info()
ti = app.toolbar.pack_info()
assert zi.get('side') == 'bottom' and pi.get('side') == 'bottom', '左侧模式二者应 side=bottom'
assert anchor_of(app.zoom_label) == 'center' and anchor_of(app.page_label) == 'center', '左侧模式应居中'
assert str(ti.get('expand')) == '1', '左侧模式工具栏应 expand=1 填满整列'
print('[OK] 左侧模式: 倍率/页码 side=%s(均置底), anchor=center(居中), 工具栏 expand=%s' % (
    zi.get('side'), ti.get('expand')))


print('\n==== v13.8 逻辑验证全部通过 ====')
root.destroy()
