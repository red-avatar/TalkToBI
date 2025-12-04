import { style } from '@vanilla-extract/css';
import { vars } from '../../styles/theme.css';

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.lg,
});

export const welcomeCard = style({
  background: `linear-gradient(135deg, rgba(0, 245, 255, 0.1) 0%, rgba(189, 0, 255, 0.1) 100%)`,
  borderColor: 'rgba(0, 245, 255, 0.2)',
});

export const welcomeContent = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.lg,
});

export const welcomeTitle = style({
  margin: 0,
  fontSize: vars.fontSize['2xl'],
  fontWeight: 700,
  background: vars.gradient.primary,
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  backgroundClip: 'text',
});

export const welcomeDesc = style({
  margin: `${vars.space.sm} 0 0 0`,
  color: vars.color.textSecondary,
  fontSize: vars.fontSize.md,
});

export const errorCard = style({
  borderColor: vars.color.error,
  background: vars.color.errorBg,
});

export const errorContent = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
  color: vars.color.error,
});

export const sectionHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: vars.space.md,
});

export const sectionTitle = style({
  margin: 0,
  fontSize: vars.fontSize.md,
  fontWeight: 600,
  color: vars.color.textPrimary,
});

export const statusGrid = style({
  display: 'flex',
  gap: vars.space.xl,
});

export const statsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: vars.space.md,
  
  '@media': {
    '(max-width: 1200px)': {
      gridTemplateColumns: 'repeat(2, 1fr)',
    },
    '(max-width: 768px)': {
      gridTemplateColumns: '1fr',
    },
  },
});

export const statCard = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
});

export const statIcon = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '48px',
  height: '48px',
  borderRadius: vars.radius.lg,
  flexShrink: 0,
});

export const statContent = style({
  display: 'flex',
  flexDirection: 'column',
});

export const statLabel = style({
  fontSize: vars.fontSize.sm,
  color: vars.color.textMuted,
});

export const statValue = style({
  fontSize: vars.fontSize['2xl'],
  fontWeight: 700,
  color: vars.color.textPrimary,
});

export const chartsGrid = style({
  display: 'grid',
  gridTemplateColumns: '2fr 1fr',
  gap: vars.space.md,
  
  '@media': {
    '(max-width: 1024px)': {
      gridTemplateColumns: '1fr',
    },
  },
});

export const chartCard = style({
  minHeight: '320px',
});

export const chartTitle = style({
  margin: `0 0 ${vars.space.md} 0`,
  fontSize: vars.fontSize.md,
  fontWeight: 600,
  color: vars.color.textPrimary,
});
