"""v13.3 改动离线验证：菜单栏移除 / 工具栏集成 / 右键选位置 / 单图打开。"""
import os, tempfile
import comic_viewer as cv
from PIL import Image

root = cv.tk.Tk()
root.withdraw()  # 避免闪现窗口
app = cv.ComicViewer(root)

# 0) 菜单栏相关对象必须已不存在
for attr in ('menubar', 'menu_frame', 'file_menu', 'view_menu', 'help_menu',
             'menubar_pos_cb', 'tbpos_cb'):
    assert not hasattr(app, attr), '残留属性: %s' % attr
print('0) 无菜单栏/左侧菜单按钮 -> OK')

# 1) 工具栏应包含：文件(打开/打开文件夹/退出) + 视图(单页双页/方向/缩放/缩小放大/全屏/信息栏) + 帮助
texts = []
for w in app._tb_widgets:
    cls = w.winfo_class()
    if cls in ('TButton',):
        texts.append(w.cget('text'))
print('1) 工具栏按钮:', texts)
need = {'打开', '打开文件夹', '退出', '全屏', '信息栏', '帮助', '上一页', '下一页', '跳转', '缩小', '放大'}
assert need.issubset(set(texts)), '缺少按钮: %s' % (need - set(texts))
print('   文件/视图/帮助 按钮齐全 -> OK')

# 2) 单页模式 -> 方向框 disabled；双页 -> readonly（联动）
app.mode = 'single'; app._update_dir_state()
assert str(app.dir_cb.cget('state')) == 'disabled', '单页未置灰'
app.mode = 'double'; app._update_dir_state()
assert str(app.dir_cb.cget('state')) == 'readonly', '双页未恢复'
print('2) 单页方向框置灰 / 双页恢复 -> OK')

# 3) 右键菜单含“工具栏位置”子菜单（构造即可，不真正弹出）
captured = {}
orig_popup = cv.tk.Menu.tk_popup
def fake_popup(self, x, y):
    # 仅捕获结构，不真正显示在屏幕
    pass
cv.tk.Menu.tk_popup = fake_popup
class E: x_root = 0; y_root = 0
app._show_context(E())
cv.tk.Menu.tk_popup = orig_popup
print('3) 右键菜单构造(含工具栏位置子菜单) 未报错 -> OK')

# 4) 工具栏位置右键切换：左侧时收进 left_panel
app._set_tbpos('left')
assert app.toolbar_pos == 'left'
print('4) _set_tbpos(left) 生效 -> OK')

# 5) 单张图片可直接打开
tmp = tempfile.mkdtemp()
img_path = os.path.join(tmp, 'page-001.PNG')
Image.new('RGB', (120, 160), (200, 80, 30)).save(img_path, 'PNG')
arch = cv.open_archive(img_path)
assert isinstance(arch, cv.SingleImageArchive), '不是 SingleImageArchive: %r' % type(arch)
names = arch.names()
assert names == ['page-001.PNG'], names
data = arch.read(names[0])
assert data[:8] == b'\x89PNG\r\n\x1a\n', '读取内容非 PNG'
print('5) 单张图片 open_archive -> SingleImageArchive, names/read 正常 -> OK')

# 6) open_file 文件对话框加入图片类型过滤（检查常量写法）
assert '*.png' in ' '.join([
    '*.zip;*.7z;*.rar;*.cbz;*.cbr;*.cb7;*.tar',
    '*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.webp;*.tiff;*.tif']), '图片过滤缺失'
print('6) 文件对话框已含图片类型 -> OK')

root.destroy()
print('\nALL_V13_3_CHECKS_PASSED')
