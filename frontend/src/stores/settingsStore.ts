/**
 * Settings Store - API Key、LLM 配置、用户偏好、布局状态
 * 扩展版：添加 sidebarCollapsed / previewCollapsed 供 AppShell 使用
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AppSettings } from '@/types';

interface SettingsState {
  settings: AppSettings;
  // 布局折叠状态
  sidebarCollapsed: boolean;
  previewCollapsed: boolean;
}

interface SettingsActions {
  updateSettings: (partial: Partial<AppSettings>) => void;
  resetSettings: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setPreviewCollapsed: (collapsed: boolean) => void;
}

const defaultSettings: AppSettings = {
  openaiApiKey: '',
  openaiBaseUrl: 'https://api.openai.com/v1',
  modelName: 'gpt-4o',
  autocadVersion: 'AutoCAD.Application',
  theme: 'dark',
  language: 'zh',
  autoConnectAutocad: false,
  snapshotInterval: 5,
};

export const useSettingsStore = create<SettingsState & SettingsActions>()(
  persist(
    (set) => ({
      settings: defaultSettings,
      sidebarCollapsed: false,
      previewCollapsed: false,

      updateSettings: (partial) => {
        set((state) => ({
          settings: { ...state.settings, ...partial },
        }));
      },

      resetSettings: () => {
        set({ settings: defaultSettings });
      },

      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setPreviewCollapsed: (collapsed) => set({ previewCollapsed: collapsed }),
    }),
    {
      name: 'app-settings',
    }
  )
);
