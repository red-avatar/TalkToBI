import { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react';
import * as styles from './styles.css';

// Toast 类型
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
  exiting?: boolean;
}

// 确认弹窗配置
interface ConfirmConfig {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  onConfirm: () => void | Promise<void>;
}

interface ToastContextType {
  toast: {
    success: (message: string) => void;
    error: (message: string) => void;
    warning: (message: string) => void;
    info: (message: string) => void;
  };
  confirm: (config: ConfirmConfig) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

let toastId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [confirmConfig, setConfirmConfig] = useState<ConfirmConfig | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, type, message }]);
    
    // 3秒后开始退出动画
    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t));
      // 动画结束后移除
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 300);
    }, 3000);
  }, []);

  const toast = {
    success: (message: string) => addToast('success', message),
    error: (message: string) => addToast('error', message),
    warning: (message: string) => addToast('warning', message),
    info: (message: string) => addToast('info', message),
  };

  const confirm = useCallback((config: ConfirmConfig) => {
    setConfirmConfig(config);
  }, []);

  const handleConfirm = async () => {
    if (!confirmConfig) return;
    setConfirmLoading(true);
    try {
      await confirmConfig.onConfirm();
      setConfirmConfig(null);
    } catch (error: any) {
      // 显示错误提示
      addToast('error', error?.message || '操作失败');
      setConfirmConfig(null);
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleCancel = () => {
    setConfirmConfig(null);
  };

  const getIcon = (type: ToastType) => {
    switch (type) {
      case 'success': return <CheckCircle size={18} color="#00FF88" />;
      case 'error': return <XCircle size={18} color="#FF3366" />;
      case 'warning': return <AlertCircle size={18} color="#FFB800" />;
      case 'info': return <Info size={18} color="#00F5FF" />;
    }
  };

  return (
    <ToastContext.Provider value={{ toast, confirm }}>
      {children}
      
      {/* Toast 容器 */}
      {createPortal(
        <div className={styles.container}>
          {toasts.map(t => (
            <div 
              key={t.id} 
              className={`${styles.toast} ${styles[t.type]} ${t.exiting ? styles.toastExiting : ''}`}
            >
              <span className={styles.icon}>{getIcon(t.type)}</span>
              <span className={styles.content}>{t.message}</span>
            </div>
          ))}
        </div>,
        document.body
      )}

      {/* 确认弹窗 */}
      {confirmConfig && createPortal(
        <div className={styles.overlay} onClick={handleCancel}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalIcon}>
              <AlertCircle size={32} color="#FF3366" />
            </div>
            <h3 className={styles.modalTitle}>{confirmConfig.title}</h3>
            <p className={styles.modalMessage}>{confirmConfig.message}</p>
            <div className={styles.modalActions}>
              <button 
                className={`${styles.button} ${styles.buttonSecondary}`}
                onClick={handleCancel}
                disabled={confirmLoading}
              >
                {confirmConfig.cancelText || '取消'}
              </button>
              <button 
                className={`${styles.button} ${confirmConfig.danger ? styles.buttonDanger : styles.buttonPrimary}`}
                onClick={handleConfirm}
                disabled={confirmLoading}
              >
                {confirmLoading ? '处理中...' : (confirmConfig.confirmText || '确定')}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
