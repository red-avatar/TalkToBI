import { style, keyframes } from '@vanilla-extract/css';
import { recipe } from '@vanilla-extract/recipes';
import { vars } from '../../../styles/theme.css';

const spin = keyframes({
  from: { transform: 'rotate(0deg)' },
  to: { transform: 'rotate(360deg)' },
});

export const button = recipe({
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: vars.space.sm,
    fontWeight: 500,
    cursor: 'pointer',
    border: '1px solid transparent',
    transition: `all ${vars.transition.fast}`,
    outline: 'none',
    position: 'relative',
    overflow: 'hidden',
    fontFamily: 'inherit',
    
    selectors: {
      '&:disabled': {
        cursor: 'not-allowed',
        opacity: 0.5,
      },
      '&:focus-visible': {
        boxShadow: `0 0 0 2px ${vars.color.bgBase}, 0 0 0 4px ${vars.color.primary}`,
      },
    },
  },
  
  variants: {
    variant: {
      primary: {
        background: vars.gradient.primary,
        color: vars.color.textInverse,
        border: 'none',
        
        selectors: {
          '&:hover:not(:disabled)': {
            boxShadow: vars.glow.primary,
          },
        },
      },
      
      secondary: {
        background: vars.color.bgSurface,
        color: vars.color.textPrimary,
        borderColor: vars.color.border,
        backdropFilter: 'blur(10px)',
        
        selectors: {
          '&:hover:not(:disabled)': {
            background: vars.color.bgHover,
            borderColor: vars.color.borderHover,
          },
        },
      },
      
      ghost: {
        background: 'transparent',
        color: vars.color.textSecondary,
        
        selectors: {
          '&:hover:not(:disabled)': {
            background: vars.color.bgHover,
            color: vars.color.textPrimary,
          },
        },
      },
      
      danger: {
        background: vars.color.error,
        color: '#ffffff',
        
        selectors: {
          '&:hover:not(:disabled)': {
            boxShadow: vars.glow.error,
          },
        },
      },
      
      success: {
        background: vars.color.success,
        color: vars.color.textInverse,
        
        selectors: {
          '&:hover:not(:disabled)': {
            boxShadow: vars.glow.success,
          },
        },
      },
    },
    
    size: {
      sm: {
        height: '32px',
        padding: `0 ${vars.space.md}`,
        fontSize: vars.fontSize.sm,
        borderRadius: vars.radius.md,
      },
      md: {
        height: '40px',
        padding: `0 ${vars.space.lg}`,
        fontSize: vars.fontSize.md,
        borderRadius: vars.radius.md,
      },
      lg: {
        height: '48px',
        padding: `0 ${vars.space.xl}`,
        fontSize: vars.fontSize.lg,
        borderRadius: vars.radius.lg,
      },
    },
  },
  
  defaultVariants: {
    variant: 'primary',
    size: 'md',
  },
});

export const fullWidth = style({
  width: '100%',
});

export const iconLeft = style({
  display: 'flex',
  marginRight: vars.space.xs,
});

export const iconRight = style({
  display: 'flex',
  marginLeft: vars.space.xs,
});

export const spinner = style({
  width: '16px',
  height: '16px',
  border: '2px solid transparent',
  borderTopColor: 'currentColor',
  borderRadius: '50%',
  animation: `${spin} 0.6s linear infinite`,
});
