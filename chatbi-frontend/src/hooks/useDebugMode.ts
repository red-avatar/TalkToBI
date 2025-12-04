import { useState, useEffect } from 'react';

// DEBUG模式从后端配置获取，前端通过环境变量或API判断
export function useDebugMode() {
  const [isDebug, setIsDebug] = useState(() => {
    // 优先从localStorage读取（允许用户手动切换）
    const stored = localStorage.getItem('lingxi_debug_mode');
    if (stored !== null) {
      return stored === 'true';
    }
    // 默认根据环境判断
    return import.meta.env.DEV;
  });

  useEffect(() => {
    localStorage.setItem('lingxi_debug_mode', String(isDebug));
  }, [isDebug]);

  const toggleDebug = () => setIsDebug(prev => !prev);

  return { isDebug, setIsDebug, toggleDebug };
}
