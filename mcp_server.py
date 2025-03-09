#!/usr/bin/env python3
import os
import sys
import json
import asyncio
from typing import List, Dict, Optional, Any, Set

from mcp.server.fastmcp import FastMCP

# 从 local_web_search.py 导入搜索函数
from local_web_search import search, launch_browser

# 初始化 FastMCP 服务器
mcp = FastMCP("web_search")

# 用于存储搜索结果的全局变量
search_results = {}

# 捕获标准输出的类
class OutputCapture:
    def __init__(self):
        self.captured_output = []
        self.original_stdout = sys.stdout
    
    def __enter__(self):
        sys.stdout = self
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
    
    def write(self, text):
        self.captured_output.append(text)
    
    def flush(self):
        pass
    
    def get_output(self):
        return ''.join(self.captured_output)

@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """执行网络搜索并返回结果。
    
    Args:
        query: 搜索查询
        max_results（可选）: 要返回的结果数量（默认为5）
    """
    # 处理排除域名
    exclude_domains_list = []
    
    # 启动浏览器
    browser_instance = await launch_browser(show=False)
    
    try:
        # 执行搜索并直接获取结果
        results = await search(
            browser=browser_instance,
            query=query,
            max_results=max_results,
            # exclude_domains=exclude_domains_list,
            # truncate=3000,  # 限制内容长度
            concurrency=5
        )
        
        if not results or not results.get("results"):
            return "未找到搜索结果。"
        
        # 格式化结果
        formatted_results = []
        for i, result in enumerate(results["results"], 1):
            if i > max_results:
                break
                
            formatted_result = f"""
结果 {i}:
标题: {result.get('title', '无标题')}
URL: {result.get('url', '无URL')}
内容: {result.get('content', '无内容')}
"""
            formatted_results.append(formatted_result)
        
        return f"搜索查询: {query}\n\n" + "\n---\n".join(formatted_results)
    finally:
        # 关闭浏览器
        await browser_instance["close"]()

if __name__ == "__main__":
    # 初始化并运行服务器
    mcp.run(transport='sse')
