/**
 * 知识图谱编辑器样式
 * Author: 陈怡坚
 * Time: 2025-12-03
 */
import { style } from '@vanilla-extract/css';
import { vars } from '../../../styles/theme.css';

export const container = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.lg,
  flex: 1,
  minHeight: 0,
  overflow: 'hidden',
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

export const headerActions = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
});

// 统计卡片
export const statsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(3, 1fr)',
  gap: vars.space.md,
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

// 主编辑区域 - 三栏布局
export const editorWrapper = style({
  display: 'grid',
  gridTemplateColumns: '280px 1fr 320px',
  gap: vars.space.md,
  flex: 1,
  minHeight: 0,
});

// 左侧DDL面板
export const ddlPanel = style({
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  minHeight: 0,
  maxHeight: '100%',
});

export const panelTitle = style({
  fontSize: vars.fontSize.sm,
  fontWeight: 600,
  color: vars.color.textSecondary,
  marginBottom: vars.space.sm,
  padding: `0 ${vars.space.sm}`,
});

export const tableList = style({
  flex: 1,
  minHeight: 0,
  maxHeight: 'calc(100vh - 380px)',
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
});

export const tableItem = style({
  display: 'flex',
  flexDirection: 'column',
  padding: vars.space.sm,
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      background: vars.color.bgHover,
    },
  },
});

export const tableItemActive = style({
  background: 'rgba(0, 245, 255, 0.1)',
  borderLeft: `3px solid ${vars.color.primary}`,
});

export const tableName = style({
  fontSize: vars.fontSize.sm,
  fontWeight: 500,
  color: vars.color.textPrimary,
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
});

export const tableComment = style({
  fontSize: vars.fontSize.xs,
  color: vars.color.textMuted,
  marginTop: '2px',
});

export const columnList = style({
  marginTop: vars.space.xs,
  paddingLeft: vars.space.md,
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
});

export const columnItem = style({
  fontSize: vars.fontSize.xs,
  color: vars.color.textSecondary,
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
});

export const columnType = style({
  color: vars.color.textMuted,
  fontSize: '10px',
});

// 中间画布
export const canvasPanel = style({
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  minHeight: 0,
  maxHeight: '100%',
});

export const canvasContainer = style({
  flex: 1,
  background: 'rgba(0, 0, 0, 0.2)',
  borderRadius: vars.radius.lg,
  position: 'relative',
  overflow: 'hidden',
});

export const canvasToolbar = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: vars.space.sm,
  borderBottom: `1px solid ${vars.color.border}`,
});

export const canvasTools = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
});

export const toolButton = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '32px',
  height: '32px',
  background: 'transparent',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textSecondary,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      background: vars.color.bgHover,
      borderColor: vars.color.borderHover,
      color: vars.color.textPrimary,
    },
  },
});

export const toolButtonActive = style({
  background: 'rgba(0, 245, 255, 0.1)',
  borderColor: vars.color.primary,
  color: vars.color.primary,
});

// 右侧属性面板
export const propertyPanel = style({
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
});

export const propertyEmpty = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  flex: 1,
  color: vars.color.textMuted,
  fontSize: vars.fontSize.sm,
});

export const propertyForm = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
  flex: 1,
  overflowY: 'auto',
});

export const formGroup = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
});

export const formLabel = style({
  fontSize: vars.fontSize.xs,
  fontWeight: 500,
  color: vars.color.textSecondary,
});

export const formInput = style({
  padding: vars.space.sm,
  background: 'rgba(255, 255, 255, 0.03)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.sm,
  outline: 'none',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:focus': {
      borderColor: vars.color.borderFocus,
      boxShadow: `0 0 0 2px rgba(0, 245, 255, 0.1)`,
    },
    '&:disabled': {
      opacity: 0.6,
      cursor: 'not-allowed',
    },
  },
});

export const formSelect = style([formInput, {
  cursor: 'pointer',
  appearance: 'none',
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2300F5FF' d='M6 8L2 4h8z'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 12px center',
  paddingRight: '36px',
  colorScheme: 'dark',
}]);

// 自定义下拉组件
export const customSelectContainer = style({
  position: 'relative',
  width: '100%',
});

export const customSelectTrigger = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: vars.space.sm,
  background: 'rgba(255, 255, 255, 0.03)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.sm,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  minHeight: '38px',
  selectors: {
    '&:hover': {
      borderColor: vars.color.borderHover,
    },
    '&[data-open="true"]': {
      borderColor: vars.color.borderFocus,
      boxShadow: `0 0 0 2px rgba(0, 245, 255, 0.1)`,
    },
    '&[data-disabled="true"]': {
      opacity: 0.6,
      cursor: 'not-allowed',
    },
  },
});

export const customSelectPlaceholder = style({
  color: vars.color.textMuted,
});

export const customSelectDropdown = style({
  position: 'absolute',
  top: '100%',
  left: 0,
  right: 0,
  marginTop: '4px',
  background: 'rgba(20, 20, 30, 0.98)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
  maxHeight: '240px',
  overflowY: 'auto',
  zIndex: 1000,
  backdropFilter: 'blur(16px)',
});

export const customSelectOption = style({
  display: 'flex',
  alignItems: 'flex-start',
  padding: `${vars.space.sm} ${vars.space.md}`,
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.sm,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  lineHeight: 1.4,
  whiteSpace: 'normal',
  wordBreak: 'break-all',
  selectors: {
    '&:hover': {
      background: 'rgba(0, 245, 255, 0.1)',
    },
    '&[data-selected="true"]': {
      background: 'rgba(0, 245, 255, 0.15)',
      color: vars.color.primary,
    },
  },
});

export const customSelectArrow = style({
  display: 'flex',
  alignItems: 'center',
  color: vars.color.primary,
  transition: `transform ${vars.transition.fast}`,
  selectors: {
    '&[data-open="true"]': {
      transform: 'rotate(180deg)',
    },
  },
});

export const formValue = style({
  padding: vars.space.sm,
  background: 'rgba(0, 245, 255, 0.1)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.primary,
  fontSize: vars.fontSize.sm,
  fontFamily: 'monospace',
});

export const formTextarea = style([formInput, {
  resize: 'vertical',
  minHeight: '80px',
}]);

export const confidenceSlider = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
});

export const sliderInput = style({
  flex: 1,
  accentColor: vars.color.primary,
});

export const sliderValue = style({
  minWidth: '40px',
  textAlign: 'right',
  fontSize: vars.fontSize.sm,
  color: vars.color.textPrimary,
});

// 关系列表
export const relationshipList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  flex: 1,
  minHeight: 0,
  maxHeight: 'calc(100vh - 380px)',
  overflowY: 'auto',
  padding: `0 ${vars.space.xs}`,
});

export const relationshipItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  padding: vars.space.sm,
  background: 'rgba(255, 255, 255, 0.02)',
  borderRadius: vars.radius.md,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      background: vars.color.bgHover,
    },
  },
});

export const relationshipItemActive = style({
  background: 'rgba(0, 245, 255, 0.1)',
  border: `1px solid ${vars.color.primary}`,
});

export const relationshipPath = style({
  flex: 1,
  fontSize: vars.fontSize.xs,
  color: vars.color.textPrimary,
});

export const relationshipType = style({
  fontSize: '10px',
  padding: `2px ${vars.space.xs}`,
  background: 'rgba(0, 245, 255, 0.1)',
  borderRadius: vars.radius.sm,
  color: vars.color.primary,
});

export const deleteButton = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '24px',
  height: '24px',
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.sm,
  color: vars.color.textMuted,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      background: 'rgba(255, 0, 0, 0.1)',
      color: '#ff4d4f',
    },
  },
});

// 空状态
export const emptyState = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: vars.space['2xl'],
  color: vars.color.textMuted,
  gap: vars.space.md,
});

// 加载状态
export const loadingOverlay = style({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(0, 0, 0, 0.5)',
  zIndex: 10,
});

// 搜索框
export const searchInput = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  background: 'rgba(255, 255, 255, 0.03)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.md,
  color: vars.color.textPrimary,
  fontSize: vars.fontSize.sm,
  outline: 'none',
  width: '100%',
  marginBottom: vars.space.sm,
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&::placeholder': { color: vars.color.textMuted },
    '&:focus': {
      borderColor: vars.color.borderFocus,
      boxShadow: `0 0 0 2px rgba(0, 245, 255, 0.1)`,
    },
  },
});

// 图形视图
export const graphView = style({
  flex: 1,
  overflow: 'auto',
  background: 'rgba(0, 0, 0, 0.2)',
  borderRadius: vars.radius.md,
  minHeight: '400px',
});

// 弹窗遮罩层
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

// 弹窗内容容器
export const modalContent = style({
  width: '90%',
  maxWidth: '600px',
  maxHeight: '90vh',
  overflow: 'auto',
  margin: '0 auto',
});

// 弹窗
export const modal = style({
  background: 'rgba(30, 30, 40, 0.95)',
  border: `1px solid ${vars.color.border}`,
  borderRadius: vars.radius.lg,
  width: '500px',
  maxWidth: '90vw',
  maxHeight: '90vh',
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column',
});

export const modalHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: vars.space.md,
  borderBottom: `1px solid ${vars.color.border}`,
});

// modalHeader 内的 h3 样式
export const modalTitle = style({
  margin: 0,
  fontSize: vars.fontSize.lg,
  color: vars.color.textPrimary,
});

export const modalClose = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '32px',
  height: '32px',
  background: 'transparent',
  border: 'none',
  borderRadius: vars.radius.md,
  color: vars.color.textMuted,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      background: vars.color.bgHover,
      color: vars.color.textPrimary,
    },
  },
});

export const modalBody = style({
  padding: vars.space.md,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
});

export const modalFooter = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: vars.space.sm,
  padding: vars.space.md,
  borderTop: `1px solid ${vars.color.border}`,
});

export const formRow = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: vars.space.md,
});

// 全屏按钮
export const fullscreenButton = style({
  position: 'absolute',
  bottom: vars.space.md,
  right: vars.space.md,
  width: '40px',
  height: '40px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(0, 245, 255, 0.1)',
  border: `1px solid ${vars.color.primary}`,
  borderRadius: vars.radius.md,
  color: vars.color.primary,
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  zIndex: 10,
  selectors: {
    '&:hover': {
      background: 'rgba(0, 245, 255, 0.2)',
      transform: 'scale(1.05)',
    },
  },
});

// 全屏遮罩
export const fullscreenOverlay = style({
  position: 'fixed',
  inset: 0,
  background: 'rgba(10, 10, 15, 0.98)',
  zIndex: 2000,
  display: 'flex',
  flexDirection: 'column',
});

// 全屏容器
export const fullscreenContainer = style({
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  padding: vars.space.lg,
});

// 全屏头部
export const fullscreenHeader = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: vars.space.lg,
});

export const fullscreenTitle = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.md,
  margin: 0,
  fontSize: vars.fontSize.xl,
  fontWeight: 600,
  color: vars.color.textPrimary,
});

// 全屏内容区
export const fullscreenContent = style({
  display: 'grid',
  gridTemplateColumns: '1fr 400px',
  gap: vars.space.lg,
  flex: 1,
  minHeight: 0,
});

// 全屏图形区
export const fullscreenGraph = style({
  background: 'rgba(0, 0, 0, 0.3)',
  borderRadius: vars.radius.lg,
  overflow: 'hidden',
  minHeight: '600px',
  position: 'relative',
});

// 全屏侧边栏
export const fullscreenSidebar = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.md,
  overflowY: 'auto',
});

export const fullscreenPanel = style({
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  minHeight: 0,
});

// 节点关系列表
export const nodeRelationsList = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
  flex: 1,
  overflowY: 'auto',
});

// 节点关系项
export const nodeRelationItem = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.xs,
  padding: vars.space.sm,
  background: 'rgba(255, 255, 255, 0.02)',
  borderRadius: vars.radius.md,
  border: '1px solid transparent',
  cursor: 'pointer',
  transition: `all ${vars.transition.fast}`,
  selectors: {
    '&:hover': {
      background: 'rgba(0, 245, 255, 0.05)',
      borderColor: 'rgba(0, 245, 255, 0.2)',
    },
  },
});

export const nodeRelationItemActive = style({
  background: 'rgba(0, 245, 255, 0.1)',
  borderColor: vars.color.primary,
});

export const nodeRelationHeader = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.xs,
  fontSize: vars.fontSize.sm,
  color: vars.color.textPrimary,
});

export const nodeRelationDirection = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '24px',
  height: '18px',
  fontSize: '10px',
  fontWeight: 600,
  borderRadius: vars.radius.sm,
  selectors: {
    '&': {
      background: 'rgba(0, 245, 255, 0.2)',
      color: vars.color.primary,
    },
  },
});

export const nodeRelationTarget = style({
  fontWeight: 500,
  color: vars.color.textPrimary,
});

export const nodeRelationInfo = style({
  display: 'flex',
  alignItems: 'center',
  gap: vars.space.sm,
  fontSize: vars.fontSize.xs,
});

export const nodeRelationType = style({
  padding: `2px ${vars.space.xs}`,
  background: 'rgba(189, 0, 255, 0.1)',
  borderRadius: vars.radius.sm,
  color: '#BD00FF',
  fontSize: '10px',
});

export const nodeRelationDesc = style({
  color: vars.color.textMuted,
  flex: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

export const nodeRelationCondition = style({
  fontFamily: 'monospace',
  fontSize: vars.fontSize.xs,
  color: vars.color.primary,
  padding: `${vars.space.xs} ${vars.space.sm}`,
  background: 'rgba(0, 0, 0, 0.3)',
  borderRadius: vars.radius.sm,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});
