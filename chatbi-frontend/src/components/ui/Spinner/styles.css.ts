import { style, keyframes } from '@vanilla-extract/css';
import { recipe } from '@vanilla-extract/recipes';
import { vars } from '../../../styles/theme.css';

const spin = keyframes({
  from: { transform: 'rotate(0deg)' },
  to: { transform: 'rotate(360deg)' },
});

export const spinner = recipe({
  base: {
    display: 'inline-block',
    borderRadius: '50%',
    border: '2px solid transparent',
    borderTopColor: vars.color.primary,
    borderRightColor: vars.color.accent,
    animation: `${spin} 0.8s linear infinite`,
    boxShadow: `0 0 10px rgba(0, 245, 255, 0.3)`,
  },
  
  variants: {
    size: {
      sm: {
        width: '16px',
        height: '16px',
      },
      md: {
        width: '24px',
        height: '24px',
      },
      lg: {
        width: '40px',
        height: '40px',
        borderWidth: '3px',
      },
    },
  },
  
  defaultVariants: {
    size: 'md',
  },
});

export const overlayWrapper = style({
  position: 'relative',
});

export const overlay = style({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: vars.space.md,
  background: 'rgba(10, 10, 15, 0.8)',
  backdropFilter: 'blur(4px)',
  borderRadius: 'inherit',
  zIndex: 10,
});

export const loadingText = style({
  color: vars.color.textSecondary,
  fontSize: vars.fontSize.sm,
});
