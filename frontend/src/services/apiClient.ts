/**
 * Axios HTTP 客户端实例
 * baseURL = http://localhost:8765
 */
import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';
import toast from 'react-hot-toast';
import type { ApiResponse } from '@/types';

// 开发环境走 Vite proxy（/api → 127.0.0.1:8765），生产环境直连
const BASE_URL = (import.meta as Record<string, any>).env?.DEV
  ? ''
  : 'http://localhost:8765';

const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================
// 请求拦截器
// ============================================================

apiClient.interceptors.request.use(
  (config) => {
    // 可在此处添加认证 token（当前 MVP 不需要）
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// ============================================================
// 响应拦截器
// ============================================================

apiClient.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const data = response.data;

    // 业务错误处理（code != 0）
    if (data && typeof data === 'object' && 'code' in data && data.code !== 0) {
      const errorMsg = data.message || '操作失败';
      // 特定错误码不自动 Toast（由调用方处理）
      const silentCodes = [3000]; // AUTOCAD_NOT_CONNECTED
      if (!silentCodes.includes(data.code)) {
        toast.error(errorMsg);
      }
    }

    return response;
  },
  (error: AxiosError) => {
    if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK') {
      toast.error('无法连接到后端服务，请确保后端已启动');
    } else if (error.response) {
      const status = error.response.status;
      if (status === 404) {
        toast.error('请求的资源不存在');
      } else if (status === 500) {
        toast.error('服务器内部错误，请查看日志');
      } else if (status === 503) {
        toast.error('AutoCAD 未连接，请先连接 AutoCAD');
      }
    } else if (error.code === 'ECONNABORTED') {
      toast.error('请求超时，请重试');
    }
    return Promise.reject(error);
  }
);

export default apiClient;
export { BASE_URL };
