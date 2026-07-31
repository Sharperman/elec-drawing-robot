"""
推理后处理：NMS 去重、置信度过滤、bbox 还原、symbol 映射
"""

import numpy as np


def nms(
    boxes: list[list[float]],
    scores: list[float],
    iou_threshold: float = 0.45,
) -> list[int]:
    """
    非极大值抑制（NMS）

    Args:
        boxes: [x1, y1, x2, y2] 归一化坐标列表
        scores: 置信度列表
        iou_threshold: IoU 阈值

    Returns:
        保留的检测框索引列表
    """
    if not boxes:
        return []

    boxes_arr = np.array(boxes, dtype=np.float32)
    scores_arr = np.array(scores, dtype=np.float32)

    x1 = boxes_arr[:, 0]
    y1 = boxes_arr[:, 1]
    x2 = boxes_arr[:, 2]
    y2 = boxes_arr[:, 3]
    areas = (x2 - x1) * (y2 - y1)

    order = scores_arr.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))

        if order.size == 1:
            break

        # 计算 IoU
        inter_x1 = np.maximum(x1[i], x1[order[1:]])
        inter_y1 = np.maximum(y1[i], y1[order[1:]])
        inter_x2 = np.minimum(x2[i], x2[order[1:]])
        inter_y2 = np.minimum(y2[i], y2[order[1:]])

        inter_w = np.maximum(0.0, inter_x2 - inter_x1)
        inter_h = np.maximum(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        union_area = areas[i] + areas[order[1:]] - inter_area
        iou = inter_area / (union_area + 1e-8)

        order = order[np.where(iou <= iou_threshold)[0] + 1]

    return keep


def filter_by_confidence(
    detections: list[dict],
    threshold: float = 0.5,
) -> list[dict]:
    """
    按置信度过滤检测结果

    Args:
        detections: 检测结果列表
        threshold: 最低置信度阈值

    Returns:
        过滤后的检测结果
    """
    return [d for d in detections if d.get("confidence", 0) >= threshold]


def apply_nms_to_detections(
    detections: list[dict],
    iou_threshold: float = 0.45,
) -> list[dict]:
    """
    对检测结果应用 NMS 去重

    Args:
        detections: 原始检测结果列表（已含 bbox）
        iou_threshold: IoU 阈值

    Returns:
        NMS 后的检测结果列表
    """
    if not detections:
        return []

    boxes = [d["bbox"] for d in detections]
    scores = [d["confidence"] for d in detections]
    keep_indices = nms(boxes, scores, iou_threshold)

    return [detections[i] for i in keep_indices]


def map_to_symbol_info(
    detections: list[dict],
    db_session=None,
) -> list[dict]:
    """
    将检测结果映射到符号库信息（补全 name 等字段）

    Args:
        detections: 检测结果列表（含 symbol_id）
        db_session: SQLAlchemy Session（可选，用于从 DB 补全信息）

    Returns:
        补全信息后的检测结果
    """
    if db_session is None:
        return detections

    try:
        from knowledge.symbol_library import SymbolLibrary

        lib = SymbolLibrary(db_session)
        enriched: list[dict] = []

        for detection in detections:
            symbol_id = detection.get("symbol_id", "")
            symbol = lib.get_by_id(symbol_id)
            if symbol:
                detection["symbol_name"] = symbol.name
                detection["layer"] = symbol.layer
                detection["block_name"] = symbol.block_name
                detection["category"] = symbol.category
            enriched.append(detection)

        return enriched
    except Exception:
        return detections


def postprocess(
    detections: list[dict],
    confidence_threshold: float = 0.5,
    iou_threshold: float = 0.45,
    db_session=None,
) -> list[dict]:
    """
    完整后处理流程：置信度过滤 → NMS → 符号映射

    Args:
        detections: 原始检测结果
        confidence_threshold: 置信度阈值
        iou_threshold: NMS IoU 阈值
        db_session: 数据库会话（补全符号信息）

    Returns:
        后处理完成的检测结果
    """
    # 1. 置信度过滤
    filtered = filter_by_confidence(detections, confidence_threshold)

    # 2. NMS 去重
    nms_result = apply_nms_to_detections(filtered, iou_threshold)

    # 3. 符号信息补全
    enriched = map_to_symbol_info(nms_result, db_session)

    return enriched
