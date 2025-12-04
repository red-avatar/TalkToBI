import { style } from '@vanilla-extract/css';
import { vars } from '../../../styles/theme.css';

export const shell = style({
  display: 'flex',
  flexDirection: 'column',
  height: '100vh',
  position: 'relative',
  overflow: 'hidden',
});

export const bgGrid = style({
  position: 'fixed',
  inset: 0,
  backgroundImage: `
    linear-gradient(rgba(0, 245, 255, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 245, 255, 0.02) 1px, transparent 1px)
  `,
  backgroundSize: '60px 60px',
  pointerEvents: 'none',
  zIndex: 0,
});

export const mainArea = style({
  display: 'flex',
  flex: 1,
  overflow: 'hidden',
  position: 'relative',
  zIndex: 1,
});

export const content = style({
  flex: 1,
  minHeight: 0,
  overflow: 'hidden',
  padding: vars.space.lg,
  display: 'flex',
  flexDirection: 'column',
});

export const pageWrapper = style({
  flex: 1,
  minHeight: 0,
  display: 'flex',
  flexDirection: 'column',
});
