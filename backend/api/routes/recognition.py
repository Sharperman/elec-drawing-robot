"""
图片识别路由
POST /api/recognize
"""
import time

from api.schemas import (
    ApiResponse,
    DetectedElement,
    RecognitionRequest,
    RecognitionResponse,
)
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from models.session import get_db
from sqlalchemy.orm import Session
from utils.error_codes import ErrorCode, get_error_message
from utils.image_utils import base64_to_image

router = APIRouter()


@router.post("", response_model=ApiResponse)
async def recognize_image(
    request: RecognitionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    识别图片中的电气元件

    接收 base64 编码的图片，返回识别到的电气图元列表。
    若 YOLOv8 模型未加载，降级为基于规则的识别。
    """
    start_time = time.time()

    if not request.image_data:
        raise HTTPException(
            status_code=400,
            detail=get_error_message(ErrorCode.IMAGE_INVALID),
        )

    try:
        # 解码图片
        try:
            image = base64_to_image(request.image_data)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"{get_error_message(ErrorCode.IMAGE_INVALID)}: {e}",
            )

        # 预处理
        from recognition.preprocessor import preprocessor
        processed_image = preprocessor.preprocess(image)

        # 推理
        from recognition.detector import detector
        raw_detections = detector.predict(processed_image)

        # 后处理（置信度过滤 + NMS + 符号映射）
        from config import settings
        from recognition.postprocessor import postprocess

        detections = postprocess(
            raw_detections,
            confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
            iou_threshold=settings.YOLO_IOU_THRESHOLD,
            db_session=db,
        )

        # 构建响应
        elements = [
            DetectedElement(
                symbol_id=d["symbol_id"],
                symbol_name=d.get("symbol_name", d["symbol_id"]),
                confidence=d["confidence"],
                bbox=d["bbox"],
                center_x=d["center_x"],
                center_y=d["center_y"],
                width=d["width"],
                height=d["height"],
            )
            for d in detections
        ]

        inference_time = (time.time() - start_time) * 1000
        model_version = detector._model_version if detector._model_loaded else "rule-based-v1"

        response_data = RecognitionResponse(
            elements=elements,
            total=len(elements),
            model_version=model_version,
            inference_time_ms=round(inference_time, 2),
        )

        logger.info(
            f"Recognition complete: {len(elements)} elements "
            f"in {inference_time:.0f}ms"
        )

        return ApiResponse(data=response_data.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recognition error: {e}")
        return ApiResponse(
            code=ErrorCode.RECOGNITION_FAILED,
            message=get_error_message(ErrorCode.RECOGNITION_FAILED),
            data={"error": str(e)},
        )
