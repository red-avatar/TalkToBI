import { style, keyframes } from '@vanilla-extract/css';
import { vars } from '../../../styles/theme.css';

const glow = keyframes({ '0%, 100%': { boxShadow: '0 0 10px rgba(0, 245, 255, 0.3)' }, '50%': { boxShadow: '0 0 20px rgba(0, 245, 255, 0.5)' } });
export const header = style({ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '60px', padding: `0 ${vars.space.lg}`, background: 'rgba(255, 255, 255, 0.02)', borderBottom: `1px solid ${vars.color.border}`, backdropFilter: 'blur(10px)' });
export const logoSection = style({ display: 'flex', alignItems: 'center', gap: vars.space.md, cursor: 'pointer' });
export const logoIcon = style({ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '36px', height: '36px', background: vars.gradient.primary, borderRadius: vars.radius.md, color: vars.color.textInverse, animation: `${glow} 3s ease-in-out infinite` });
export const logoText = style({ display: 'flex', flexDirection: 'column' });
export const logoTitle = style({ fontSize: vars.fontSize.lg, fontWeight: 700, background: vars.gradient.primary, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text', lineHeight: 1.2 });
export const logoSubtitle = style({ fontSize: vars.fontSize.xs, color: vars.color.textMuted, letterSpacing: '0.5px' });
export const center = style({ flex: 1, display: 'flex', justifyContent: 'center' });
export const tagline = style({ fontSize: vars.fontSize.sm, color: vars.color.textMuted });
export const rightSection = style({ display: 'flex', alignItems: 'center', gap: vars.space.md });
export const userButton = style({ display: 'flex', alignItems: 'center', gap: vars.space.sm, padding: `${vars.space.xs} ${vars.space.md}`, background: vars.color.bgSurface, border: `1px solid ${vars.color.border}`, borderRadius: vars.radius.full, cursor: 'pointer', transition: `all ${vars.transition.fast}`, selectors: { '&:hover': { background: vars.color.bgHover, borderColor: vars.color.borderHover } } });
export const avatar = style({ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '28px', height: '28px', background: vars.gradient.primary, borderRadius: '50%', color: vars.color.textInverse });
export const userName = style({ fontSize: vars.fontSize.sm, color: vars.color.textPrimary });
export const dropdownContent = style({ minWidth: '120px', padding: vars.space.xs, background: vars.color.bgElevated, border: `1px solid ${vars.color.border}`, borderRadius: vars.radius.md, boxShadow: vars.shadow.lg, zIndex: 9999 });
export const dropdownItem = style({ display: 'flex', alignItems: 'center', justifyContent: 'flex-start', gap: vars.space.sm, padding: `${vars.space.sm} ${vars.space.md}`, fontSize: vars.fontSize.sm, color: vars.color.textSecondary, borderRadius: vars.radius.sm, cursor: 'pointer', outline: 'none', transition: `all ${vars.transition.fast}`, whiteSpace: 'nowrap', selectors: { '&:hover': { background: vars.color.bgHover, color: vars.color.textPrimary }, '&:focus': { background: vars.color.bgHover } } });
export const dropdownSeparator = style({ height: '1px', margin: `${vars.space.xs} 0`, background: vars.color.border });
