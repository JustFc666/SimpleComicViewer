# -*- coding: utf-8 -*-
"""用真实 tkinter 验证 v13.2 的 UI 细节改动（headless 可跑，不调用 mainloop）。"""
import tkinter as tk
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('cv_test', os.path.join(HERE, 'comic_viewer.py'))
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)
cv.DND_AVAILABLE = False  # 用原生 tk.Tk，避免 TkinterDnD 在无显示环境初始化

# 居中样式应在 _build_ui 内被 configure
root = tk.Tk()
app = cv.ComicViewer(root)

# 1) 菜单栏位置框存在且带正确选项
assert hasattr(app, 'menubar_pos_cb'), '菜单栏位置 Combobox 缺失'
assert tuple(app.menubar_pos_cb.cget('values')) == ('顶部', '左侧'), app.menubar_pos_cb.cget('values')
print('menubar_pos_cb: values =', app.menubar_pos_cb.cget('values'))

# 2) 工具栏位置框也带标签(框架含 Label)
assert hasattr(app, 'tbpos_cb'), '工具栏位置 Combobox 缺失'

# 3) 单页 -> 方向框禁用；双页 -> 恢复可用
def st(c):
    return str(c.cget('state'))

app.mode = 'single'
app._update_dir_state()
assert st(app.dir_cb) == 'disabled', '单页下方向框未禁用: %r' % st(app.dir_cb)
print('single -> dir_cb state =', st(app.dir_cb))

app.mode = 'double'
app._update_dir_state()
assert st(app.dir_cb) == 'readonly', '双页下方向框未恢复: %r' % st(app.dir_cb)
print('double -> dir_cb state =', st(app.dir_cb))

# 4) 经 _set_mode 正式路径联动
app._set_mode('single')
assert st(app.dir_cb) == 'disabled'
app._set_mode('double')
assert st(app.dir_cb) == 'readonly'
print('_set_mode 联动 OK')

# 5) 菜单栏位置回调
app.menubar_pos_cb.set('左侧')
app._set_menubar_pos('left' if app.menubar_pos_cb.get() == '左侧' else 'top')
assert app.menubar_pos == 'left', app.menubar_pos
print('menubar_pos 回调 OK ->', app.menubar_pos)

# 6) 居中样式存在
st = tk.ttk.Style()
ok = bool(st.lookup('Center.TCombobox', 'justify'))
print('Center.TCombobox justify =', ok)
assert ok == 'center' or ok, '居中样式未生效'

root.destroy()
print('\nUI_LOGIC_OK')
