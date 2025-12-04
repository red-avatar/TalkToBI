import { style, keyframes } from '@vanilla-extract/css';

// Toast通过Portal渲染到body，不在主题作用范围内，所以使用硬编码的颜色值
const colors = {
  bgElevated: '#12121a',
  border: 'rgba(255, 255, 255, 0.08)',
  textPrimary: '#ffffff',
  success: '#00FF88',
  error: '#FF3366',
  warning: '#FFB800',
  info: '#00F5FF',
};

const slideIn = keyframes({
  from: { transform: 'translateX(100%)', opacity: 0 },
  to: { transform: 'translateX(0)', opacity: 1 }
});

const slideOut = keyframes({
  from: { transform: 'translateX(0)', opacity: 1 },
  to: { transform: 'translateX(100%)', opacity: 0 }
});

export const container = style({
  position: 'fixed',
  top: '24px',
  right: '24px',
  zIndex: 99999,
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
  pointerEvents: 'none',
});

export const toast = style({
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '12px 16px',
  background: colors.bgElevated,
  border: `1px solid ${colors.border}`,
  borderRadius: '8px',
  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.6)',
  minWidth: '280px',
  maxWidth: '400px',
  animation: `${slideIn} 0.3s ease`,
  pointerEvents: 'auto',
});

export const toastExiting = style({
  animation: `${slideOut} 0.3s ease forwards`,
});

export const icon = style({
  flexShrink: 0,
});

export const content = style({
  flex: 1,
  fontSize: '14px',
  color: colors.textPrimary,
});

export const success = style({
  borderColor: colors.success,
  selectors: {
    [`&::before`]: {
      content: '""',
      position: 'absolute',
      left: 0,
      top: 0,
      bottom: 0,
      width: '3px',
      background: colors.success,
      borderRadius: '8px 0 0 8px',
    }
  }
});

export const error = style({
  borderColor: colors.error,
});

export const warning = style({
  borderColor: colors.warning,
});

export const info = style({
  borderColor: colors.info,
});

// Modal styles - SweetAlert 风格
export const overlay = style({
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: 'rgba(0, 0, 0, 0.8)',
  backdropFilter: 'blur(4px)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 99999,
  padding: '24px',
});

export const modal = style({
  width: '100%',
  maxWidth: '420px',
  padding: '48px 32px',
  background: colors.bgElevated,
  border: `1px solid ${colors.border}`,
  borderRadius: '16px',
  boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
  textAlign: 'center',
});

export const modalIcon = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '64px',
  height: '64px',
  margin: '0 auto',
  marginBottom: '24px',
  borderRadius: '50%',
  background: 'rgba(255, 51, 102, 0.1)',
  border: '2px solid rgba(255, 51, 102, 0.3)',
});

export const modalTitle = style({
  fontSize: '20px',
  fontWeight: 600,
  color: colors.textPrimary,
  marginBottom: '8px',
});

export const modalMessage = style({
  fontSize: '14px',
  color: 'rgba(255, 255, 255, 0.7)',
  marginBottom: '32px',
  lineHeight: 1.6,
});

export const modalActions = style({
  display: 'flex',
  gap: '16px',
  justifyContent: 'center',
});

export const button = style({
  padding: '8px 32px',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 500,
  cursor: 'pointer',
  transition: 'all 0.15s ease',
  border: 'none',
  minWidth: '100px',
});

export const buttonPrimary = style({
  background: 'linear-gradient(135deg, #00F5FF 0%, #BD00FF 100%)',
  color: '#0a0a0f',
  selectors: {
    '&:hover': {
      transform: 'translateY(-1px)',
      boxShadow: '0 0 20px rgba(0, 245, 255, 0.5), 0 0 40px rgba(0, 245, 255, 0.2)',
    }
  }
});

export const buttonSecondary = style({
  background: 'rgba(255, 255, 255, 0.03)',
  border: `1px solid ${colors.border}`,
  color: colors.textPrimary,
  selectors: {
    '&:hover': {
      background: 'rgba(255, 255, 255, 0.06)',
    }
  }
});

export const buttonDanger = style({
  background: colors.error,
  color: '#fff',
  selectors: {
    '&:hover': {
      boxShadow: '0 0 20px rgba(255, 51, 102, 0.5)',
    }
  }
});
