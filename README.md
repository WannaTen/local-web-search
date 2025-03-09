# 本地网页搜索工具 (Local Web Search)

这是一个用Python实现的本地网页搜索工具，它能够执行网络搜索并提取搜索结果的内容。该工具使用浏览器自动化技术来模拟用户搜索行为，避免被搜索引擎检测为爬虫。

## 功能特点

- 使用Google搜索引擎执行网络搜索
- 自动提取搜索结果链接
- 访问链接并提取页面主要内容
- 可过滤特定域名
- 支持代理设置
- 可配置并发数量和最大结果数
- 支持内容截断

## 安装

### 前提条件

- Python 3.7+
- pip

### 安装步骤

1. 克隆仓库或下载源代码

```bash
git clone https://github.com/yourusername/local-web-search-py.git
cd local-web-search-py
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 安装Playwright浏览器

```bash
playwright install chromium
```

## 使用方法

### 基本用法

```bash
python local_web_search.py search -q "你的搜索查询"
```

### 命令行参数

- `-q`, `--query`: 搜索查询（必需）
- `-c`, `--concurrency`: 设置并发数量（默认：5）
- `--show`: 显示浏览器窗口
- `--max-results`: 每个查询的最大结果数（默认：10）
- `--exclude-domain`: 排除特定域名，可多次使用以排除多个域名
- `--truncate`: 截断页面内容的字符数
- `--proxy`: 使用代理，格式为"http://host:port"或"socks5://host:port"

### 示例

1. 基本搜索：

```bash
python local_web_search.py search -q "Python教程"
```

2. 排除特定域名：

```bash
python local_web_search.py search -q "Python教程" --exclude-domain youtube.com --exclude-domain reddit.com
```

3. 使用代理并显示浏览器：

```bash
python local_web_search.py search -q "Python教程" --proxy "http://127.0.0.1:8080" --show
```

4. 限制结果数量并截断内容：

```bash
python local_web_search.py search -q "Python教程" --max-results 5 --truncate 1000
```

## 输出格式

该工具以JSON格式输出结果。每次搜索会输出两次结果：

1. 第一次输出包含搜索结果的链接信息（不含内容）
2. 第二次输出包含完整的搜索结果，包括链接和页面内容

## 原理

该工具使用以下技术：

- **Playwright**：用于浏览器自动化
- **Readability**：用于提取网页的主要内容
- **BeautifulSoup**：用于HTML解析
- **html2text**：用于将HTML转换为Markdown
- **Click**：用于构建命令行接口

## 注意事项

- 该工具仅供学习和研究目的使用
- 过度或不当使用可能违反搜索引擎的服务条款
- 建议设置合理的并发数和请求间隔，避免IP被封禁

## 许可证

MIT
