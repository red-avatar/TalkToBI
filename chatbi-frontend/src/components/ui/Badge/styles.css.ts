import { style, keyframes } from '@vanilla-extract/css';
import { recipe } from '@vanilla-extract/recipes';
import { vars } from '../../../styles/theme.css';

const pulse = keyframes({
  '0%, 100%': { opacity: 1 },
  '50%': { opacity: 0.5 },
});

export const badge = recipe({
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: vars.space.xs,
    fontWeight: 500,
    borderRadius: vars.radius.full,
  },
  
  variants: {
    variant: {
      default: {
        background: vars.color.bgSurface,
        color: vars.color.textSecondary,
        border: `1px solid ${vars.color.border}`,
      },
      primary: {
        background: vars.color.infoBg,
        color: vars.color.primary,
        border: `1px solid rgba(0, 245, 255, 0.3)`,
      },
      success: {
        background: vars.color.successBg,
        color: vars.color.success,
        border: `1px solid rgba(0, 255, 136, 0.3)`,
      },
      warning: {
        background: vars.color.warningBg,
        color: vars.color.warning,
        border: `1px solid rgba(255, 184, 0, 0.3)`,
      },
      error: {
        background: vars.color.errorBg,
        color: vars.color.error,
        border: `1px solid rgba(255, 51, 102, 0.3)`,
      },
      info: {
        background: vars.color.infoBg,
        color: vars.color.info,
        border: `1px solid rgba(0, 245, 255, 0.3)`,
      },
    },
    
    size: {
      sm: {
        padding: `2px ${vars.space.sm}`,
        fontSize: vars.fontSize.xs,
      },
      md: {
        padding: `4px ${vars.space.md}`,
        fontSize: vars.fontSize.sm,
      },
    },
  },
  
  defaultVariants: {
    variant: 'default',
    size: 'md',
  },
});

export const dot = recipe({
  base: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
  },
  
  variants: {
    variant: {
      default: { background: vars.color.textMuted },
      primary: { background: vars.color.primary },
      success: { background: vars.color.success },
      warning: { background: vars.color.warning },
      error: { background: vars.color.error },
      info: { background: vars.color.info },
    },
  },
});

// Status indicator styles
export const statusWrapper = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: vars.space.sm,
});

export const statusDot = recipe({
  base: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    position: 'relative',
    
    selectors: {
      '&::after': {
        content: '""',
        position: 'absolute',
        inset: '-2px',
        borderRadius: '50%',
        animation: `${pulse} 2s ease-in-out infinite`,
      },
    },
  },
  
  variants: {
    status: {
      online: {
        background: vars.color.success,
        boxShadow: `0 0 8px ${vars.color.success}`,
        selectors: {
          '&::after': {
            background: vars.color.success,
            opacity: 0.3,
          },
        },
      },
      offline: {
        background: vars.color.textMuted,
      },
      busy: {
        background: vars.color.error,
        boxShadow: `0 0 8px ${vars.color.error}`,
        selectors: {
          '&::after': {
            background: vars.color.error,
            opacity: 0.3,
          },
        },
      },
      away: {
        background: vars.color.warning,
        boxShadow: `0 0 8px ${vars.color.warning}`,
      },
    },
  },
});

export const statusLabel = style({
  fontSize: vars.fontSize.sm,
  color: vars.color.textSecondary,
});
