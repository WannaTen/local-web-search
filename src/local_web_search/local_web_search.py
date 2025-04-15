#!/usr/bin/env python3
import os
import sys
import json
import tempfile
import asyncio
from typing import List, Dict, Optional, Any, Set
from urllib.parse import urlparse, urlencode

import click
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

# 修复 lxml 依赖问题
try:
    from readability import Document
except ImportError as e:
    if "lxml.html.clean" in str(e):
        print("错误: lxml.html.clean 模块现在是一个独立项目。")
        print("请运行以下命令安装缺失的依赖:")
        print("pip install lxml[html_clean] 或 pip install lxml_html_clean")
        sys.exit(1)
    else:
        raise

import html2text
import platform
from pathlib import Path
import logging

# 设置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 定义类型
class SearchResult:
    def __init__(self, title: str, url: str, content: Optional[str] = None):
        self.title = title
        self.url = url
        self.content = content
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content
        }

# 浏览器查找功能
def find_browser(browser_name=None):
    """查找本地安装的浏览器"""
    system = platform.system().lower()
    home_dir = os.path.expanduser('~')
    
    # 定义浏览器查找路径
    browsers = {
        "chrome": {
            "windows": [
                os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Google\\Chrome\\Application\\chrome.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Google\\Chrome\\Application\\chrome.exe')
            ],
            "darwin": [
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                f'{home_dir}/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            ],
            "linux": [
                '/usr/bin/google-chrome',
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium'
            ]
        },
        "edge": {
            "windows": [
                os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Microsoft\\Edge\\Application\\msedge.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Microsoft\\Edge\\Application\\msedge.exe')
            ],
            "darwin": [
                '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                f'{home_dir}/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
            ],
            "linux": [
                '/usr/bin/microsoft-edge',
                '/usr/bin/microsoft-edge-stable'
            ]
        }
    }
    
    # 默认使用Chrome，除非指定了其他浏览器
    browser_type = browser_name.lower() if browser_name else "chrome"
    if browser_type not in browsers:
        browser_type = "chrome"  # 默认回退到Chrome
    
    # 查找浏览器路径
    for path in browsers[browser_type].get(system, []):
        if os.path.exists(path):
            return path
    
    # 如果找不到指定的浏览器，尝试查找任何可用的浏览器
    if browser_type != "chrome":
        for path in browsers["chrome"].get(system, []):
            if os.path.exists(path):
                return path
    
    # 如果还是找不到，抛出异常
    raise Exception(f"未找到本地安装的浏览器: {browser_type}")

# 浏览器相关功能
async def launch_browser(show: bool = False, proxy: Optional[str] = None, 
                         browser: Optional[str] = None, profile_path: Optional[str] = None) -> Dict[str, Any]:
    """启动浏览器并返回浏览器实例及相关方法"""
    p = await async_playwright().start()
    
    # 设置浏览器启动参数
    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-web-security"
    ]
    
    # 处理配置文件路径
    if profile_path:
        profile_dir = os.path.dirname(profile_path)
        profile_name = os.path.basename(profile_path)
        user_data_dir = profile_dir
        browser_args.append(f"--profile-directory={profile_name}")
    else:
        user_data_dir = os.path.join(tempfile.gettempdir(), "local-web-search-python")
        
    # 找到本地浏览器的路径
    try:
        executable_path = find_browser(browser)
        logging.info(f"local web browser: {executable_path}")
    except Exception as e:
        logging.info(f"warning: {str(e)}, use playwright built-in chromium")
        executable_path = None
        
    # 启动浏览器上下文
    browser_context = await p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=not show,
        executable_path=executable_path,  # 这里使用找到的本地浏览器路径
        args=browser_args,
        ignore_default_args=["--enable-automation"],
        viewport={"width": 1280, "height": 720},
        device_scale_factor=1,
        locale="en-US",
        accept_downloads=False,
        bypass_csp=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/237.84.2.178 Safari/537.36",
        ignore_https_errors=True,
        proxy={"server": proxy} if proxy else None
    )
    
    # 返回浏览器相关方法
    async def close():
        """关闭浏览器"""
        for page in browser_context.pages:
            await page.close()
        logging.info(f"close browser")
        await browser_context.close()
        logging.info(f"close browser context")
        await p.stop()
    
    async def with_page(fn):
        """使用页面执行函数"""
        page = await browser_context.new_page()
        try:
            await apply_stealth_scripts(page)
            await intercept_requests(page)
            logging.info(f"apply stealth scripts")
            result = await fn(page)
            await page.close()  # 这里只关闭页面
            logging.info(f"close page")
            return result
        except Exception as e:
            await page.close()
            logging.info(f"close page")
            raise e
    
    return {
        "close": close,
        "with_page": with_page
    }

async def apply_stealth_scripts(page: Page):
    """应用反爬虫脚本"""
    await page.add_init_script("""
    () => {
        // 隐藏WebDriver属性
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // 模拟语言和插件
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        // 重定义headless属性
        Object.defineProperty(navigator, 'headless', {
            get: () => false
        });
        
        // 重写permissions API
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => 
            parameters.name === 'notifications' 
                ? Promise.resolve({ state: Notification.permission }) 
                : originalQuery(parameters);
    }
    """)

async def intercept_requests(page: Page):
    """拦截请求，只允许文档请求通过"""
    await page.route("**/*", lambda route: 
        route.continue_() if route.request.resource_type == "document" 
        else route.abort()
    )

# 搜索结果提取功能
async def get_search_page_links(page: Page) -> List[SearchResult]:
    """从Google搜索结果页面提取链接"""
    return await page.evaluate("""
    () => {
        const links = [];
        const document = window.document;

        const isValidUrl = (url) => {
            // Basic check, can be improved
            return url && (url.startsWith('http://') || url.startsWith('https://'));
        };

        try {
            // Try selecting result blocks more generally. Google often uses divs directly under #search or #rso.
            // Let's try finding divs that contain both an h3 and an a[href].
            const resultsContainer = document.querySelector('#search') || document.querySelector('#rso') || document.body; // Fallback to body
            const candidates = Array.from(resultsContainer.querySelectorAll('div')); // Consider direct children or more specific divs if needed

            candidates.forEach(element => {
                // Find the first link and h3 within this div. Be mindful that structure might vary.
                const linkElement = element.querySelector('a[href]');
                const titleElement = element.querySelector('h3');

                if (linkElement && titleElement) {
                    const url = linkElement.getAttribute('href');
                    const title = titleElement.textContent || "";

                    // Further checks: ensure it's a plausible result link
                    // Avoid internal links, related searches, fragments etc.
                    if (url && isValidUrl(url) && title && url.startsWith('http') && !url.includes('google.com/') && !url.startsWith('#')) {

                        // Check if we've already added a very similar URL (e.g., http vs https, slight param diffs)
                        let urlObj;
                        try {
                            urlObj = new URL(url);
                        } catch (e) {
                            // If URL is invalid, skip
                            console.error(`Invalid URL encountered: ${url}`);
                            return;
                        }
                        const simplifiedUrl = urlObj.hostname + urlObj.pathname;
                        const alreadyExists = links.some(l => {
                            try {
                                const existingUrlObj = new URL(l.url);
                                return (existingUrlObj.hostname + existingUrlObj.pathname) === simplifiedUrl;
                            } catch { return false; } // Ignore errors comparing potentially invalid existing URLs
                        });

                        if (!alreadyExists) {
                            links.push({ title: title.trim(), url: url });
                        }
                    }
                }
            });

            // Fallback if the general approach yields no results
            if (links.length === 0) {
                 console.log("Primary selector logic failed, trying fallback class selectors...");
                 // Example fallback selectors (these WILL change frequently and need updates)
                 // Combine common older and newer patterns observed over time. Inspect page source for current ones.
                 document.querySelectorAll('div.g, div.Gx5Zad, div.DhN8Cf, div.tF2Cxc, [data-hveid]').forEach(element => { // Added [data-hveid] as another potential container attribute
                     const linkElement = element.querySelector('a[href]');
                     const titleElement = element.querySelector('h3');

                     if (linkElement && titleElement) {
                         const url = linkElement.getAttribute('href');
                         const title = titleElement.textContent || "";
                         if (url && isValidUrl(url) && title && url.startsWith('http') && !url.includes('google.com/') && !url.startsWith('#')) {
                             let urlObj;
                             try {
                                 urlObj = new URL(url);
                             } catch (e) {
                                 console.error(`Invalid URL encountered in fallback: ${url}`);
                                 return;
                             }
                             const simplifiedUrl = urlObj.hostname + urlObj.pathname;
                             const alreadyExists = links.some(l => {
                                try {
                                    const existingUrlObj = new URL(l.url);
                                    return (existingUrlObj.hostname + existingUrlObj.pathname) === simplifiedUrl;
                                } catch { return false; }
                             });
                             if (!alreadyExists) {
                                 links.push({ title: title.trim(), url: url });
                             }
                         }
                     }
                 });
            }

        } catch (error) {
            console.error('Error extracting links:', error);
        }

        // Limit the number of results explicitly here if needed, although search URL param 'num' should handle it.
        // return links.slice(0, 10); // Example limit if too many irrelevant results are caught

        return links;
    }
    """)

def should_skip_domain(url: str) -> bool:
    """判断是否应该跳过某些域名"""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        skip_domains = [
            "reddit.com",
            "www.reddit.com",
            "x.com",
            "twitter.com",
            "www.twitter.com",
            "facebook.com",
            "www.facebook.com",
            "instagram.com",
            "www.instagram.com",
            "youtube.com",
            "www.youtube.com"
        ]
        
        return hostname in skip_domains
    except:
        return True

def get_search_url(query: str, engine: str = "google", exclude_domains: List[str] = None, max_results: int = 10) -> str:
    """构建搜索URL，支持多个搜索引擎"""
    if exclude_domains is None:
        exclude_domains = []
    
    exclude_clause = " ".join([f"-site:{domain}" for domain in exclude_domains])
    search_query = f"{exclude_clause} {query}" if exclude_domains else query
    
    if engine.lower() == "bing":
        params = {
            "q": search_query,
            "count": str(max_results)
        }
        return f"https://www.bing.com/search?{urlencode(params)}"
    elif engine.lower() == "duckduckgo":
        params = {
            "q": search_query
        }
        return f"https://duckduckgo.com/?{urlencode(params)}"
    else:  # 默认Google
        params = {
            "q": search_query,
            "num": str(max_results),
            "udm": "14",  # web标签
            "lr": "lang_en"
        }
        return f"https://www.google.com/search?{urlencode(params)}"

async def extract_content(page: Page) -> Dict[str, str]:
    """提取页面内容，改进版"""
    # 等待页面加载完成
    try:
        # 等待主体内容加载
        await page.wait_for_selector("body", timeout=10000)
        
        # 尝试等待可能的动态内容加载
        await asyncio.sleep(2)
    except:
        pass
    
    # 获取页面内容
    content = await page.content()
    
    # 使用readability提取主要内容
    doc = Document(content)
    article_html = doc.summary()
    title = doc.title()
    
    # 删除不必要的元素（广告、导航等）
    soup = BeautifulSoup(article_html, 'html.parser')
    for selector in ['nav', '.ad', '.ads', '.advert', '.cookie-notice', '.popup', 'iframe']:
        for element in soup.select(selector):
            element.decompose()
    
    # 转换为纯文本
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0  # 不限制宽度
    text_content = converter.handle(str(soup))
    
    return {
        "title": title,
        "content": text_content
    }

# 主搜索功能
async def search(browser, query: str, max_results: int = 10, 
               exclude_domains: List[str] = None, 
               truncate: Optional[int] = None,
               visited_urls: Set[str] = None,
               concurrency: int = 5) -> Dict[str, Any]:
    """执行搜索并返回结果"""
    if visited_urls is None:
        visited_urls = set()
    
    if exclude_domains is None:
        exclude_domains = []
    
    # 构建搜索URL
    url = get_search_url(query, exclude_domains=exclude_domains, max_results=max_results)
    
    # 获取搜索结果链接
    links = await browser["with_page"](lambda page: _search_page(page, url))
    logging.info(f"search_page_links: {links}")
    if not links:
        return {"query": query, "results": []}
    
    # 过滤已访问链接和需要跳过的域名
    filtered_links = []
    for link in links:
        if link["url"] in visited_urls or should_skip_domain(link["url"]):
            continue
        visited_urls.add(link["url"])
        filtered_links.append(link)
    
    if not filtered_links:
        return {"query": query, "results": []}
    
    # 只在调试模式下输出初始搜索结果
    logger.debug(json.dumps({
        "query": query, 
        "results": filtered_links
    }, ensure_ascii=False))
    
    # 使用传入的concurrency参数创建信号量
    semaphore = asyncio.Semaphore(concurrency)
    
    async def process_link(link):
        async with semaphore:
            try:
                content = await browser["with_page"](lambda page: _visit_link_with_retry(page, link["url"]))
                if content and content.get("content"):
                    if truncate:
                        content["content"] = content["content"][:truncate]
                    return {**link, **content}
            except Exception as e:
                logger.debug(f"Error visiting {link['url']}: {str(e)}")
            return None
    
    # 使用asyncio.gather处理所有链接
    results = await asyncio.gather(*[process_link(link) for link in filtered_links])
    results = [r for r in results if r]  # 过滤掉None结果
    
    final_results = {
        "query": query,
        "results": results
    }
    
    # 只在调试模式下输出最终结果
    logger.debug(json.dumps(final_results, ensure_ascii=False))
    
    return final_results

async def _search_page(page: Page, url: str) -> List[Dict[str, str]]:
    """导航到搜索页并提取链接"""
    await page.goto(url, wait_until="domcontentloaded")
    links = await get_search_page_links(page)
    logger.info(f"Extracted links from {url}: {links}")
    return links

async def _visit_link_with_retry(page: Page, url: str, max_retries: int = 3) -> Dict[str, str]:
    """访问链接并提取内容，支持重试"""
    for attempt in range(max_retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return await extract_content(page)
        except Exception as e:
            if attempt == max_retries - 1:
                # 最后一次尝试失败，抛出异常
                raise
            logger.debug(f"重试访问 {url}，尝试 {attempt+1}/{max_retries}，错误：{str(e)}")
            await asyncio.sleep(2)  # 等待2秒再重试

def get_browser_profiles(browser_name=None):
    """获取浏览器配置文件列表"""
    profiles = []
    system = platform.system().lower()
    home_dir = os.path.expanduser('~')
    
    # 浏览器配置文件路径
    profile_paths = {
        "chrome": {
            "win32": os.path.join(home_dir, "AppData", "Local", "Google", "Chrome", "User Data"),
            "darwin": os.path.join(home_dir, "Library", "Application Support", "Google", "Chrome"),
            "linux": os.path.join(home_dir, ".config", "google-chrome")
        },
        "edge": {
            "win32": os.path.join(home_dir, "AppData", "Local", "Microsoft", "Edge", "User Data"),
            "darwin": os.path.join(home_dir, "Library", "Application Support", "Microsoft Edge"),
            "linux": os.path.join(home_dir, ".config", "microsoft-edge")
        }
    }
    
    browser_type = browser_name.lower() if browser_name else "chrome"
    if browser_type not in profile_paths:
        browser_type = "chrome"
    
    # 获取配置文件路径
    profile_dir = profile_paths[browser_type].get(system)
    if not profile_dir or not os.path.exists(profile_dir):
        return profiles
    
    # 查找配置文件
    for item in os.listdir(profile_dir):
        full_path = os.path.join(profile_dir, item)
        if os.path.isdir(full_path) and (item == "Default" or item.startswith("Profile ")):
            try:
                # 尝试读取Preferences文件获取配置文件名称
                pref_path = os.path.join(full_path, "Preferences")
                if os.path.exists(pref_path):
                    with open(pref_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        name = data.get("profile", {}).get("name", item)
                        profiles.append({
                            "name": name,
                            "path": full_path
                        })
            except:
                # 如果读取失败，使用目录名称
                profiles.append({
                    "name": item,
                    "path": full_path
                })
    
    return profiles

# 命令行接口
@click.group()
def cli():
    """本地网页搜索工具"""
    pass


def load_config():
    """从配置文件加载设置"""
    try:
        with open("./local-web-search.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

@cli.command()
@click.option("-q", "--query", required=True, help="搜索查询")
@click.option("-c", "--concurrency", default=5, help="并发数量")
@click.option("--show", is_flag=True, help="显示浏览器")
@click.option("--browser", help="选择浏览器（chrome或edge）")
@click.option("--max-results", default=10, type=int, help="每个查询的最大结果数")
@click.option("--exclude-domain", multiple=True, help="排除的域名")
@click.option("--truncate", type=int, help="截断页面内容的字符数")
@click.option("--proxy", help="使用代理")
@click.option("--profile-path", help="浏览器配置文件路径")
def search_cmd(query, concurrency, show, browser, max_results, exclude_domain, truncate, proxy, profile_path):
    """执行搜索命令"""
    # 使用 asyncio.run 运行异步函数
    asyncio.run(_search_cmd_async(query, concurrency, show, browser, max_results, exclude_domain, truncate, proxy, profile_path))

# 将原来的 search_cmd 函数移到这里，并重命名
async def _search_cmd_async(query, concurrency, show, browser, max_results, exclude_domain, truncate, proxy, profile_path):
    # 合并配置文件和命令行参数
    config = load_config()
    
    # 命令行参数优先级高于配置文件
    if not query and "query" in config:
        query = config["query"]
    
    concurrency = concurrency or config.get("concurrency", 5)
    show = show or config.get("show", False)
    browser = browser or config.get("browser")
    max_results = max_results or config.get("maxResults", 10)
    truncate = truncate or config.get("truncate")
    proxy = proxy or config.get("proxy")
    
    # 如果命令行没有指定exclude_domain，但配置文件中有
    if not exclude_domain and "excludeDomain" in config:
        exclude_domains = config["excludeDomain"]
        if isinstance(exclude_domains, str):
            exclude_domain = [exclude_domains]
        elif isinstance(exclude_domains, list):
            exclude_domain = exclude_domains
    
    try:
        # 启动浏览器，传入browser参数
        browser_instance = await launch_browser(show=show, proxy=proxy, browser=browser, profile_path=profile_path)
        
        # 如果查询包含逗号，分割为多个查询
        queries = [q.strip() for q in query.split(",") if q.strip()]
        if not queries:
            queries = [query]
        
        # 创建已访问URL集合
        visited_urls = set()
        
        # 执行搜索
        for q in queries:
            results = await search(
                browser=browser_instance,
                query=q,
                max_results=max_results,
                exclude_domains=list(exclude_domain),
                truncate=truncate,
                visited_urls=visited_urls,
                concurrency=concurrency
            )
            # 在命令行模式下打印结果
            print(json.dumps(results, ensure_ascii=False))
        
        # 关闭浏览器
        await browser_instance["close"]()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

@cli.command()
@click.option("--browser", help="选择浏览器（chrome或edge）")
def list_profiles(browser):
    """列出浏览器配置文件"""
    try:
        profiles = get_browser_profiles(browser)
        print(json.dumps(profiles, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    cli() 