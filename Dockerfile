# 使用预装 uv 的 Python 镜像作为构建阶段
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS uv

# 设置工作目录
WORKDIR /app

# 启用字节码编译
ENV UV_COMPILE_BYTECODE=1

# 使用复制而不是链接，因为它是挂载卷
ENV UV_LINK_MODE=copy

# 安装项目依赖
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --no-editable

# 添加项目源代码并安装
ADD . /app

# 安装 Playwright 浏览器
RUN playwright install chromium --with-deps

# 安装项目
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# 使用精简的 Python 镜像作为最终阶段
FROM python:3.12-slim-bookworm

# 安装 Playwright 的系统依赖
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制 Python 包和虚拟环境
COPY --from=uv /root/.local /root/.local
COPY --from=uv /app/.venv /app/.venv
COPY --from=uv /ms-playwright /ms-playwright

# 复制源代码
COPY --from=uv /app/src /app/src

# 设置环境变量
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# 设置入口点
ENTRYPOINT ["local_web_search"] 