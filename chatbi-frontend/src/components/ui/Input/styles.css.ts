import { style } from '@vanilla-extract/css';
import { vars } from '../../../styles/theme.css';

export const wrapper = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
});

export const fullWidth = style({
  width: '100%',
});

export const label = style({
  fontSize: vars.fontSize.sm,
  fontWeight: 500,
  color: vars.color.textSecondary,
});

export const inputWrapper = style({
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  transition: `all ${vars.transition.fast}`,
  
  selectors: {
    '&:hover': {
      borderColor: vars.color.borderHover,
    },
    '&:focus-within': {
      borderColor: vars.color.borderFocus,
      boxShadow: `0 0 0 3px rgba(0, 245, 255, 0.1), 0 0 20px rgba(0, 245, 255, 0.1)`,
    },
  },
});

export const hasError = style({
  borderColor: vars.color.error,
  
  selectors: {
    '&:focus-within': {
      borderColor: vars.color.error,
      boxShadow: `0 0 0 3px rgba(255, 51, 102, 0.1)`,
    },
  },
});

export const input = style({
  flex: 1,
  width: '100%',
  height: '40px',
  padding: `0 ${vars.space.md}`,
  background: 'transparent',
  border: 'none',
  outline: 'none',
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.md,
  fontFamily: 'inherit',
  
  selectors: {
    '&::placeholder': {
      color: vars.color.textMuted,
    },
    '&:disabled': {
      cursor: 'not-allowed',
      opacity: 0.5,
    },
  },
});

export const withLeftIcon = style({
  paddingLeft: vars.space.xs,
});

export const withRightIcon = style({
  paddingRight: vars.space.xs,
});

export const iconLeft = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  paddingLeft: vars.space.md,
  color: vars.color.textMuted,
});

export const iconRight = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  paddingRight: vars.space.md,
  color: vars.color.textMuted,
});

export const errorText = style({
  fontSize: vars.fontSize.xs,
  color: vars.color.error,
});

export const textarea = style({
  width: '100%',
  minHeight: '100px',
  padding: vars.space.md,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.md,
  fontFamily: 'inherit',
  resize: 'vertical',
  outline: 'none',
  transition: `all ${vars.transition.fast}`,
  
  selectors: {
    '&::placeholder': {
      color: vars.color.textMuted,
    },
    '&:hover': {
      borderColor: vars.color.borderHover,
    },
    '&:focus': {
      borderColor: vars.color.borderFocus,
      boxShadow: `0 0 0 3px rgba(0, 245, 255, 0.1), 0 0 20px rgba(0, 245, 255, 0.1)`,
    },
    '&:disabled': {
      cursor: 'not-allowed',
      opacity: 0.5,
    },
  },
});
