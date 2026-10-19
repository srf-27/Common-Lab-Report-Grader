# 界面规范与 HIG 对照

> **状态：旧版存档。** 当前前端已按 HIG 重新实现（纯 CSS 令牌 + 自写组件，见 README「界面规范」一节）；本文记录的是上一版 HeroUI 实现的对照数据，仅供追溯。

本项目的界面按 Apple《人机界面指南》重写。本文记录**每一处关键改动对应的指南条款**，以及可复核的量化结果（对比度、断点、点击区域）。

参考页面：

- [人机界面指南总览](https://developer.apple.com/cn/design/human-interface-guidelines/)
- [布局 layout](https://developer.apple.com/cn/design/human-interface-guidelines/layout)
- [字体排印 typography](https://developer.apple.com/cn/design/human-interface-guidelines/typography)
- [颜色 color](https://developer.apple.com/cn/design/human-interface-guidelines/color)
- [按钮 buttons](https://developer.apple.com/cn/design/human-interface-guidelines/buttons)
- [边栏 sidebars](https://developer.apple.com/cn/design/human-interface-guidelines/sidebars)
- [文本栏 text-fields](https://developer.apple.com/cn/design/human-interface-guidelines/text-fields)
- [无障碍 accessibility](https://developer.apple.com/cn/design/human-interface-guidelines/accessibility)

---

## 1. 设计令牌

### 1.1 文本样式（typography）

`1rem = 17px`（`html { font-size: 106.25% }`，保留浏览器字号缩放），字号全部用 rem，布局用 px，用户放大字号时只放大文字。

| 令牌 | 点值 | 用途 | 指南依据 |
|---|---|---|---|
| `--type-large-title` | 34 | 页面标题 | 大标题样式 |
| `--type-title1` | 28 | 指标数字、紧凑模式页标题 | 标题 1 |
| `--type-title2` | 22 | 进度数字、块内大标题 | 标题 2 |
| `--type-title3` | 20 | 分组标题 | 标题 3 |
| `--type-headline` / `--type-body` | 17 | 行标题 / 正文 | 标题、正文（iOS 默认 17 点） |
| `--type-callout` | 16 | 次级信息 | 标注 |
| `--type-subhead` | 15 | 列表副标题、控件文字 | 副标题 |
| `--type-footnote` | 13 | 说明、元信息 | 脚注 |
| `--type-caption1/2` | 12 / 11 | 徽章、极小标注 | 说明 1/2（11 点为最小字号） |

字重只用 regular / 500 / 600 / 700，不用细体（指南：避免极细、纤细、细体）。行高：标题 1.25、正文 1.45、长文 1.62；正文段落最大宽度 `68ch`（可读宽度）。

### 1.2 语义色（color）

不直接写品牌色，而是按用途取语义令牌，深浅两套自动切换：

| 令牌 | 浅色 | 深色 | 对应系统色 |
|---|---|---|---|
| `--bg-grouped` | `#f2f2f7` | `#000000` | systemGroupedBackground |
| `--bg-elevated` | `#ffffff` | `#1c1c1e` | secondarySystemGroupedBackground |
| `--bg-field` | `#ffffff` | `#2c2c2e` | 文本栏背景 |
| `--label` | `#1d1d1f` | `#f5f5f7` | label |
| `--label-2` | `#6c6c70` | `#aeaeb2` | secondaryLabel |
| `--label-3` | `#8e8e93` | `#8e8e93` | tertiaryLabel（仅图标/装饰） |
| `--separator` | `rgba(60,60,67,.29)` | `rgba(84,84,88,.6)` | separator |
| `--accent` | `#0066cc` | `#4da3ff` | link / 强调色 |
| `--accent-fill` | `#0066cc` | `#0a84ff` | 填充按钮背景 |

- 强调色只用于**链接、选中态、主操作**，同一视图的主按钮不超过一个（buttons：保留一到两个突出按钮）。
- 状态不只靠颜色：所有状态徽章都是「圆点 + 文字」，等级标签同时有字母与底色（color/accessibility：避免仅依靠颜色）。
- 深色模式与 `prefers-contrast: more` 都有独立令牌覆盖（color：浅色/深色/增强对比度都要协调）。

### 1.3 尺寸与栅格（layout）

8pt 栅格：`4 / 8 / 12 / 16 / 24 / 32 / 40 / 48`；分组圆角 12、控件圆角 10；内容最大宽度 1060px；边栏 248px；最小点击区域 44×44。

---

## 2. 导航（sidebars / layout）

| 改动 | 依据 |
|---|---|
| 常规宽度（>700px）固定左侧边栏，分「评阅 / 设置」两组，最多两层 | sidebars：通常不超过两层，用简洁描述性标签分组 |
| 当前项用 `aria-current="page"` + 强调色浅底 | sidebars：选中项与图标使用强调色 |
| 边栏底部只放状态指示（细则/插件），不放关键操作 | sidebars（macOS）：避免把关键信息或操作放在边栏底部 |
| 紧凑宽度（≤700px）切换为底部标签栏，5 项以内，第 5 项为「更多」 | layout：iPadOS「尽可能推迟切换至紧凑视图」；tab bars 最多 5 项 |
| 「更多」用底部面板承载插件、配置、课程切换 | 模态面板用于次级入口，主流程仍留在标签栏 |
| 每页标题上方保留面包屑（工作台 / 报告管理 / 详情） | layout：项目放置传达相对重要性，阅读顺序自上而下 |

切换点在 700px：834（iPad 11" 竖排，常规宽度）仍是边栏；390（iPhone）为标签栏。实测 834/768/701/700/520/390 六个宽度均无页面级横向滚动（`scrollWidth == clientWidth`）。

---

## 3. 页面结构（layout）

| 改动 | 依据 |
|---|---|
| 页面标题：大标题 34 + 副标题 15，副标题限宽 68ch | typography：用字号/字重/颜色表达层级；可读宽度 |
| 内容改为「分组卡片」（白底、12 圆角、发丝线分隔），去掉投影 | layout：用背景形状、分隔线表达分组；控制与内容区分开 |
| 行高 ≥44，行间用 1px 分隔线且左侧内缩 | layout：对齐与缩进传达层级；accessibility：控制尺寸与间距 |
| 工作台三步卡片，主按钮统一贴底对齐 | layout：将组件互相对齐，便于浏览 |
| 长内容（维度、报告、名册、配置、一致性分析）默认折叠，摘要行 ≥44 | layout：渐进显示，提示还有更多内容 |
| 摘要行右侧统一用 45° 折角箭头表示可展开 | 与系统 disclosure 一致的视觉语言 |

---

## 4. 控件（buttons / segmented-controls / text-fields / toggles）

### 4.1 按钮

- 三种层级：`filled`（主操作，强调色填充）、`tinted`（次级，浅色底）、`bordered / plain`（三级，无填充）。
- 每个视图只保留一个 `filled`；下载、返回、筛选等用 `bordered` / `plain`。
- 所有按钮最小高度 44（`--tap`）；`small` 视觉 34，用 `::after { inset: -5px }` 把点击区域补到 44。
- 破坏性操作用 `destructive`（红底红字），不分配给主按钮角色（buttons：不要把主要角色给破坏性操作）。
- 加载态显示 14px 环形指示并加 `aria-busy`（buttons/iOS：按钮内显示活动指示符）。

### 4.2 分段控制

- 评分结果的 7 个状态筛选由「胶囊 chip」改为分段控制（`role=group` + `aria-pressed`），可横向滚动。
- 未选中文字使用专门令牌 `--label-on-fill`（浅色 `#56565b`），保证在浅灰底上仍 ≥4.5:1。

### 4.3 文本栏

- 每个输入都有可见标签（`<label for>`），标签 13 点灰色，与输入框 6px 间距（text-fields：占位符不能代替标签）。
- 占位符只放示例值；密钥框 `type=password` + `autocomplete=off`，占位符显示「已配置 / 未配置」（text-fields：安全文本栏）。
- 输入框最小高度 44；聚焦时 1px 强调色边框 + 3px 外发光，替代浏览器默认轮廓。
- 多栏表单按 260px 自适应列宽，窄屏单列（text-fields：多个文本栏应均匀间隔、垂直叠放）。

### 4.4 开关与选择

- 布尔项（机械判决、全选）用开关样式（`toggles`），点击区域由 44 高的 label 承担。
- 校准打分的 A–E 用 5 个 48×44 的方块选择组，选中态同时改变底色与字重（不只靠颜色）。

### 4.5 上传区

- 虚线框整体是可点击区域（`label` 包裹 `input[type=file]`），最小高 140。
- 选择文件后出现「已选择 / 已上传 + 大小 + 移除」的紧凑行；上传过程有真实字节进度条与取消按钮。

---

## 5. 无障碍（accessibility）

| 措施 | 依据 |
|---|---|
| 正文对比度全部 ≥4.5:1，大字/粗体 ≥3:1；**实测 8 个页面 × 浅色/深色 = 0 处不达标** | accessibility：WCAG AA 对比度表 |
| 所有可交互元素有 `:focus-visible` 3px 强调色焦点环 | 全键盘控制 |
| `skip-link` 跳到主内容，`main tabindex="-1"` | 键盘与屏幕阅读器导航 |
| 语义结构：`aside[aria-label]`、`nav[aria-label]`、`main`、`caption`（表格）、`fieldset/legend` | 旁白：为界面与内容提供描述 |
| 异步更新（进度、筛选计数、插件测试、OCR 自检）标 `role=status` / `aria-live=polite` | 状态变化需要被播报 |
| 进度条用 `role=progressbar` + `aria-valuenow` | 可感知的进度信息 |
| 图表/状态不使用颜色作为唯一线索（圆点 + 文字、字母 + 底色） | 不只通过颜色传达信息 |
| `prefers-reduced-motion` 关闭动画与平滑滚动 | 减弱动态效果 |
| `prefers-contrast: more` 提高文字与分隔线对比度 | 增强对比度 |
| 密码框、图标按钮均有可读名称（`aria-label`） | 语音控制与旁白 |

对比度审计方法：在无头 Chrome 中遍历带文本的元素，向上合成实际背景色（含半透明），按 WCAG 相对亮度公式计算比值，字号 ≥24 或 ≥18.66 且粗体按 3:1 判定。结果：浅色 8 页、深色 8 页均为 0 处不达标。

点击区域审计：`a/button/input/select/textarea/summary/switch/choice` 的最小高度均 ≥34（小按钮由伪元素补到 44，开关由 44 高的 label 承担），主按钮、导航项、列表摘要行均 ≥44。

---

## 6. 逐页改动对照

| 页面 | 关键改动 | HIG 依据 |
|---|---|---|
| 工作台 | 大标题 + 三步分组卡片 + 指标行；主按钮贴底；阶段移到边栏/紧凑结构顶部 | layout（分组、对齐、层级）、typography（大标题） |
| 评分细则 | 由横向宽表改为「每个维度一张折叠卡 + 五级并排」；字段带标签；机械判决用开关；校验告警用带图标提示条 | layout（渐进显示、可读宽度）、text-fields、toggles |
| 报告管理 | 由数据表改为分组列表：标题/学生/元信息/状态+操作；顶部搜索栏 + 下载工具条 | layout（分组与对齐）、search fields、buttons |
| 选择评分 | 每个学生一组，行内复选框 + 状态；未识别学生合并为一组；全选为开关 | list selection、toggles |
| 评分结果 | 状态筛选改分段控制；报告为可展开行；维度改为「说明 + 右侧等级/评语」两栏；终审/打回为行内工具条 | segmented-controls、layout、buttons |
| 维度详情 | 每个维度折叠卡，级别用字母徽章；图片网格 + 图注；原文为嵌套折叠 | layout（渐进显示）、images |
| 花名册 | 四个指标 + 四个折叠分组；编辑表表头即列名（右侧 × 删除列、二次确认），列宽与正文对齐，横向滚动时「操作」列吸附在左侧；可疑/缺交分表 | layout、text-fields、accessibility（≥44 触控、sticky） |
| 配置 | 三个分组卡片，字段 260px 自适应；协议切换只显示相关字段；密钥占位提示；OCR 自检结果用状态文本 | text-fields、layout、progressive disclosure |
| 插件 | 挂载表 + 字段表单；测试连接结果就地显示；添加插件为折叠区 | layout、buttons |
| 校准打分/结果 | 每维度一组，等级用方块选择组；分歧用带图标提示条 | segmented-controls、color |

---

## 7. 取舍与限制

- HIG 面向原生控件，Web 没有 Liquid Glass、Dynamic Type 的系统级支持；这里用语义色令牌、rem 字号和 `prefers-*` 媒体查询近似，无法做到系统级 Dynamic Type 全档位联动。
- 底部标签栏在桌面浏览器里不如原生自然，因此只在 ≤700px 出现；桌面保留边栏。
- 行内文字链接（面包屑、表格内链接）不强行做到 44×44，因为它们是文本流的一部分，指南的 44 点要求针对控件。
- 分段控制 7 项超出常见的 2–5 项建议，但筛选维度由业务决定；采用可横向滚动 + `aria-pressed` 保证可用性。
