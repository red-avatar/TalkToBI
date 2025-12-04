import { style } from '@vanilla-extract/css';
import { vars } from '../../styles/theme.css';

export const container = style({
  maxWidth: '1200px',
  margin: '0 auto',
});

export const header = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: vars.space.xl,
});

export const title = style({
  fontSize: vars.fontSize['2xl'],
  fontWeight: 700,
  color: vars.color.textPrimary,
});

export const tabs = style({
  display: 'flex',
  gap: vars.space.sm,
  marginBottom: vars.space.lg,
  borderBottom: `1px solid ${vars.color.border}`,
  paddingBottom: vars.space.sm,
});

export const tab = style({
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.md,
  color: vars.color.textMuted,
  fontSize: vars.fontSize.sm,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      color: vars.color.textPrimary,
      background: vars.color.bgHover,
    },
  },
});

export const tabActive = style({
  color: vars.color.primary,
  background: vars.color.infoBg,
});

export const toolbar = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: vars.space.md,
});

export const button = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: vars.gradient.primary,
  border: 'none',
  borderRadius: vars.radius.md,
  color: vars.color.textInverse,
  fontSize: vars.fontSize.sm,
  fontWeight: 600,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      transform: 'translateY(-1px)',
      boxShadow: vars.glow.primary,
    },
  },
});

export const buttonSecondary = style({
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.border}`,
  color: vars.color.textPrimary,
  selectors: {
    '&:hover': {
      background: vars.color.bgHover,
      boxShadow: 'none',
    },
  },
});

export const table = style({
  width: '100%',
  borderCollapse: 'collapse',
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.lg,
  overflow: 'hidden',
});

export const th = style({
  padding: vars.space.md,
  textAlign: 'left',
  fontSize: vars.fontSize.sm,
  fontWeight: 600,
  color: vars.color.textSecondary,
  background: vars.color.bgSurface,
  borderBottom: `1px solid ${vars.color.border}`,
});

export const td = style({
  padding: vars.space.md,
  fontSize: vars.fontSize.sm,
  color: vars.color.textPrimary,
  borderBottom: `1px solid ${vars.color.border}`,
});

export const badge = style({
  display: 'inline-block',
  padding: `${vars.space.xs} ${vars.space.sm}`,
  borderRadius: vars.radius.full,
  fontSize: vars.fontSize.xs,
  fontWeight: 500,
});

export const badgeSuccess = style({
  background: vars.color.successBg,
  color: vars.color.success,
});

export const badgeError = style({
  background: vars.color.errorBg,
  color: vars.color.error,
});

export const badgeInfo = style({
  background: vars.color.infoBg,
  color: vars.color.info,
});

export const actionButton = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  background: 'transparent',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.sm,
  color: vars.color.textSecondary,
  fontSize: vars.fontSize.xs,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      background: vars.color.bgHover,
      color: vars.color.textPrimary,
    },
  },
});

export const pagination = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: vars.space.sm,
  marginTop: vars.space.lg,
});

export const pageButton = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.sm,
  color: vars.color.textSecondary,
  fontSize: vars.fontSize.sm,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      background: vars.color.bgHover,
    },
    '&:disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },
});

export const pageInfo = style({
  fontSize: vars.fontSize.sm,
  color: vars.color.textMuted,
});

// Modal styles
export const modalOverlay = style({
  position: 'fixed',
  inset: 0,
  background: 'rgba(0, 0, 0, 0.7)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 10000,
});

export const modal = style({
  width: '100%',
  maxWidth: '400px',
  padding: vars.space.xl,
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.lg,
});

export const modalTitle = style({
  fontSize: vars.fontSize.lg,
  fontWeight: 600,
  color: vars.color.textPrimary,
  marginBottom: vars.space.lg,
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
  selectors: {
    '&:focus': {
      borderColor: vars.color.primary,
    },
  },
});

export const modalActions = style({
  display: 'flex',
  gap: vars.space.sm,
  justifyContent: 'flex-end',
  marginTop: vars.space.md,
});

export const empty = style({
  padding: vars.space['2xl'],
  textAlign: 'center',
  color: vars.color.textMuted,
  fontSize: vars.fontSize.sm,
});
