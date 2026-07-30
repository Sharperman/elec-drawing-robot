"""
视频录制引擎
mss 截图 → OpenCV MP4 编码 → 队列消费线程 → 分段文件。
"""
import os
import queue
import threading
import time
from pathlib import Path
from typing import Optional, List

import cv2
import numpy as np
from loguru import logger


class VideoRecorder:
    """
    视频录制器。
    - fps: 帧率（默认5，可调）
    - segment_minutes: 每段时长（默认10分钟）
    - output_dir: 输出目录
    """

    def __init__(self, fps: int = 5, segment_minutes: int = 10, output_dir: str = "data/recordings"):
        self.fps = fps
        self.segment_minutes = segment_minutes
        self.segment_frames = fps * 60 * segment_minutes
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._paused = False
        self._frame_count = 0
        self._total_frames = 0
        self._segment_index = 0
        self._writer: Optional[cv2.VideoWriter] = None
        self._writer_thread: Optional[threading.Thread] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._frame_queue = queue.Queue(maxsize=300)  # 最多缓冲 300 帧
        self._segments: List[str] = []
        self._start_time: float = 0
        self._session_id: str = ""
        self._screen_width = 1920
        self._screen_height = 1080

    # ── 公开接口 ────────────────────────────────────

    def start(self, session_id: str) -> bool:
        """开始录制"""
        if self._recording:
            logger.warning("录制已在运行中")
            return False

        self._session_id = session_id
        self._recording = True
        self._paused = False
        self._frame_count = 0
        self._total_frames = 0
        self._segment_index = 0
        self._segments = []
        self._start_time = time.time()

        # 创建录制目录
        session_dir = self.output_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 获取屏幕尺寸
        from desktop import screen_capture
        info = screen_capture.get_main_display_info()
        self._screen_width = info["width"]
        self._screen_height = info["height"]

        # 清空队列
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break

        # 创建第一个 video writer
        self._rotate_writer()

        # 启动截图线程
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        # 启动写文件线程
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

        logger.info(f"录制开始: session={session_id}, fps={self.fps}, segment={self.segment_minutes}min")
        return True

    def stop(self) -> dict:
        """停止录制，返回录制信息"""
        self._recording = False

        if self._capture_thread:
            self._capture_thread.join(timeout=3)
        if self._writer_thread:
            self._writer_thread.join(timeout=5)

        # 关闭最后一个 writer
        if self._writer and self._writer.isOpened():
            self._writer.release()
            self._writer = None

        duration = time.time() - self._start_time if self._start_time else 0

        result = {
            "session_id": self._session_id,
            "duration_seconds": round(duration, 1),
            "total_frames": self._total_frames,
            "segments": self._segments,
            "fps": self.fps,
            "resolution": f"{self._screen_width}x{self._screen_height}",
        }

        logger.info(f"录制停止: {result}")
        return result

    def pause(self):
        """暂停录制"""
        self._paused = True

    def resume(self):
        """恢复录制"""
        self._paused = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def duration_seconds(self) -> float:
        if not self._start_time:
            return 0
        return time.time() - self._start_time

    @property
    def frame_count(self) -> int:
        return self._total_frames

    def set_fps(self, fps: int):
        """动态调整帧率"""
        self.fps = max(1, min(fps, 30))
        self.segment_frames = self.fps * 60 * self.segment_minutes

    # ── 内部方法 ────────────────────────────────────

    def _rotate_writer(self):
        """切换到新的视频文件段"""
        if self._writer and self._writer.isOpened():
            self._writer.release()

        segment_filename = f"{self._session_id}_{self._segment_index:03d}.mp4"
        segment_path = str(self.output_dir / self._session_id / segment_filename)
        self._segments.append(segment_filename)
        self._segment_index += 1
        self._frame_count = 0

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self._writer = cv2.VideoWriter(segment_path, fourcc, self.fps, (self._screen_width, self._screen_height))

        if not self._writer.isOpened():
            logger.error(f"无法创建视频文件: {segment_path}")
            # fallback: 尝试 XVID
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self._writer = cv2.VideoWriter(segment_path, fourcc, self.fps, (self._screen_width, self._screen_height))

        logger.info(f"新视频段: {segment_filename}")

    def _capture_loop(self):
        """截图线程：定时截取全屏 → 放入队列"""
        from desktop import screen_capture
        interval = 1.0 / self.fps

        while self._recording:
            loop_start = time.time()

            if not self._paused:
                try:
                    frame = screen_capture.capture_fullscreen_numpy()
                    if frame is not None:
                        # 转换 BGRA → BGR (OpenCV 格式)
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        # 确保尺寸一致
                        if frame_bgr.shape[1] != self._screen_width or frame_bgr.shape[0] != self._screen_height:
                            frame_bgr = cv2.resize(frame_bgr, (self._screen_width, self._screen_height))
                        # 非阻塞放入队列
                        try:
                            self._frame_queue.put_nowait((frame_bgr, self._total_frames))
                            self._total_frames += 1
                        except queue.Full:
                            logger.debug("帧队列已满，丢弃一帧")
                except Exception as e:
                    logger.warning(f"截图线程出错: {e}")

            elapsed = time.time() - loop_start
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)

    def _writer_loop(self):
        """写文件线程：从队列取帧 → 写入 MP4"""
        while self._recording or not self._frame_queue.empty():
            try:
                frame, _ = self._frame_queue.get(timeout=1)
                if self._writer and self._writer.isOpened():
                    self._writer.write(frame)
                    self._frame_count += 1
                    # 检查是否需要切换段
                    if self._frame_count >= self.segment_frames:
                        self._rotate_writer()
            except queue.Empty:
                continue
            except Exception as e:
                logger.warning(f"写入视频帧出错: {e}")


# 全局单例
video_recorder = VideoRecorder()
