import { style } from '@vanilla-extract/css';
import { vars } from '../../styles/theme.css';

export const container = style({
  maxWidth: '600px',
  margin: '0 auto',
});

export const header = style({
  marginBottom: vars.space.xl,
});

export const title = style({
  fontSize: vars.fontSize['2xl'],
  fontWeight: 700,
  color: vars.color.textPrimary,
  marginBottom: vars.space.xs,
});

export const subtitle = style({
  fontSize: vars.fontSize.sm,
  color: vars.color.textMuted,
});

export const card = style({
  padding: vars.space.xl,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.lg,
  marginBottom: vars.space.lg,
});

export const cardTitle = style({
  fontSize: vars.fontSize.lg,
  fontWeight: 600,
  color: vars.color.textPrimary,
  marginBottom: vars.space.lg,
  paddingBottom: vars.space.sm,
  borderBottom: `1px solid ${vars.color.border}`,
});

export const infoRow = style({
  display: 'flex',
  alignItems: 'center',
  padding: `${vars.space.sm} 0`,
});

export const infoLabel = style({
  width: '100px',
  fontSize: vars.fontSize.sm,
  color: vars.color.textMuted,
});

export const infoValue = style({
  flex: 1,
  fontSize: vars.fontSize.sm,
  color: vars.color.textPrimary,
});

export const form = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
});

export const inputGroup = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
});

export const label = style({
  fontSize: vars.fontSize.sm,
  color: vars.color.textSecondary,
});

export const input = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.sm,
  outline: 'none',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:focus': {
      borderColor: vars.color.primary,
    },
  },
});

export const button = style({
  padding: `${vars.space.sm} ${vars.space.lg}`,
  background: vars.gradient.primary,
  border: 'none',
  borderRadius: vars.radius.md,
  color: vars.color.textInverse,
  fontSize: vars.fontSize.sm,
  fontWeight: 600,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  alignSelf: 'flex-start',
  selectors: {
    '&:hover': {
      transform: 'translateY(-1px)',
      boxShadow: vars.glow.primary,
    },
    '&:disabled': {
      opacity: 0.6,
      cursor: 'not-allowed',
      transform: 'none',
    },
  },
});

export const message = style({
  padding: vars.space.sm,
  borderRadius: vars.radius.md,
  fontSize: vars.fontSize.sm,
  textAlign: 'center',
});

export const success = style({
  background: vars.color.successBg,
  border: `1px solid ${vars.color.success}`,
  color: vars.color.success,
});

export const error = style({
  background: vars.color.errorBg,
  border: `1px solid ${vars.color.error}`,
  color: vars.color.error,
});
