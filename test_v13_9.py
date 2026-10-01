"""v13.9 离线逻辑验证：CSV 阅读历史数据库 + 最近阅读菜单跳转（headless 真实 tkinter）。"""
import os, tempfile, tkinter as tk
import comic_viewer as cv

tmp = tempfile.mkdtemp()
csv_path = os.path.join(tmp, 'read_history.csv')

root = tk.Tk()
root.withdraw()
app = cv.ComicViewer(root)
# 把历史数据库重定向到临时文件，避免污染真实 %APPDATA%
app._history_path = lambda: csv_path
app._history = app._load_history()
# tk_popup 在 headless 下无窗口，置为 no-op 以便验证菜单构建不报错
tk.Menu.tk_popup = lambda self, x, y: None
print('[OK] ComicViewer 构造成功')


def reload_csv():
    d = {}
    if os.path.isfile(csv_path):
        import csv as _csv
        with open(csv_path, 'r', encoding='utf-8', newline='') as f:
            for row in _csv.DictReader(f):
                d[row['path']] = {'filename': row['filename'], 'last_page': int(row['last_page'])}
    return d


# ===== 1) 打开登记：仅新增，不覆盖已有进度 =====
app._record_open('/books/comicA.cbz')
h = reload_csv()
assert h['/books/comicA.cbz']['last_page'] == 1, h
print('[OK] 打开登记: 新条目 last_page=1，已写入 CSV')

app._history['/books/comicA.cbz']['last_page'] = 7   # 模拟已读到第 7 页
app._save_history()
app._record_open('/books/comicA.cbz')  # 再次打开，不应覆盖
h = reload_csv()
assert h['/books/comicA.cbz']['last_page'] == 7, '再次打开不应覆盖进度，实得 %r' % h
print('[OK] 再次打开不覆盖已有进度(仍为 7)')


# ===== 2) 翻页记录最后阅读页数 =====
app.archive_path = '/books/comicA.cbz'
app.index = 9
app._record_page()
h = reload_csv()
assert h['/books/comicA.cbz']['last_page'] == 10, '翻到第10页应记录 10，实得 %r' % h
print('[OK] 翻页记录: 第10页 -> last_page=10')


# ===== 3) 最近顺序：末尾为最近阅读 =====
app._record_open('/books/comicB.cbz')
app.archive_path = '/books/comicB.cbz'; app.index = 2; app._record_page()  # B 最近活动
app.archive_path = '/books/comicA.cbz'; app.index = 4; app._record_page()  # A 最近活动
order = list(app._history.keys())
assert order[-1] == '/books/comicA.cbz', '最近阅读应排在末尾，实得 %r' % order
print('[OK] 最近顺序: 末尾=%s（最近阅读在前显示）' % order[-1])


# ===== 4) 打开最近阅读并跳转到最后阅读页 =====
class FakeArchive:
    def __init__(self, names):
        self._n = names
    def names(self):
        return self._n
app.open_path = lambda p: setattr(app, 'archive', FakeArchive(['p%d' % i for i in range(1, 9)])) or setattr(app, 'archive_path', p)
app.render = lambda: None  # 跳过真实渲染
app._history['/books/comicB.cbz'] = {'filename': 'comicB.cbz', 'last_page': 3}
app._open_recent('/books/comicB.cbz')
assert app.index == 2, '应跳转到最后阅读页(3) -> index=2，实得 %r' % app.index
assert app._history['/books/comicB.cbz']['last_page'] == 3, '跳转后进度仍为 3'
print('[OK] 打开最近阅读并跳转: index=%d (第3页)' % (app.index + 1))


# ===== 5) 右键菜单构建（含“打开最近阅读漫画”）不报错 =====
class Ev:
    x_root = 0; y_root = 0
try:
    app._show_context(Ev())
    print('[OK] 右键菜单构建成功（含“打开最近阅读漫画”级联）')
except Exception as ex:
    raise AssertionError('右键菜单构建异常: %r' % ex)


print('\n==== v13.9 逻辑验证全部通过 ====')
root.destroy()
