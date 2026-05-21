"""
YOLOv8 推理单例
懒加载、预热线程、支持 ONNX 模式
若模型文件不存在，降级到基于规则的简单识别
"""
import threading
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger
from PIL import Image


class YOLODetector:
    """
    YOLOv8 电气图元检测器

    MVP 阶段若模型文件不存在，自动降级到基于颜色区域的简单识别。
    """

    def __init__(self) -> None:
        self._model = None
        self._model_loaded: bool = False
        self._model_version: str = "fallback-rule-based"
        self._load_lock: threading.Lock = threading.Lock()
        self._warmup_done: bool = False

    def warmup(self) -> None:
        """在后台线程中预热模型"""
        thread = threading.Thread(
            target=self._warmup_thread,
            daemon=True,
            name="yolo-warmup",
        )
        thread.start()

    def _warmup_thread(self) -> None:
        """预热线程：加载模型并跑一次空推理"""
        try:
            self._load_model()
            if self._model_loaded and self._model:
                # 预热推理（空白图片）
                dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                self._model.predict(
                    source=dummy,
                    verbose=False,
                    conf=0.5,
                )
                self._warmup_done = True
                logger.info("YOLOv8 model warmup complete")
        except Exception as e:
            logger.warning(f"YOLOv8 warmup failed: {e}")

    def _load_model(self) -> None:
        """加载 YOLOv8 模型（线程安全）"""
        with self._load_lock:
            if self._model_loaded:
                return

            from config import settings
            model_path = Path(settings.YOLO_MODEL_PATH)

            if not model_path.exists():
                logger.warning(
                    f"⚠️  YOLOv8 model not found at: {model_path}\n"
                    f"   Falling back to rule-based detection.\n"
                    f"   To enable AI detection, place the trained model at the above path."
                )
                self._model_loaded = False
                return

            try:
                from ultralytics import YOLO  # type: ignore
                self._model = YOLO(str(model_path))
                self._model_version = model_path.stem
                self._model_loaded = True
                logger.info(f"YOLOv8 model loaded: {model_path}")
            except ImportError:
                logger.error("ultralytics not installed. Run: pip install ultralytics")
            except Exception as e:
                logger.error(f"Failed to load YOLOv8 model: {e}")

    def predict(
        self,
        image: Image.Image,
    ) -> list[dict]:
        """
        执行推理

        Args:
            image: PIL Image 对象

        Returns:
            检测结果列表，每项包含:
            {symbol_id, symbol_name, confidence, bbox, center_x, center_y, width, height}
        """
        if not self._model_loaded:
            self._load_model()

        if not self._model_loaded:
            # 降级到基于规则的识别
            return self._rule_based_detect(image)

        return self._yolo_detect(image)

    def _yolo_detect(self, image: Image.Image) -> list[dict]:
        """使用 YOLOv8 进行推理"""
        from config import settings

        try:
            img_array = np.array(image.convert("RGB"))
            results = self._model.predict(
                source=img_array,
                conf=settings.YOLO_CONFIDENCE_THRESHOLD,
                iou=settings.YOLO_IOU_THRESHOLD,
                imgsz=settings.YOLO_IMG_SIZE,
                device=settings.YOLO_DEVICE,
                verbose=False,
            )

            detections: list[dict] = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                img_w, img_h = image.size

                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()

                    # 归一化坐标
                    x1 = xyxy[0] / img_w
                    y1 = xyxy[1] / img_h
                    x2 = xyxy[2] / img_w
                    y2 = xyxy[3] / img_h

                    symbol_id = self._cls_to_symbol_id(cls_id)
                    symbol_name = self._cls_to_name(cls_id)

                    detections.append({
                        "symbol_id": symbol_id,
                        "symbol_name": symbol_name,
                        "confidence": round(confidence, 4),
                        "bbox": [x1, y1, x2, y2],
                        "center_x": round((x1 + x2) / 2, 4),
                        "center_y": round((y1 + y2) / 2, 4),
                        "width": round(x2 - x1, 4),
                        "height": round(y2 - y1, 4),
                    })

            logger.info(f"YOLOv8 detected {len(detections)} elements")
            return detections

        except Exception as e:
            logger.error(f"YOLOv8 inference failed: {e}")
            return self._rule_based_detect(image)

    def _rule_based_detect(self, image: Image.Image) -> list[dict]:
        """
        基于规则的简单检测（Fallback）
        通过颜色区域和形状分析进行简单识别
        """
        import cv2  # type: ignore

        logger.warning("Using rule-based detection (YOLOv8 model not available)")

        try:
            img_array = np.array(image.convert("RGB"))
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            # 边缘检测
            edges = cv2.Canny(gray, 50, 150)
            # 形态学操作，连通相近的边缘
            kernel = np.ones((3, 3), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=2)

            # 查找轮廓
            contours, _ = cv2.findContours(
                dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            img_h, img_w = img_array.shape[:2]
            detections: list[dict] = []

            # 过滤合理大小的轮廓（排除过小或过大的噪点）
            min_area = img_h * img_w * 0.001  # 图片面积的 0.1%
            max_area = img_h * img_w * 0.3    # 图片面积的 30%

            for contour in contours:
                area = cv2.contourArea(contour)
                if not (min_area < area < max_area):
                    continue

                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0

                # 简单形状分类
                symbol_id, symbol_name, confidence = self._shape_classify(
                    aspect_ratio=aspect_ratio,
                    area=area,
                    img_area=img_h * img_w,
                )

                # 归一化坐标
                x1_n = x / img_w
                y1_n = y / img_h
                x2_n = (x + w) / img_w
                y2_n = (y + h) / img_h

                detections.append({
                    "symbol_id": symbol_id,
                    "symbol_name": symbol_name,
                    "confidence": round(confidence, 4),
                    "bbox": [x1_n, y1_n, x2_n, y2_n],
                    "center_x": round((x1_n + x2_n) / 2, 4),
                    "center_y": round((y1_n + y2_n) / 2, 4),
                    "width": round(x2_n - x1_n, 4),
                    "height": round(y2_n - y1_n, 4),
                })

                if len(detections) >= 10:
                    break

            logger.info(f"Rule-based detection found {len(detections)} elements")
            return detections

        except Exception as e:
            logger.error(f"Rule-based detection failed: {e}")
            return []

    @staticmethod
    def _shape_classify(
        aspect_ratio: float,
        area: float,
        img_area: float,
    ) -> tuple[str, str, float]:
        """基于形状特征简单分类图元"""
        relative_area = area / img_area

        if aspect_ratio > 3.0:
            return "BUS_3P", "三相母线", 0.45
        elif aspect_ratio < 0.4:
            return "WIRE", "导线", 0.40
        elif 0.8 < aspect_ratio < 1.2 and relative_area > 0.02:
            return "TR_2W", "变压器", 0.50
        elif 0.6 < aspect_ratio < 1.5 and relative_area < 0.01:
            return "CB_3P", "断路器", 0.45
        else:
            return "WIRE", "导线/连接", 0.35

    @staticmethod
    def _cls_to_symbol_id(cls_id: int) -> str:
        """将 YOLOv8 类别 ID 映射到 symbol_id"""
        CLASS_MAP = {
            0: "CB_3P", 1: "DS_3P", 2: "TR_2W", 3: "BUS_3P",
            4: "GND", 5: "LA", 6: "CT", 7: "VT",
            8: "SWGR", 9: "CABLE", 10: "WIRE", 11: "FUSE",
            12: "KM", 13: "MOTOR", 14: "GEN", 15: "RECT",
            16: "BAT", 17: "CAP", 18: "REACT", 19: "AMMETER",
        }
        return CLASS_MAP.get(cls_id, f"UNKNOWN_{cls_id}")

    @staticmethod
    def _cls_to_name(cls_id: int) -> str:
        """将类别 ID 映射到中文名称"""
        NAME_MAP = {
            0: "三相断路器", 1: "三相隔离开关", 2: "双绕组变压器",
            3: "三相母线", 4: "接地符号", 5: "避雷器",
            6: "电流互感器", 7: "电压互感器", 8: "开关柜",
            9: "电力电缆", 10: "导线", 11: "熔断器",
            12: "接触器", 13: "三相异步电动机", 14: "发电机",
            15: "整流器", 16: "蓄电池组", 17: "电容器组",
            18: "电抗器", 19: "电流表",
        }
        return NAME_MAP.get(cls_id, f"未知图元[{cls_id}]")


# 全局单例
detector = YOLODetector()
