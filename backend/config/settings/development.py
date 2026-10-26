"""开发环境配置。"""
from .base import *  # noqa: F401,F403

DEBUG = True

# 开发时允许 Vite dev server 调试
ALLOWED_HOSTS = ["*"]
