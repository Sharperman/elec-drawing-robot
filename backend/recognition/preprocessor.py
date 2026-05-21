"""
图片预处理：灰度化、二值化、去噪、缩放
用于 YOLOv8 推理前的图像预处理
"""
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image


class ImagePreprocessor:
    """图片预处理器"""

    def preprocess(
        self,
        image: Image.Image,
        target_size: int = 640,
        enhance_contrast: bool = True,
    ) -> Image.Image:
        """
        全流程预处理

        Args:
            image: 原始 PIL Image
            target_size: 目标尺寸（YOLOv8 默认 640）
            enhance_contrast: 是否增强对比度

        Returns:
            预处理后的 PIL Image（RGB 格式）
        """
        # 确保 RGB
        img = image.convert("RGB")
        img_array = np.array(img)

        # 增强对比度（适用于工程图纸扫描件）
        if enhance_contrast:
            img_array = self._enhance_contrast(img_array)

        # 去噪
        img_array = self._denoise(img_array)

        # 缩放至目标尺寸（保持比例，填充空白）
        img_array = self._letterbox_resize(img_array, target_size)

        return Image.fromarray(img_array)

    def to_grayscale(self, image: Image.Image) -> Image.Image:
        """转为灰度图"""
        return image.convert("L")

    def binarize(
        self,
        image: Image.Image,
        threshold: Optional[int] = None,
    ) -> Image.Image:
        """
        二值化处理

        Args:
            image: 灰度或 RGB 图像
            threshold: 阈值（None=自动 Otsu 算法）

        Returns:
            二值化后的 PIL Image
        """
        gray = np.array(image.convert("L"))

        if threshold is None:
            # Otsu 自动阈值
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

        return Image.fromarray(binary)

    def _enhance_contrast(self, img_array: np.ndarray) -> np.ndarray:
        """CLAHE 对比度增强（适用于工程图纸）"""
        # 转换到 LAB 颜色空间
        lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
        l_channel, a, b = cv2.split(lab)

        # 对亮度通道应用 CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_channel)

        # 合并通道
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)

    def _denoise(self, img_array: np.ndarray) -> np.ndarray:
        """高斯模糊去噪（轻度，不影响线条细节）"""
        return cv2.GaussianBlur(img_array, (3, 3), 0)

    def _letterbox_resize(
        self,
        img_array: np.ndarray,
        target_size: int,
        color: Tuple[int, int, int] = (114, 114, 114),
    ) -> np.ndarray:
        """
        Letterbox 缩放：保持比例，用灰色填充空白

        Args:
            img_array: 原始图像数组
            target_size: 目标尺寸
            color: 填充颜色（YOLOv8 默认 (114,114,114)）

        Returns:
            缩放后的图像数组
        """
        h, w = img_array.shape[:2]
        scale = min(target_size / h, target_size / w)
        new_h, new_w = int(h * scale), int(w * scale)

        resized = cv2.resize(img_array, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # 创建目标画布（灰色填充）
        canvas = np.full((target_size, target_size, 3), color, dtype=np.uint8)

        # 居中放置
        top = (target_size - new_h) // 2
        left = (target_size - new_w) // 2
        canvas[top:top + new_h, left:left + new_w] = resized

        return canvas


# 全局单例
preprocessor = ImagePreprocessor()
