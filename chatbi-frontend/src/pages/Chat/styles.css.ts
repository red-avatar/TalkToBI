import { style, keyframes, globalStyle } from '@vanilla-extract/css';
import { recipe } from '@vanilla-extract/recipes';
import { vars } from '../../styles/theme.css';

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  minHeight: 0,
  position: 'relative',
  overflow: 'hidden',
});

export const header = style({
  flexShrink: 0,
  padding: vars.space.md,
  background: 'rgba(255, 255, 255, 0.02)',
  borderBottom: `1px solid ${vars.color.border}`,
  backdropFilter: 'blur(10px)',
});

export const headerMain = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.lg,
});

export const headerLeft = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
});

export const headerIcon = style({
  color: vars.color.primary,
});

export const headerTitleGroup = style({
  display: 'flex',
  flexDirection: 'column',
});

export const title = style({
  margin: 0,
  fontSize: vars.fontSize.lg,
  fontWeight: 600,
  color: vars.color.textPrimary,
  lineHeight: 1.2,
});

export const sessionId = style({
  fontSize: vars.fontSize.xs,
  color: vars.color.textMuted,
});

export const headerCenter = style({
  flex: 1,
  display: 'flex',
  justifyContent: 'center',
});

export const headerRight = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
});

export const messageList = style({
  flex: 1,
  minHeight: 0,
  overflowY: 'auto',
  padding: vars.space.lg,
  paddingBottom: vars.space.xl,
});

export const emptyState = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100%',
  gap: vars.space.md,
  color: vars.color.textMuted,
});

const glowPulse = keyframes({
  '0%, 100%': { opacity: 0.5 },
  '50%': { opacity: 1 },
});

export const emptyIcon = style({
  color: vars.color.primary,
  animation: `${glowPulse} 2s ease-in-out infinite`,
});

export const messageItem = recipe({
  base: {
    display: 'flex',
    gap: vars.space.md,
    marginBottom: vars.space.lg,
  },
  variants: {
    isUser: {
      true: {
        flexDirection: 'row-reverse',
      },
      false: {
        flexDirection: 'row',
      },
    },
  },
});

export const avatar = recipe({
  base: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '36px',
    height: '36px',
    borderRadius: vars.radius.lg,
    flexShrink: 0,
  },
  variants: {
    isUser: {
      true: {
        background: vars.gradient.accent,
        color: '#fff',
      },
      false: {
        background: vars.gradient.primary,
        color: vars.color.textInverse,
      },
    },
  },
});

export const messageBubble = recipe({
  base: {
    maxWidth: '80%',
    padding: vars.space.md,
    borderRadius: vars.radius.lg,
  },
  variants: {
    isUser: {
      true: {
        background: 'rgba(189, 0, 255, 0.15)',
        borderBottomRightRadius: vars.radius.sm,
        border: '1px solid rgba(189, 0, 255, 0.3)',
      },
      false: {
        background: vars.color.bgSurface,
        borderBottomLeftRadius: vars.radius.sm,
        border: `1px solid ${vars.color.border}`,
      },
    },
  },
});

export const messageText = style({
  margin: 0,
  fontSize: vars.fontSize.md,
  lineHeight: 1.6,
  color: vars.color.textPrimary,
});

export const assistantContent = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
});

export const inlineSpinner = style({
  marginRight: vars.space.sm,
});

export const highlights = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: vars.space.xs,
});

export const codeSection = style({
  marginTop: vars.space.sm,
});

export const sectionToggle = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.xs} ${vars.space.sm}`,
  background: 'rgba(255, 255, 255, 0.03)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textSecondary,
  fontSize: vars.fontSize.sm,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  width: '100%',
  
  selectors: {
    '&:hover': {
      background: vars.color.bgHover,
      color: vars.color.textPrimary,
    },
  },
});

export const codeBlock = style({
  margin: `${vars.space.sm} 0 0 0`,
  padding: vars.space.md,
  background: 'rgba(0, 0, 0, 0.3)',
  borderRadius: vars.radius.md,
  fontSize: vars.fontSize.xs,
  fontFamily: 'monospace',
  color: vars.color.primary,
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
});

export const debugContent = style({
  overflow: 'hidden',
});

export const debugLabel = style({
  fontSize: vars.fontSize.xs,
  color: vars.color.textMuted,
  marginTop: vars.space.sm,
});

export const tableWrapper = style({
  overflowX: 'auto',
  marginTop: vars.space.sm,
});

export const dataTable = style({
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: vars.fontSize.sm,
});

globalStyle(`${dataTable} th, ${dataTable} td`, {
  padding: `${vars.space.xs} ${vars.space.sm}`,
  textAlign: 'left',
  borderBottom: `1px solid ${vars.color.border}`,
});

globalStyle(`${dataTable} th`, {
  background: 'rgba(0, 245, 255, 0.05)',
  color: vars.color.textSecondary,
  fontWeight: 500,
});

globalStyle(`${dataTable} td`, {
  color: vars.color.textPrimary,
});

globalStyle(`${dataTable} tr:hover td`, {
  background: vars.color.bgHover,
});

export const tableMore = style({
  margin: `${vars.space.sm} 0 0 0`,
  fontSize: vars.fontSize.xs,
  color: vars.color.textMuted,
  textAlign: 'center',
});

export const chartCard = style({
  marginTop: vars.space.sm,
});

export const inputArea = style({
  flexShrink: 0,
  padding: vars.space.md,
  paddingTop: vars.space.lg,
  background: vars.color.bgBase,
  borderTop: `1px solid ${vars.color.border}`,
});

export const inputWrapper = style({
  display: 'flex',
  alignItems: 'flex-end',
  gap: vars.space.md,
  padding: vars.space.sm,
  background: 'rgba(255, 255, 255, 0.03)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.lg,
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:focus-within': {
      borderColor: vars.color.borderFocus,
      boxShadow: `0 0 0 3px rgba(0, 245, 255, 0.1)`,
    },
  },
});

export const input = style({
  flex: 1,
  padding: vars.space.sm,
  background: 'transparent',
  border: 'none',
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.md,
  fontFamily: 'inherit',
  resize: 'none',
  outline: 'none',
  minHeight: '40px',
  maxHeight: '120px',
  lineHeight: 1.5,
  selectors: {
    '&::placeholder': {
      color: vars.color.textMuted,
    },
    '&:disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },
});

export const sendButton = style({
  flexShrink: 0,
});

export const inputHint = style({
  margin: `${vars.space.xs} 0 0 0`,
  fontSize: vars.fontSize.xs,
  color: vars.color.textMuted,
  textAlign: 'center',
});
