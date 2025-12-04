/**
 * React Flow 图形视图样式
 * Author: 陈怡坚
 * Time: 2025-12-03
 */
import { style, globalStyle } from '@vanilla-extract/css';
import { vars } from '../../../styles/theme.css';

export const graphContainer = style({
  width: '100%',
  height: '100%',
  minHeight: '400px',
  background: 'rgba(0, 0, 0, 0.3)',
  borderRadius: vars.radius.md,
  overflow: 'hidden',
});

// 自定义表节点样式
export const tableNode = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: `${vars.space.sm} ${vars.space.md}`,
  background: 'rgba(20, 20, 35, 0.95)',
  border: '2px solid rgba(0, 245, 255, 0.4)',
  borderRadius: vars.radius.lg,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  minWidth: '140px',
  selectors: {
    '&:hover': {
      borderColor: '#00F5FF',
      boxShadow: '0 0 20px rgba(0, 245, 255, 0.3)',
      transform: 'scale(1.02)',
    },
  },
});

export const tableNodeSelected = style({
  borderColor: '#00F5FF',
  boxShadow: '0 0 30px rgba(0, 245, 255, 0.5)',
  background: 'rgba(0, 245, 255, 0.1)',
});

export const tableNodeIcon = style({
  fontSize: '18px',
  flexShrink: 0,
});

export const tableNodeLabel = style({
  flex: 1,
  fontSize: vars.fontSize.sm,
  fontWeight: 500,
  color: vars.color.textPrimary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

export const tableNodeBadge = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: '20px',
  height: '20px',
  padding: '0 6px',
  background: 'rgba(0, 245, 255, 0.2)',
  borderRadius: '10px',
  fontSize: '10px',
  fontWeight: 600,
  color: '#00F5FF',
});

// 连接点样式
export const handle = style({
  width: '10px',
  height: '10px',
  background: 'rgba(0, 245, 255, 0.6)',
  border: '2px solid #00F5FF',
  borderRadius: '50%',
  opacity: 0,
  transition: `opacity ${vars.transition.fast}`,
});

// 控制面板样式
export const controls = style({});

// 小地图样式
export const minimap = style({
  borderRadius: vars.radius.md,
  overflow: 'hidden',
  border: `1px solid ${vars.color.border}`,
});

// React Flow 全局样式覆盖
globalStyle(`${graphContainer} .react-flow__node:hover ${handle}`, {
  opacity: 1,
});

globalStyle(`${graphContainer} .react-flow__edge-path`, {
  strokeLinecap: 'round',
});

globalStyle(`${graphContainer} .react-flow__edge:hover .react-flow__edge-path`, {
  stroke: '#00F5FF',
  strokeWidth: 3,
});

globalStyle(`${graphContainer} .react-flow__controls`, {
  background: 'rgba(20, 20, 35, 0.9)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  overflow: 'hidden',
});

globalStyle(`${graphContainer} .react-flow__controls-button`, {
  background: 'transparent',
  border: 'none',
  borderBottom: `1px solid ${vars.color.border}`,
  color: vars.color.textSecondary,
  width: '30px',
  height: '30px',
  padding: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
});

globalStyle(`${graphContainer} .react-flow__controls-button:last-child`, {
  borderBottom: 'none',
});

globalStyle(`${graphContainer} .react-flow__controls-button:hover`, {
  background: 'rgba(0, 245, 255, 0.1)',
  color: '#00F5FF',
});

globalStyle(`${graphContainer} .react-flow__controls-button svg`, {
  fill: 'currentColor',
  width: '14px',
  height: '14px',
});

globalStyle(`${graphContainer} .react-flow__minimap`, {
  background: 'rgba(20, 20, 35, 0.9)',
});

globalStyle(`${graphContainer} .react-flow__background`, {
  background: 'transparent',
});
