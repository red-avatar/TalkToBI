import { keyframes, style } from '@vanilla-extract/css';
import { vars } from './theme.css';

// ============================================
// 关键帧动画
// ============================================

export const fadeIn = keyframes({
  from: { opacity: 0 },
  to: { opacity: 1 },
});

export const fadeInUp = keyframes({
  from: { 
    opacity: 0, 
    transform: 'translateY(20px)' 
  },
  to: { 
    opacity: 1, 
    transform: 'translateY(0)' 
  },
});

export const fadeInDown = keyframes({
  from: { 
    opacity: 0, 
    transform: 'translateY(-20px)' 
  },
  to: { 
    opacity: 1, 
    transform: 'translateY(0)' 
  },
});

export const slideInLeft = keyframes({
  from: { 
    opacity: 0, 
    transform: 'translateX(-20px)' 
  },
  to: { 
    opacity: 1, 
    transform: 'translateX(0)' 
  },
});

export const slideInRight = keyframes({
  from: { 
    opacity: 0, 
    transform: 'translateX(20px)' 
  },
  to: { 
    opacity: 1, 
    transform: 'translateX(0)' 
  },
});

export const pulse = keyframes({
  '0%, 100%': { opacity: 1 },
  '50%': { opacity: 0.5 },
});

export const glow = keyframes({
  '0%, 100%': { 
    boxShadow: '0 0 5px rgba(0, 245, 255, 0.5), 0 0 10px rgba(0, 245, 255, 0.3)' 
  },
  '50%': { 
    boxShadow: '0 0 20px rgba(0, 245, 255, 0.8), 0 0 40px rgba(0, 245, 255, 0.4)' 
  },
});

export const shimmer = keyframes({
  '0%': { backgroundPosition: '-200% 0' },
  '100%': { backgroundPosition: '200% 0' },
});

export const spin = keyframes({
  from: { transform: 'rotate(0deg)' },
  to: { transform: 'rotate(360deg)' },
});

export const bounce = keyframes({
  '0%, 100%': { transform: 'translateY(0)' },
  '50%': { transform: 'translateY(-10px)' },
});

export const typing = keyframes({
  '0%, 100%': { opacity: 1 },
  '50%': { opacity: 0 },
});

// 渐变边框流动
export const borderGlow = keyframes({
  '0%': { backgroundPosition: '0% 50%' },
  '50%': { backgroundPosition: '100% 50%' },
  '100%': { backgroundPosition: '0% 50%' },
});

// 网格背景动画
export const gridMove = keyframes({
  '0%': { transform: 'translateY(0)' },
  '100%': { transform: 'translateY(50px)' },
});

// ============================================
// 预定义动画样式类
// ============================================

export const animateFadeIn = style({
  animation: `${fadeIn} 0.3s ease-out`,
});

export const animateFadeInUp = style({
  animation: `${fadeInUp} 0.4s ease-out`,
});

export const animateFadeInDown = style({
  animation: `${fadeInDown} 0.4s ease-out`,
});

export const animateSlideInLeft = style({
  animation: `${slideInLeft} 0.3s ease-out`,
});

export const animateSlideInRight = style({
  animation: `${slideInRight} 0.3s ease-out`,
});

export const animatePulse = style({
  animation: `${pulse} 2s ease-in-out infinite`,
});

export const animateGlow = style({
  animation: `${glow} 2s ease-in-out infinite`,
});

export const animateSpin = style({
  animation: `${spin} 1s linear infinite`,
});

export const animateShimmer = style({
  background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)',
  backgroundSize: '200% 100%',
  animation: `${shimmer} 2s infinite`,
});

// 打字光标
export const typingCursor = style({
  selectors: {
    '&::after': {
      content: '"|"',
      animation: `${typing} 1s step-end infinite`,
      color: vars.color.primary,
      marginLeft: '2px',
    },
  },
});

// ============================================
// 背景效果
// ============================================

// 网格背景
export const gridBackground = style({
  position: 'relative',
  selectors: {
    '&::before': {
      content: '""',
      position: 'absolute',
      inset: 0,
      backgroundImage: `
        linear-gradient(rgba(0, 245, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 245, 255, 0.03) 1px, transparent 1px)
      `,
      backgroundSize: '50px 50px',
      pointerEvents: 'none',
    },
  },
});

// 点阵背景
export const dotBackground = style({
  position: 'relative',
  selectors: {
    '&::before': {
      content: '""',
      position: 'absolute',
      inset: 0,
      backgroundImage: 'radial-gradient(rgba(0, 245, 255, 0.15) 1px, transparent 1px)',
      backgroundSize: '20px 20px',
      pointerEvents: 'none',
    },
  },
});

// 渐变发光边框
export const glowBorder = style({
  position: 'relative',
  selectors: {
    '&::before': {
      content: '""',
      position: 'absolute',
      inset: '-2px',
      background: vars.gradient.primary,
      borderRadius: 'inherit',
      zIndex: -1,
      opacity: 0,
      transition: `opacity ${vars.transition.normal}`,
    },
    '&:hover::before': {
      opacity: 1,
    },
  },
});
