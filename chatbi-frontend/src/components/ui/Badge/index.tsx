import React from 'react';
import { cn } from '../../../lib/utils';
import * as styles from './styles.css';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
  dot?: boolean;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  className,
}) => {
  return (
    <span className={cn(styles.badge({ variant, size }), className)}>
      {dot && <span className={styles.dot({ variant })} />}
      {children}
    </span>
  );
};

// Status indicator with pulse animation
export interface StatusIndicatorProps {
  status: 'online' | 'offline' | 'busy' | 'away';
  label?: string;
  className?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  label,
  className,
}) => {
  return (
    <span className={cn(styles.statusWrapper, className)}>
      <span className={styles.statusDot({ status })} />
      {label && <span className={styles.statusLabel}>{label}</span>}
    </span>
  );
};

export default Badge;
