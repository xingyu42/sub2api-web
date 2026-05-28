import starlette.config
from slowapi import Limiter
from slowapi.util import get_remote_address

# 修复 starlette.config.Config 在 Windows 上的编码问题
# starlette 的 _read_file 方法未指定 encoding，导致 Windows 下使用 GBK 解码 UTF-8 文件失败
# 通过 Monkey Patch 修复此问题
def _read_file_utf8(self, file_name):
    """修复版本：显式使用 UTF-8 编码读取 .env 文件"""
    file_values = {}
    with open(file_name, encoding='utf-8') as input_file:
        for line in input_file.readlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                file_values[key] = value
    return file_values

starlette.config.Config._read_file = _read_file_utf8

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/hour", "50/minute"],
    enabled=True,
    headers_enabled=True
)
