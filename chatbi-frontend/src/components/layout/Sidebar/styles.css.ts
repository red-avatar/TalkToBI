import { style } from '@vanilla-extract/css';
import { vars } from '../../../styles/theme.css';

export const sidebar = style({ width: '240px', height: '100%', display: 'flex', flexDirection: 'column', background: 'rgba(255, 255, 255, 0.02)', borderRight: `1px solid ${vars.color.border}`, transition: `width ${vars.transition.normal}`, overflow: 'hidden' });
export const collapsed = style({ width: '64px' });
export const nav = style({ flex: 1, padding: vars.space.sm, overflowY: 'auto', overflowX: 'hidden' });
export const menuItem = style({ display: 'flex', alignItems: 'center', gap: vars.space.md, width: '100%', padding: `${vars.space.sm} ${vars.space.md}`, marginBottom: vars.space.xs, background: 'transparent', border: 'none', borderRadius: vars.radius.md, color: vars.color.textSecondary, fontSize: vars.fontSize.sm, cursor: 'pointer', transition: `all ${vars.transition.fast}`, textAlign: 'left', whiteSpace: 'nowrap', selectors: { '&:hover': { background: vars.color.bgHover, color: vars.color.textPrimary } } });
export const active = style({ background: 'rgba(0, 245, 255, 0.1)', color: vars.color.primary, selectors: { '&:hover': { background: 'rgba(0, 245, 255, 0.15)' } } });
export const icon = style({ display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, width: '24px', height: '24px' });
export const label = style({ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' });
export const expandIcon = style({ flexShrink: 0, transition: `transform ${vars.transition.fast}`, color: vars.color.textMuted });
export const expanded = style({ transform: 'rotate(90deg)' });
export const subMenu = style({ marginLeft: vars.space.xl, overflow: 'hidden' });
export const subMenuItem = style({ display: 'flex', alignItems: 'center', gap: vars.space.sm, width: '100%', padding: `${vars.space.xs} ${vars.space.md}`, marginBottom: '2px', background: 'transparent', border: 'none', borderRadius: vars.radius.sm, color: vars.color.textMuted, fontSize: vars.fontSize.sm, cursor: 'pointer', transition: `all ${vars.transition.fast}`, textAlign: 'left', whiteSpace: 'nowrap', selectors: { '&:hover': { background: vars.color.bgHover, color: vars.color.textSecondary } } });
export const collapseBtn = style({ display: 'flex', alignItems: 'center', justifyContent: 'center', margin: vars.space.sm, padding: vars.space.sm, background: vars.color.bgSurface, border: `1px solid ${vars.color.border}`, borderRadius: vars.radius.md, color: vars.color.textMuted, cursor: 'pointer', transition: `all ${vars.transition.fast}`, selectors: { '&:hover': { background: vars.color.bgHover, color: vars.color.textPrimary, borderColor: vars.color.borderHover } } });
