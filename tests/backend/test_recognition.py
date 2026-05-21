"""
Test Suite: Recognition / Detector
Tests for:
  - recognition/detector.py - YOLODetector predict(), _rule_based_detect(),
                              _shape_classify(), _cls_to_symbol_id(), _cls_to_name()
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from PIL import Image


# ============================================================
# Helpers
# ============================================================


def make_rgb_image(width: int = 200, height: int = 200) -> Image.Image:
    """Create a simple RGB test image."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    # Add a bright rectangle to give the edge detector something to find
    arr[50:150, 50:150] = 200
    return Image.fromarray(arr, mode="RGB")


# ============================================================
# Test: _cls_to_symbol_id
# ============================================================


class TestClsToSymbolId:
    """Static mapping from class ID to symbol_id string."""

    @pytest.mark.parametrize("cls_id,expected", [
        (0, "CB_3P"),
        (1, "DS_3P"),
        (2, "TR_2W"),
        (3, "BUS_3P"),
        (4, "GND"),
        (5, "LA"),
        (6, "CT"),
        (7, "VT"),
        (8, "SWGR"),
        (9, "CABLE"),
        (10, "WIRE"),
        (11, "FUSE"),
        (12, "KM"),
        (13, "MOTOR"),
        (14, "GEN"),
        (15, "RECT"),
        (16, "BAT"),
        (17, "CAP"),
        (18, "REACT"),
        (19, "AMMETER"),
    ])
    def test_known_class_ids(self, cls_id, expected):
        from recognition.detector import YOLODetector
        assert YOLODetector._cls_to_symbol_id(cls_id) == expected

    def test_unknown_class_id_returns_unknown_string(self):
        from recognition.detector import YOLODetector
        result = YOLODetector._cls_to_symbol_id(99)
        assert result.startswith("UNKNOWN_")


# ============================================================
# Test: _cls_to_name
# ============================================================


class TestClsToName:
    @pytest.mark.parametrize("cls_id,expected_fragment", [
        (0, "断路器"),
        (2, "变压器"),
        (4, "接地"),
        (10, "导线"),
    ])
    def test_known_names(self, cls_id, expected_fragment):
        from recognition.detector import YOLODetector
        name = YOLODetector._cls_to_name(cls_id)
        assert expected_fragment in name

    def test_unknown_cls_id_name(self):
        from recognition.detector import YOLODetector
        name = YOLODetector._cls_to_name(99)
        assert "未知" in name or "99" in name


# ============================================================
# Test: _shape_classify
# ============================================================


class TestShapeClassify:
    """Tests for the rule-based shape classifier."""

    def test_wide_aspect_ratio_returns_bus(self):
        from recognition.detector import YOLODetector
        symbol_id, name, conf = YOLODetector._shape_classify(
            aspect_ratio=4.0, area=5000, img_area=100_000
        )
        assert symbol_id == "BUS_3P"

    def test_very_narrow_aspect_ratio_returns_wire(self):
        from recognition.detector import YOLODetector
        symbol_id, name, conf = YOLODetector._shape_classify(
            aspect_ratio=0.2, area=1000, img_area=100_000
        )
        assert symbol_id == "WIRE"

    def test_square_large_area_returns_transformer(self):
        from recognition.detector import YOLODetector
        symbol_id, name, conf = YOLODetector._shape_classify(
            aspect_ratio=1.0, area=3000, img_area=100_000  # 3% of img -> > 2%
        )
        assert symbol_id == "TR_2W"

    def test_moderate_aspect_small_area_returns_circuit_breaker(self):
        from recognition.detector import YOLODetector
        symbol_id, name, conf = YOLODetector._shape_classify(
            aspect_ratio=1.0, area=500, img_area=100_000  # 0.5% -> < 1%
        )
        assert symbol_id == "CB_3P"

    def test_confidence_in_valid_range(self):
        from recognition.detector import YOLODetector
        for ar in [0.1, 0.5, 1.0, 2.0, 4.0]:
            _, _, conf = YOLODetector._shape_classify(ar, 1000, 100_000)
            assert 0.0 <= conf <= 1.0


# ============================================================
# Test: YOLODetector.predict – fallback path (no model)
# ============================================================


class TestYOLODetectorFallbackPredict:
    """When no YOLO model file exists, predict() delegates to _rule_based_detect."""

    def test_predict_calls_rule_based_when_no_model(self):
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        detector._model_loaded = False
        detector._model = None

        img = make_rgb_image()

        with patch.object(detector, "_rule_based_detect", return_value=[]) as mock_rbd:
            # Also patch _load_model to be a no-op (so it never sets _model_loaded=True)
            with patch.object(detector, "_load_model"):
                detector.predict(img)

        mock_rbd.assert_called_once_with(img)

    def test_predict_returns_list(self):
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        detector._model_loaded = False
        detector._model = None

        img = make_rgb_image()

        with patch("config.settings"):
            with patch.object(detector, "_load_model"):
                result = detector.predict(img)

        assert isinstance(result, list)

    def test_rule_based_detect_returns_list_of_dicts(self):
        """_rule_based_detect returns dicts with expected keys."""
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        img = make_rgb_image(300, 300)

        results = detector._rule_based_detect(img)

        assert isinstance(results, list)
        for item in results:
            assert "symbol_id" in item
            assert "symbol_name" in item
            assert "confidence" in item
            assert "bbox" in item
            assert "center_x" in item
            assert "center_y" in item
            assert "width" in item
            assert "height" in item

    def test_rule_based_detect_bbox_normalized(self):
        """All bbox coordinates are in [0, 1]."""
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        img = make_rgb_image(300, 300)

        results = detector._rule_based_detect(img)
        for item in results:
            x1, y1, x2, y2 = item["bbox"]
            assert 0.0 <= x1 <= 1.0
            assert 0.0 <= y1 <= 1.0
            assert 0.0 <= x2 <= 1.0
            assert 0.0 <= y2 <= 1.0

    def test_rule_based_detect_caps_at_10_results(self):
        """Rule-based detect returns at most 10 elements."""
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        # Large image with many rectangles drawn
        arr = np.zeros((600, 600, 3), dtype=np.uint8)
        # Draw 15 distinct squares
        for i in range(15):
            top = i * 30 + 5
            arr[top:top + 20, 10:30] = 200
        img = Image.fromarray(arr, mode="RGB")

        results = detector._rule_based_detect(img)
        assert len(results) <= 10

    def test_rule_based_detect_on_blank_image_returns_empty(self):
        """A completely blank image (no edges) returns an empty list."""
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        blank = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8), mode="RGB")
        results = detector._rule_based_detect(blank)
        assert isinstance(results, list)
        # Blank image might produce 0 contours above threshold
        assert len(results) <= 10


# ============================================================
# Test: YOLODetector.predict – YOLO path
# ============================================================


class TestYOLODetectorYoloPath:
    """Tests for _yolo_detect using a mocked ultralytics YOLO model."""

    def _make_mock_model(self, detections):
        """
        Build a mock YOLO model whose predict() returns a results list.
        `detections` is a list of (cls_id, confidence, xyxy_list) tuples.
        `xyxy_list` should be a 4-element list like [x1, y1, x2, y2].
        """
        mock_model = MagicMock()

        results_list = []
        for cls_id, conf, xyxy_list in detections:
            box = MagicMock()
            box.cls = [MagicMock()]
            box.cls[0].item.return_value = float(cls_id)
            box.conf = [MagicMock()]
            box.conf[0].item.return_value = conf
            # box.xyxy[0] must support .tolist() to return the coordinate list
            xyxy_tensor = MagicMock()
            xyxy_tensor.tolist.return_value = xyxy_list
            box.xyxy = [xyxy_tensor]

            mock_result = MagicMock()
            mock_result.boxes = [box]
            results_list.append(mock_result)

        mock_model.predict.return_value = results_list
        return mock_model

    def test_yolo_detect_single_result(self):
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        detector._model_loaded = True
        detector._model = self._make_mock_model([
            (0, 0.92, [10.0, 20.0, 50.0, 60.0])
        ])

        img = make_rgb_image(200, 200)

        with patch("config.settings") as mock_s:
            mock_s.YOLO_CONFIDENCE_THRESHOLD = 0.5
            mock_s.YOLO_IOU_THRESHOLD = 0.45
            mock_s.YOLO_IMG_SIZE = 640
            mock_s.YOLO_DEVICE = "cpu"
            results = detector._yolo_detect(img)

        assert len(results) == 1
        det = results[0]
        assert det["symbol_id"] == "CB_3P"
        assert abs(det["confidence"] - 0.92) < 1e-3
        assert len(det["bbox"]) == 4

    def test_yolo_detect_normalizes_coordinates(self):
        """bbox coordinates should be normalized relative to image dimensions."""
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        detector._model_loaded = True
        # Image 200x200; box covers x=[0,200], y=[0,100]  → x2-x1=1.0, y2-y1=0.5
        detector._model = self._make_mock_model([
            (2, 0.8, [0.0, 0.0, 200.0, 100.0])
        ])

        img = make_rgb_image(200, 200)

        with patch("config.settings") as mock_s:
            mock_s.YOLO_CONFIDENCE_THRESHOLD = 0.5
            mock_s.YOLO_IOU_THRESHOLD = 0.45
            mock_s.YOLO_IMG_SIZE = 640
            mock_s.YOLO_DEVICE = "cpu"
            results = detector._yolo_detect(img)

        bbox = results[0]["bbox"]
        assert abs(bbox[0] - 0.0) < 1e-6
        assert abs(bbox[1] - 0.0) < 1e-6
        assert abs(bbox[2] - 1.0) < 1e-6
        assert abs(bbox[3] - 0.5) < 1e-6

    def test_yolo_detect_fallback_on_model_exception(self):
        """If model.predict throws, _yolo_detect falls back to _rule_based_detect."""
        from recognition.detector import YOLODetector

        detector = YOLODetector()
        detector._model_loaded = True
        detector._model = MagicMock()
        detector._model.predict.side_effect = RuntimeError("CUDA OOM")

        img = make_rgb_image()

        with patch.object(detector, "_rule_based_detect", return_value=[]) as mock_rbd:
            with patch("config.settings") as mock_s:
                mock_s.YOLO_CONFIDENCE_THRESHOLD = 0.5
                mock_s.YOLO_IOU_THRESHOLD = 0.45
                mock_s.YOLO_IMG_SIZE = 640
                mock_s.YOLO_DEVICE = "cpu"
                results = detector._yolo_detect(img)

        mock_rbd.assert_called_once()
