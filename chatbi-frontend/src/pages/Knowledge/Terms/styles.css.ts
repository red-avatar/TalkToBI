import { style, globalStyle } from '@vanilla-extract/css';
import { vars } from '../../../styles/theme.css';

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.lg,
});

export const header = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
});

export const headerLeft = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
});

export const title = style({
  margin: 0,
  fontSize: vars.fontSize.xl,
  fontWeight: 600,
  color: vars.color.textPrimary,
});

export const headerRight = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
});

export const tableWrapper = style({
  overflowX: 'auto',
});

export const table = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: vars.fontSize.sm,
});

globalStyle(`${table} th, ${table} td`, {
  padding: `${vars.space.sm} ${vars.space.md}`,
  textAlign: 'left',
  borderBottom: `1px solid ${vars.color.border}`,
});

globalStyle(`${table} th`, {
  background: 'rgba(189, 0, 255, 0.05)',
  color: vars.color.textSecondary,
  fontWeight: 500,
});

globalStyle(`${table} td`, {
  color: vars.color.textPrimary,
});

globalStyle(`${table} tr:hover td`, {
  background: vars.color.bgHover,
});

export const nameCell = style({
  fontWeight: 600,
  color: vars.color.accent,
});

export const meaningCell = style({
  maxWidth: '300px',
});

export const sqlHint = style({
  fontFamily: 'monospace',
  fontSize: vars.fontSize.xs,
  padding: `${vars.space.xs} ${vars.space.sm}`,
  background: 'rgba(0, 0, 0, 0.3)',
  borderRadius: vars.radius.sm,
  color: vars.color.primary,
});

export const examplesList = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: vars.space.xs,
});

export const exampleTag = style({
  padding: `2px ${vars.space.xs}`,
  background: 'rgba(255, 255, 255, 0.05)',
  borderRadius: vars.radius.sm,
  fontSize: vars.fontSize.xs,
  color: vars.color.textMuted,
});

export const actions = style({
  display: 'flex',
  gap: vars.space.xs,
});

export const emptyState = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: vars.space['2xl'],
  color: vars.color.textMuted,
});

// Modal styles
export const modalOverlay = style({
  position: 'fixed',
  inset: 0,
  background: 'rgba(0, 0, 0, 0.7)',
  backdropFilter: 'blur(4px)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
});

export const modalContent = style({
  width: '90%',
  maxWidth: '800px',
  maxHeight: '90vh',
  overflow: 'auto',
  margin: '0 auto',
});

export const modalHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: vars.space.lg,
});

export const modalTitle = style({
  margin: 0,
  fontSize: vars.fontSize.lg,
  fontWeight: 600,
  color: vars.color.textPrimary,
});

export const formGroup = style({
  marginBottom: vars.space.md,
});

export const formLabel = style({
  display: 'block',
  marginBottom: vars.space.xs,
  fontSize: vars.fontSize.sm,
  color: vars.color.textSecondary,
});

export const formInput = style({
  width: '100%',
  padding: vars.space.sm,
  background: 'rgba(255, 255, 255, 0.03)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.sm,
  outline: 'none',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&::placeholder': { color: vars.color.textMuted },
    '&:focus': {
      borderColor: vars.color.borderFocus,
      boxShadow: `0 0 0 2px rgba(0, 245, 255, 0.1)`,
    },
  },
});

export const formTextarea = style({
  width: '100%',
  padding: vars.space.sm,
  background: 'rgba(255, 255, 255, 0.03)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.sm,
  fontFamily: 'inherit',
  resize: 'vertical',
  minHeight: '120px',
  outline: 'none',
  boxSizing: 'border-box',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&::placeholder': { color: vars.color.textMuted },
    '&:focus': {
      borderColor: vars.color.borderFocus,
      boxShadow: `0 0 0 2px rgba(0, 245, 255, 0.1)`,
    },
  },
});

export const modalFooter = style({
  display: 'flex',
  justifyContent: 'flex-end',
  gap: vars.space.sm,
  marginTop: vars.space.lg,
});

export const pageInfo = style({
  fontSize: vars.fontSize.sm,
  color: vars.color.textMuted,
  marginTop: vars.space.md,
  textAlign: 'right',
});
