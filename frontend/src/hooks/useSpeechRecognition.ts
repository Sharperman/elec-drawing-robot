/**
 * useSpeechRecognition.ts
 * 浏览器语音识别 Hook — P1-01
 *
 * 使用 Web Speech API (SpeechRecognition) 实现实时语音转文字。
 * 浏览器支持：Chrome / Edge (Chromium)
 */

import { useState, useRef, useCallback, useEffect } from 'react';

// SpeechRecognition 接口类型
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  }
}

export interface UseSpeechRecognitionReturn {
  /** 当前是否正在监听 */
  isListening: boolean;
  /** 当前识别文本（实时） */
  transcript: string;
  /** 是否支持语音识别 */
  isSupported: boolean;
  /** 错误信息 */
  error: string | null;
  /** 开始监听 */
  startListening: () => void;
  /** 停止监听并返回最终文本 */
  stopListening: () => string;
  /** 取消监听 */
  cancelListening: () => void;
}

export function useSpeechRecognition(): UseSpeechRecognitionReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const finalTextRef = useRef<string>('');

  const isSupported = !!(
    typeof window !== 'undefined' &&
    (window.SpeechRecognition || window.webkitSpeechRecognition)
  );

  useEffect(() => {
    if (!isSupported) return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'zh-CN';

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = '';
      let final = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          final += result[0]?.transcript ?? '';
        } else {
          interim += result[0]?.transcript ?? '';
        }
      }

      if (final) {
        finalTextRef.current += final;
      }
      setTranscript(finalTextRef.current + interim);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === 'no-speech') {
        // 静默，不报错
        return;
      }
      if (event.error === 'aborted') {
        return;
      }
      setError(`语音识别错误: ${event.error}`);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      try {
        recognition.abort();
      } catch {
        // ignore
      }
    };
  }, [isSupported]);

  const startListening = useCallback(() => {
    if (!recognitionRef.current) return;
    setError(null);
    setTranscript('');
    finalTextRef.current = '';
    try {
      recognitionRef.current.start();
      setIsListening(true);
    } catch {
      // 可能已在监听中
    }
  }, []);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current) return '';
    try {
      recognitionRef.current.stop();
    } catch {
      // ignore
    }
    setIsListening(false);
    const final = finalTextRef.current + transcript.replace(finalTextRef.current, '');
    return final.trim();
  }, [transcript]);

  const cancelListening = useCallback(() => {
    if (!recognitionRef.current) return;
    try {
      recognitionRef.current.abort();
    } catch {
      // ignore
    }
    setIsListening(false);
    setTranscript('');
    finalTextRef.current = '';
  }, []);

  return {
    isListening,
    transcript,
    isSupported,
    error,
    startListening,
    stopListening,
    cancelListening,
  };
}
