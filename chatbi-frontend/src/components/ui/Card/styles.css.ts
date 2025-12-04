import { style } from '@vanilla-extract/css';
import { recipe } from '@vanilla-extract/recipes';
import { vars } from '../../../styles/theme.css';

export const card = recipe({
  base: {
    borderRadius: vars.radius.lg,
    transition: `all ${vars.transition.normal}`,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  
  variants: {
    variant: {
      default: {
        background: vars.color.bgElevated,
        border: `1px solid ${vars.color.border}`,
      },
      
      glass: {
        background: 'rgba(255, 255, 255, 0.03)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: `1px solid ${vars.color.border}`,
      },
      
      bordered: {
        background: 'transparent',
        border: `1px solid ${vars.color.border}`,
      },
      
      glow: {
        background: vars.color.bgElevated,
        border: `1px solid ${vars.color.border}`,
        boxShadow: vars.shadow.glow,
      },
    },
    
    padding: {
      none: {},
      sm: {},
      md: {},
      lg: {},
    },
  },
  
  compoundVariants: [
    { variants: { padding: 'sm' }, style: { padding: vars.space.sm } },
    { variants: { padding: 'md' }, style: { padding: vars.space.md } },
    { variants: { padding: 'lg' }, style: { padding: vars.space.lg } },
  ],
  
  defaultVariants: {
    variant: 'default',
    padding: 'md',
  },
});

export const hoverable = style({
  cursor: 'pointer',
  
  selectors: {
    '&:hover': {
      borderColor: vars.color.borderHover,
      boxShadow: `0 8px 32px rgba(0, 0, 0, 0.3), ${vars.shadow.glow}`,
    },
  },
});

export const header = style({
  padding: vars.space.md,
  borderBottom: `1px solid ${vars.color.border}`,
});

export const content = style({
  // padding handled by card recipe
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  minHeight: 0,
  overflow: 'hidden',
});

export const footer = style({
  padding: vars.space.md,
  borderTop: `1px solid ${vars.color.border}`,
});

export const title = style({
  margin: 0,
  fontSize: vars.fontSize.lg,
  fontWeight: 600,
  color: vars.color.textPrimary,
  marginBottom: vars.space.xs,
});

export const description = style({
  margin: 0,
  fontSize: vars.fontSize.sm,
  color: vars.color.textSecondary,
});
