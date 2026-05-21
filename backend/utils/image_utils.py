"""
图片工具函数
提供 base64 编解码、格式校验、图片压缩等功能
"""
import base64
import io
from pathlib import Path
from typing import Optional, Tuple

from loguru import logger
from PIL import Image


# 支持的图片格式（MIME type 映射）
SUPPORTED_FORMATS: dict[str, str] = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "webp": "image/webp",
}

# 最大文件大小（10 MB）
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


def image_to_base64(
    image: Image.Image,
    format: str = "PNG",
    quality: int = 85,
) -> str:
    """
    将 PIL Image 对象转换为 base64 字符串

    Args:
        image: PIL Image 对象
        format: 输出格式（PNG/JPEG）
        quality: JPEG 质量（1-95），PNG 忽略此参数

    Returns:
        base64 编码的图片字符串（含 data URL 前缀）
    """
    buffer = io.BytesIO()
    save_kwargs: dict = {"format": format}
    if format.upper() == "JPEG":
        save_kwargs["quality"] = quality
        # JPEG 不支持透明通道
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
    image.save(buffer, **save_kwargs)
    buffer.seek(0)
    b64_data = base64.b64encode(buffer.read()).decode("utf-8")
    mime = "image/png" if format.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64_data}"


def base64_to_image(b64_string: str) -> Image.Image:
    """
    将 base64 字符串解码为 PIL Image

    Args:
        b64_string: base64 字符串（支持含/不含 data URL 前缀）

    Returns:
        PIL Image 对象

    Raises:
        ValueError: base64 字符串无效或不是有效图片
    """
    if not b64_string:
        raise ValueError("base64 字符串为空")

    # 去掉 data URL 前缀
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]

    try:
        image_data = base64.b64decode(b64_string)
    except Exception as e:
        raise ValueError(f"base64 解码失败: {e}") from e

    try:
        image = Image.open(io.BytesIO(image_data))
        image.load()  # 强制加载，确保数据有效
        return image
    except Exception as e:
        raise ValueError(f"图片解析失败: {e}") from e


def file_to_base64(file_path: str | Path) -> str:
    """
    读取文件并转换为 base64 字符串

    Args:
        file_path: 图片文件路径

    Returns:
        base64 编码的图片字符串（含 data URL 前缀）

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式不支持或文件过大
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的图片格式: {suffix}，支持格式: {list(SUPPORTED_FORMATS.keys())}")

    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"文件过大: {file_size / 1024 / 1024:.1f}MB，最大支持 10MB")

    with open(path, "rb") as f:
        data = f.read()

    b64_data = base64.b64encode(data).decode("utf-8")
    mime = SUPPORTED_FORMATS[suffix]
    return f"data:{mime};base64,{b64_data}"


def validate_image_bytes(data: bytes) -> Tuple[bool, Optional[str]]:
    """
    校验字节数据是否为有效图片

    Args:
        data: 图片字节数据

    Returns:
        (is_valid, error_message) 元组
    """
    if len(data) > MAX_FILE_SIZE_BYTES:
        return False, f"文件过大: {len(data) / 1024 / 1024:.1f}MB"

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        return True, None
    except Exception as e:
        return False, f"无效图片: {e}"


def resize_image_if_needed(
    image: Image.Image,
    max_size: int = 1920,
) -> Image.Image:
    """
    如果图片超过最大尺寸则缩放（保持比例）

    Args:
        image: 原始 PIL Image
        max_size: 最大边长（像素）

    Returns:
        缩放后的 PIL Image（如无需缩放则返回原图）
    """
    width, height = image.size
    if max(width, height) <= max_size:
        return image

    scale = max_size / max(width, height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    logger.debug(f"Resizing image from {width}x{height} to {new_width}x{new_height}")
    return image.resize((new_width, new_height), Image.LANCZOS)


def screenshot_to_base64(screenshot_bytes: bytes) -> str:
    """
    将截图字节数据转换为 base64 字符串

    Args:
        screenshot_bytes: 截图原始字节

    Returns:
        base64 编码字符串（含 data:image/png;base64, 前缀）
    """
    b64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64_data}"
