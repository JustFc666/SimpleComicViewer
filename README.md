# ComicViewer

本地漫画压缩文档浏览器（Python / tkinter）。支持多种压缩格式与图片文件夹，**自包含**——`rar`/`cbr` 由内置的 7-Zip 解压，无需在系统里另行安装 7-Zip 即可使用。

> 当前版本：**v13.10**（发布包与源码已同步至本项目）

---

## 功能特性

- **多格式支持**：`zip` / `7z` / `rar` / `cbz` / `cbr` / `cb7`，以及常见图片（`jpg` / `png` / `gif` / `webp` 等）和图片文件夹。
- **自包含解压**：`rar` / `cbr` 通过内置 7-Zip（`7z.exe` + `7z.dll`）解压，打包时一并打入产物，零外部依赖。
- **拖拽打开**：可直接把漫画压缩包或图片拖到浏览页面打开。
- **单页 / 双页显示**，可切换阅读方向（左→右 / 右→左）。
- **图片旋转**：工具栏下拉框支持 `不旋转` / `逆时针90°` / `旋转180°` / `顺时针90°`（跨页持久）。
- **阅读记录**：工具栏「阅读记录」可查看已读漫画（文件名 / 阅读时间 / 页码 / 路径）；双击记录可直接打开并从最后阅读页继续；支持 `Shift` / `Ctrl` 多选后删除选中或全部；若原压缩包已删除，双击会提示「文件已删除」。
- **布局记忆**：工具栏位置（顶部 / 左侧）、缩放、方向、双页等设置自动记忆。
- **高 DPI 感知**：高分屏下大图不会被系统拉伸模糊。
- **全屏模式**。

## 快捷键

| 按键 | 功能 |
| --- | --- |
| 空格 / → / PageDown | 下一页 |
| BackSpace / ← / PageUp | 上一页 |
| Ctrl + = / - | 放大 / 缩小（每级 5%） |
| Ctrl + 鼠标滚轮 | 放大 / 缩小 |
| 鼠标滚轮 | 翻页（按住 Ctrl 为缩放） |
| W / H | 适应宽度 / 适应高度 |
| 1 / 2 | 单页 / 双页显示 |
| R | 切换阅读方向 |
| G | 跳转到指定页 |
| F / Esc | 全屏 / 退出全屏 |
| Home / End | 首页 / 末页 |

浏览页面右键可「隐藏 / 显示 信息栏」，并切换「工具栏位置」（顶部 / 左侧）。

---

## 下载与安装

### 方式一：下载发布版（推荐，开箱即用）

到本仓库 **Releases** 页面下载 `ComicViewer_v13.10.zip`，解压后得到文件夹 `ComicViewer_v13.10/`，双击其中的 `ComicViewer_v13.10.exe` 即可运行，**无需安装、无需 Python 环境**。

- 下载地址：<https://github.com/JustFc666/SimpleComicViewer/releases/download/v13.10/ComicViewer_v13.10.zip>
- 仓库 Releases：<https://github.com/JustFc666/SimpleComicViewer/releases>

### 方式二：从源码运行

```bash
# 1. 准备 Python 环境（建议 3.10+）
python -m venv buildenv
buildenv\Scripts\activate

# 2. 安装依赖
pip install Pillow py7zr tkinterdnd2

# 3. 运行
python comic_viewer.py
```

> 源码直接运行时，阅读记录 `reading_history.csv` 回退到 `%APPDATA%/ComicViewer/`；打包产物则落在 exe 同目录。

---

## 从源码打包（PyInstaller）

仓库内含三份打包规格（spec）：

| spec 文件 | 产物形态 | 说明 |
| --- | --- | --- |
| `ComicViewer_v13.spec` | 单文件 `ComicViewer_v13.10.exe` | 窗口版，双击即用 |
| `ComicViewer_v13_dbg.spec` | `ComicViewer_v13.10_dbg.exe` | 调试版（带控制台输出） |
| `ComicViewer_v13_onedir.spec` | 文件夹 `dist/ComicViewer_v13.10/` | 文件夹版，内置 `_internal/7z.exe` + `7z.dll` |

打包命令（以单文件版为例，调试版 / 文件夹版同理替换 spec 名）：

```bash
pyinstaller --noconfirm ComicViewer_v13.spec
```

- 需额外安装 `pyinstaller`（`pip install pyinstaller`）。
- `hook-tkinterdnd2.py` 用于把 `tkinterdnd2` 正确打入产物；`comic_viewer.ico` 为程序图标；`comic_viewer.ini` 为配置。
- `del_batch.py` 为辅助脚本，用于绕过批量删除守卫（清理旧构建产物时按小批量删除），日常使用无需它。

---

## 项目结构

```
ComicViewer/
├── comic_viewer.py            # 主程序
├── ComicViewer_v13.spec       # 单文件版打包规格
├── ComicViewer_v13_dbg.spec   # 调试版打包规格
├── ComicViewer_v13_onedir.spec# 文件夹版打包规格
├── hook-tkinterdnd2.py        # tkinterdnd2 打包 hook
├── requirements.txt           # 运行依赖（Pillow / py7zr）
├── comic_viewer.ico           # 程序图标
├── comic_viewer.ini           # 配置
├── del_batch.py               # 清理辅助脚本
└── test_*.py                  # 离线测试套件
```

---

## 作者

- 作者：Justin F.
- 邮箱：fc666@hotmail.com
- 版本：v13.10

---

## 许可证

本项目为私有仓库，仅供作者自用与分发。如需转载或二次分发，请联系作者。
