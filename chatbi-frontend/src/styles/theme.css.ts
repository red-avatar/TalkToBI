import { createTheme, createGlobalTheme, globalStyle, createThemeContract } from '@vanilla-extract/css';

// ============================================
// 主题契约 - 定义所有可变的主题变量
// ============================================
export const vars = createThemeContract({
  color: {
    // 品牌色
    primary: null,
    primaryHover: null,
    primaryActive: null,
    accent: null,
    accentHover: null,
    
    // 语义色
    success: null,
    successBg: null,
    warning: null,
    warningBg: null,
    error: null,
    errorBg: null,
    info: null,
    infoBg: null,
    
    // 背景色
    bgBase: null,
    bgElevated: null,
    bgSurface: null,
    bgHover: null,
    bgActive: null,
    
    // 边框
    border: null,
    borderHover: null,
    borderFocus: null,
    
    // 文字
    textPrimary: null,
    textSecondary: null,
    textMuted: null,
    textDisabled: null,
    textInverse: null,
  },
  
  // 渐变
  gradient: {
    primary: null,
    accent: null,
    glow: null,
    surface: null,
  },
  
  // 发光效果
  glow: {
    primary: null,
    accent: null,
    success: null,
    error: null,
  },
  
  // 间距
  space: {
    xs: null,
    sm: null,
    md: null,
    lg: null,
    xl: null,
    '2xl': null,
    '3xl': null,
  },
  
  // 圆角
  radius: {
    sm: null,
    md: null,
    lg: null,
    xl: null,
    full: null,
  },
  
  // 字体大小
  fontSize: {
    xs: null,
    sm: null,
    md: null,
    lg: null,
    xl: null,
    '2xl': null,
    '3xl': null,
  },
  
  // 阴影
  shadow: {
    sm: null,
    md: null,
    lg: null,
    glow: null,
  },
  
  // 过渡
  transition: {
    fast: null,
    normal: null,
    slow: null,
  },
});

// ============================================
// 深色主题 - AI 科技感
// ============================================
export const darkTheme = createTheme(vars, {
  color: {
    // 品牌色 - 霓虹青
    primary: '#00F5FF',
    primaryHover: '#33F7FF',
    primaryActive: '#00D4DD',
    accent: '#BD00FF',
    accentHover: '#D033FF',
    
    // 语义色 - 霓虹风格
    success: '#00FF88',
    successBg: 'rgba(0, 255, 136, 0.1)',
    warning: '#FFB800',
    warningBg: 'rgba(255, 184, 0, 0.1)',
    error: '#FF3366',
    errorBg: 'rgba(255, 51, 102, 0.1)',
    info: '#00F5FF',
    infoBg: 'rgba(0, 245, 255, 0.1)',
    
    // 背景色 - 深黑
    bgBase: '#0a0a0f',
    bgElevated: '#12121a',
    bgSurface: 'rgba(255, 255, 255, 0.03)',
    bgHover: 'rgba(255, 255, 255, 0.06)',
    bgActive: 'rgba(255, 255, 255, 0.08)',
    
    // 边框
    border: 'rgba(255, 255, 255, 0.08)',
    borderHover: 'rgba(255, 255, 255, 0.15)',
    borderFocus: '#00F5FF',
    
    // 文字
    textPrimary: '#ffffff',
    textSecondary: 'rgba(255, 255, 255, 0.7)',
    textMuted: 'rgba(255, 255, 255, 0.5)',
    textDisabled: 'rgba(255, 255, 255, 0.3)',
    textInverse: '#0a0a0f',
  },
  
  gradient: {
    primary: 'linear-gradient(135deg, #00F5FF 0%, #BD00FF 100%)',
    accent: 'linear-gradient(135deg, #BD00FF 0%, #FF3366 100%)',
    glow: 'radial-gradient(ellipse at center, rgba(0, 245, 255, 0.15) 0%, transparent 70%)',
    surface: 'linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
  },
  
  glow: {
    primary: '0 0 20px rgba(0, 245, 255, 0.5), 0 0 40px rgba(0, 245, 255, 0.2)',
    accent: '0 0 20px rgba(189, 0, 255, 0.5), 0 0 40px rgba(189, 0, 255, 0.2)',
    success: '0 0 20px rgba(0, 255, 136, 0.5)',
    error: '0 0 20px rgba(255, 51, 102, 0.5)',
  },
  
  space: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
    '3xl': '64px',
  },
  
  radius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },
  
  fontSize: {
    xs: '12px',
    sm: '14px',
    md: '16px',
    lg: '18px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '32px',
  },
  
  shadow: {
    sm: '0 1px 2px rgba(0, 0, 0, 0.5)',
    md: '0 4px 12px rgba(0, 0, 0, 0.5)',
    lg: '0 8px 24px rgba(0, 0, 0, 0.6)',
    glow: '0 0 30px rgba(0, 245, 255, 0.3)',
  },
  
  transition: {
    fast: '0.15s ease',
    normal: '0.25s ease',
    slow: '0.4s ease',
  },
});

// ============================================
// 全局样式应用
// ============================================
globalStyle(':root', {
  colorScheme: 'dark',
});

globalStyle('html, body', {
  margin: 0,
  padding: 0,
  height: '100%',
  overflow: 'hidden',
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
  WebkitFontSmoothing: 'antialiased',
  MozOsxFontSmoothing: 'grayscale',
});

globalStyle('body', {
  background: `
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0, 245, 255, 0.1), transparent),
    radial-gradient(ellipse 60% 40% at 80% 50%, rgba(189, 0, 255, 0.05), transparent),
    ${vars.color.bgBase}
  `,
  color: vars.color.textPrimary,
});

globalStyle('#root', {
  height: '100%',
  overflow: 'hidden',
});

globalStyle('*', {
  boxSizing: 'border-box',
});

globalStyle('::selection', {
  background: 'rgba(0, 245, 255, 0.3)',
  color: '#ffffff',
});

// 滚动条
globalStyle('::-webkit-scrollbar', {
  width: '6px',
  height: '6px',
});

globalStyle('::-webkit-scrollbar-track', {
  background: 'transparent',
});

globalStyle('::-webkit-scrollbar-thumb', {
  background: 'rgba(255, 255, 255, 0.2)',
  borderRadius: '3px',
});

globalStyle('::-webkit-scrollbar-thumb:hover', {
  background: 'rgba(255, 255, 255, 0.3)',
});

// 链接
globalStyle('a', {
  color: vars.color.primary,
  textDecoration: 'none',
});

globalStyle('a:hover', {
  color: vars.color.primaryHover,
});
