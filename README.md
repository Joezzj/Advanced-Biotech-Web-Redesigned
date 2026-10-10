# Advanced Biotech

四页英文企业网站。保留上一版的产品、方案、公司资料和交互功能，重新整理了排版与代码。所有图片、字体和脚本均随项目提供，不需要 npm、CDN 或外部字体服务。

## 打开网站

完整解压后，直接打开 `docs/index.html`。产品搜索、筛选、详情展开和邮件草稿都可在本地使用。

需要使用邮件接口时，安装 Python 3.10 或更新版本：

- Windows：双击 `start-preview.bat`。
- macOS / Linux：执行 `sh start-preview.sh`。
- 或在项目根目录执行 `python server.py`，打开 `http://127.0.0.1:8000`。

## 这次的调整

- 使用本地 Ubuntu 字体的四个字重，统一标题、正文、标签和表单的排版。
- 改用深蓝、青绿色与浅色背景，调整按钮、卡片、页脚和区块间距。
- 字号使用 rem，放大原先过小的辅助文字，保留手机断点和减少动态效果设置。
- HTML 直接作为页面源码，取消大段 Python 字符串生成页面的方式。
- 样式按公共部分和页面拆分；脚本按导航、产品目录和询盘职责拆分。
- 整理后端、测试和配置文件的命名、缩进与长表达式。

## 文件如何修改

| 文件 | 职责 |
|---|---|
| `docs/index.html` | 首页内容与结构 |
| `docs/products.html` | 全部产品、分类、详情及询问链接 |
| `docs/solutions.html` | 四大方案与应用案例 |
| `docs/contact.html` | 联系资料与表单 |
| `docs/style.css` | 字体、设计变量、公共控件、导航及页脚 |
| `docs/assets/css/home.css` | 首页样式 |
| `docs/assets/css/products.css` | 产品页样式 |
| `docs/assets/css/solutions.css` | 方案页样式 |
| `docs/assets/css/contact.css` | 联系页样式 |
| `docs/assets/css/responsive.css` | 断点、动态效果、无脚本和打印样式 |
| `docs/main.js` | 导航、焦点控制与年份 |
| `docs/assets/js/products.js` | 分类、关键词搜索、数量和 URL 状态 |
| `docs/assets/js/contact.js` | 表单校验、邮件草稿、复制和 API 提交 |
| `docs/site-config.js` | 静态部署的邮件接口设置 |
| `docs/assets/images/` | 本地图片、Logo 与图标 |
| `docs/assets/fonts/` | 本地字体及许可 |
| `server.py` | 静态文件服务和可选 SMTP 接口 |
| `scripts/prepare_static.py` | 将 `docs/` 原样复制到 `dist/`，供静态发布 |
| `tests/` | 后端、前端事件及内容完整性测试 |
| `tests/fixtures/content.json` | 原产品和方案文字的回归基准；不是页面生成源 |

修改文字直接编辑对应 HTML；修改样式编辑对应 CSS。四页的页头和页脚分别保存在各自 HTML 中，调整公共链接时需要同步四页。没有生成脚本会覆盖 HTML 修改。

产品卡片的 `id`、`data-product`、`data-category`，筛选按钮的 `data-filter`，以及表单字段的 `name` / `id` 是脚本使用的接口。仅修改显示文字时保留这些属性。需要主动修改业务内容时，同步调整测试基准，否则内容检查会提示差异。

## 保留的内容与功能

四页文件名、全部 12 类产品、四大解决方案及应用案例、技术原理、首页统计、Logo、邮箱、Auckland 地址和 `CNAME` 均保留。产品和方案文字沿用提供的版本，没有新增客户、认证或测试数据。

保留分类筛选、多关键词搜索、清空与无结果状态、产品锚点、URL 参数、询问链接自动填入、原生详情展开、手机菜单、Escape / 焦点循环、跳过导航和表单状态播报。关闭 JavaScript 时，页面内容、链接和详情展开仍可使用。

## 联系表单

### 静态部署

默认按钮为 **Prepare email enquiry**。填写后生成邮件草稿，点击 **Open email draft** 后由访客在邮件软件中发送；也可以复制询盘文字。剪贴板不可用时，页面显示可手动复制的文本框。

生成草稿不会发送邮件，页面会明确说明。静态预览使用这种模式。

### 直接发送

复制 `.env.example` 为根目录的 `.env`，填写新的有效配置：

```dotenv
SMTP_HOST=your-smtp-host
SMTP_PORT=465
SMTP_SECURITY=ssl
SMTP_USER=your-smtp-account
SMTP_PASSWORD=your-app-password
MAIL_FROM=your-verified-sender-address
MAIL_TO=info@advancedbiotech.co.nz
```

重启 `python server.py`。完整配置启用后，服务器提供同源 `/api/contact`，按钮自动变为 **Send enquiry**。STARTTLS 使用 `SMTP_SECURITY=starttls`，端口按邮件服务商提供的设置填写。

仅在 SMTP 接受邮件后显示成功；这不代表收件箱已收到或已阅读。失败和超时会保留内容并提供邮件草稿。`/send_mail` 兼容接口仍保留。

`.env` 留在 `docs/` 外，已被 Git 忽略。前后端分离时，可在 `docs/site-config.js` 配置 HTTPS 接口，并在服务器 `ALLOWED_ORIGINS` 列出前端完整来源。不要将邮件凭据写入前端代码。

## 发布与检查

静态网站只发布 `docs/`，或者执行 `python scripts/prepare_static.py` 后发布 `dist/`。`CNAME` 沿用原域名设置，可按托管平台要求调整。直接邮件服务需要另行运行 Python 后端；静态托管不会执行 `server.py`。

执行回归检查：

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python tests/audit_site.py
node tests/test_frontend.cjs
```

本次 20 项后端测试、57 项前端事件断言及 364 项静态检查通过，全部四页可见文字也与上传版本比对一致。测试包含新拆分的样式、脚本和字体资源。

当前环境未完成真实浏览器渲染及手机触控验收；真实 SMTP 也未发送测试邮件。前端测试验证事件与状态，不替代浏览器视觉检查。详见 `QA_REPORT.md`。
