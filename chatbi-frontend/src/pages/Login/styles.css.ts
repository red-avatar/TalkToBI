import { style, keyframes } from '@vanilla-extract/css';
import { vars } from '../../styles/theme.css';

const glow = keyframes({
  '0%, 100%': { boxShadow: '0 0 20px rgba(0, 245, 255, 0.3)' },
  '50%': { boxShadow: '0 0 40px rgba(0, 245, 255, 0.5)' }
});

export const container = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '100vh',
  background: `
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0, 245, 255, 0.15), transparent),
    radial-gradient(ellipse 60% 40% at 80% 50%, rgba(189, 0, 255, 0.08), transparent),
    ${vars.color.bgBase}
  `,
});

export const card = style({
  width: '100%',
  maxWidth: '400px',
  padding: vars.space['2xl'],
  background: vars.color.bgElevated,
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.xl,
  boxShadow: vars.shadow.lg,
});

export const logo = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  marginBottom: vars.space.xl,
});

export const logoIcon = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '64px',
  height: '64px',
  background: vars.gradient.primary,
  borderRadius: vars.radius.lg,
  color: vars.color.textInverse,
  marginBottom: vars.space.md,
  animation: `${glow} 3s ease-in-out infinite`,
});

export const logoTitle = style({
  fontSize: vars.fontSize['2xl'],
  fontWeight: 700,
  background: vars.gradient.primary,
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  backgroundClip: 'text',
});

export const logoSubtitle = style({
  fontSize: vars.fontSize.sm,
  color: vars.color.textMuted,
  marginTop: vars.space.xs,
});

export const form = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.lg,
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
  fontSize: vars.fontSize.md,
  outline: 'none',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:focus': {
      borderColor: vars.color.primary,
      boxShadow: `0 0 0 2px ${vars.color.infoBg}`,
    },
    '&::placeholder': {
      color: vars.color.textMuted,
    },
  },
});

export const button = style({
  padding: `${vars.space.sm} ${vars.space.lg}`,
  background: vars.gradient.primary,
  border: 'none',
  borderRadius: vars.radius.md,
  color: vars.color.textInverse,
  fontSize: vars.fontSize.md,
  fontWeight: 600,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  marginTop: vars.space.sm,
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

export const error = style({
  padding: vars.space.sm,
  background: vars.color.errorBg,
  border: `1px solid ${vars.color.error}`,
  borderRadius: vars.radius.md,
  color: vars.color.error,
  fontSize: vars.fontSize.sm,
  textAlign: 'center',
});
