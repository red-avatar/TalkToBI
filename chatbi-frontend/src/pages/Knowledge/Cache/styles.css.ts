import { style, globalStyle } from '@vanilla-extract/css';
import { vars } from '../../../styles/theme.css';

export const container = style({ display: 'flex', flexDirection: 'column', gap: vars.space.lg });
export const header = style({ display: 'flex', alignItems: 'center', justifyContent: 'space-between' });
export const headerLeft = style({ display: 'flex', alignItems: 'center', gap: vars.space.md });
export const title = style({ margin: 0, fontSize: vars.fontSize.xl, fontWeight: 600, color: vars.color.textPrimary });

export const statsGrid = style({ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: vars.space.md });
export const statCard = style({ display: 'flex', alignItems: 'center', gap: vars.space.md });
export const statIcon = style({ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '48px', height: '48px', borderRadius: vars.radius.lg, flexShrink: 0 });
export const statContent = style({ display: 'flex', flexDirection: 'column' });
export const statLabel = style({ fontSize: vars.fontSize.sm, color: vars.color.textMuted });
export const statValue = style({ fontSize: vars.fontSize['2xl'], fontWeight: 700, color: vars.color.textPrimary });

export const toolbar = style({ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: vars.space.md });
export const filters = style({ display: 'flex', alignItems: 'center', gap: vars.space.sm });
export const filterButton = style({ padding: `${vars.space.xs} ${vars.space.md}`, background: 'transparent', border: `1px solid ${vars.color.border}`, borderRadius: vars.radius.md, color: vars.color.textSecondary, fontSize: vars.fontSize.sm, cursor: 'pointer', transition: `all ${vars.transition.fast}`, selectors: { '&:hover': { background: vars.color.bgHover, borderColor: vars.color.borderHover } } });
export const filterButtonActive = style({ background: 'rgba(0, 255, 136, 0.1)', borderColor: vars.color.success, color: vars.color.success });
export const searchInput = style({ padding: `${vars.space.xs} ${vars.space.md}`, width: '240px', background: 'rgba(255, 255, 255, 0.03)', border: `1px solid ${vars.color.border}`, borderRadius: vars.radius.md, color: vars.color.textPrimary, fontSize: vars.fontSize.sm, outline: 'none', transition: `all ${vars.transition.fast}`, selectors: { '&::placeholder': { color: vars.color.textMuted }, '&:focus': { borderColor: vars.color.borderFocus, boxShadow: `0 0 0 2px rgba(0, 245, 255, 0.1)` } } });

export const tableWrapper = style({ overflowX: 'auto' });
export const table = style({ width: '100%', borderCollapse: 'collapse', fontSize: vars.fontSize.sm });

globalStyle(`${table} th, ${table} td`, { padding: `${vars.space.sm} ${vars.space.md}`, textAlign: 'left', borderBottom: `1px solid ${vars.color.border}` });
globalStyle(`${table} th`, { background: 'rgba(0, 255, 136, 0.05)', color: vars.color.textSecondary, fontWeight: 500 });
globalStyle(`${table} td`, { color: vars.color.textPrimary });
globalStyle(`${table} tr:hover td`, { background: vars.color.bgHover });

export const queryCell = style({ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' });
export const sqlCell = style({ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'monospace', fontSize: vars.fontSize.xs, color: vars.color.primary });

export const statusBadge = style({ display: 'inline-flex', padding: `2px ${vars.space.sm}`, borderRadius: vars.radius.sm, fontSize: vars.fontSize.xs, fontWeight: 500 });
export const statusActive = style({ background: 'rgba(0, 255, 136, 0.1)', color: vars.color.success });
export const statusInvalid = style({ background: 'rgba(255, 51, 102, 0.1)', color: vars.color.error });
export const statusDeprecated = style({ background: 'rgba(255, 184, 0, 0.1)', color: vars.color.warning });

export const scoreCell = style({ fontWeight: 600 });
export const actions = style({ display: 'flex', gap: vars.space.xs });
export const emptyState = style({ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: vars.space['2xl'], color: vars.color.textMuted });
export const pagination = style({ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: vars.space.md, marginTop: vars.space.md });
export const pageInfo = style({ fontSize: vars.fontSize.sm, color: vars.color.textMuted });
