/**
 * useImageUpload Hook - 图片上传和识别
 */
import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';

import apiClient from '@/services/apiClient';
import type { RecognitionResponse } from '@/types';

interface ImageUploadState {
  isUploading: boolean;
  previewUrl: string | null;
  imageData: string | null;
  recognitionResult: RecognitionResponse | null;
  error: string | null;
}

export function useImageUpload(sessionId?: string) {
  const [state, setState] = useState<ImageUploadState>({
    isUploading: false,
    previewUrl: null,
    imageData: null,
    recognitionResult: null,
    error: null,
  });

  /**
   * 将 File 对象转换为 base64 字符串
   */
  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  /**
   * 处理图片文件选择/拖拽
   */
  const handleImageFile = useCallback(async (file: File): Promise<string | null> => {
    // 验证文件类型
    const validTypes = ['image/jpeg', 'image/png', 'image/bmp', 'image/tiff', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      toast.error('不支持的文件格式，请使用 JPG/PNG/BMP/TIFF');
      return null;
    }

    // 验证文件大小（10MB）
    if (file.size > 10 * 1024 * 1024) {
      toast.error('图片文件不能超过 10MB');
      return null;
    }

    try {
      const base64 = await fileToBase64(file);
      const previewUrl = URL.createObjectURL(file);

      setState((prev) => ({
        ...prev,
        previewUrl,
        imageData: base64,
        recognitionResult: null,
        error: null,
      }));

      return base64;
    } catch (err) {
      toast.error('图片读取失败');
      return null;
    }
  }, []);

  /**
   * 调用识别 API 识别图片中的电气元件
   */
  const recognize = useCallback(async (imageData?: string): Promise<RecognitionResponse | null> => {
    const dataToUse = imageData ?? state.imageData;
    if (!dataToUse) {
      toast.error('请先选择图片');
      return null;
    }

    setState((prev) => ({ ...prev, isUploading: true, error: null }));

    try {
      const toastId = toast.loading('正在识别电气元件...');
      const resp = await apiClient.post<{ data: RecognitionResponse }>(
        '/api/recognize',
        {
          image_data: dataToUse,
          session_id: sessionId,
        }
      );

      const result = resp.data.data;
      setState((prev) => ({
        ...prev,
        recognitionResult: result,
        isUploading: false,
      }));

      toast.success(
        `识别完成：发现 ${result.total} 个电气元件（${result.model_version}）`,
        { id: toastId }
      );

      return result;
    } catch (err) {
      const errMsg = '识别失败，请重试';
      setState((prev) => ({ ...prev, error: errMsg, isUploading: false }));
      toast.error(errMsg);
      return null;
    }
  }, [state.imageData, sessionId]);

  /**
   * 清除当前图片和识别结果
   */
  const clearImage = useCallback(() => {
    if (state.previewUrl) {
      URL.revokeObjectURL(state.previewUrl);
    }
    setState({
      isUploading: false,
      previewUrl: null,
      imageData: null,
      recognitionResult: null,
      error: null,
    });
  }, [state.previewUrl]);

  return {
    ...state,
    handleImageFile,
    recognize,
    clearImage,
  };
}
