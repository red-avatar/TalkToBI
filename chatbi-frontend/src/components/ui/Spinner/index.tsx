import React from 'react';
import { cn } from '../../../lib/utils';
import * as styles from './styles.css';

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className }) => {
  return <span className={cn(styles.spinner({ size }), className)} />;
};

// Loading overlay component
export interface LoadingOverlayProps {
  isLoading: boolean;
  children: React.ReactNode;
  text?: string;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  isLoading,
  children,
  text,
}) => {
  return (
    <div className={styles.overlayWrapper}>
      {children}
      {isLoading && (
        <div className={styles.overlay}>
          <Spinner size="lg" />
          {text && <span className={styles.loadingText}>{text}</span>}
        </div>
      )}
    </div>
  );
};

export default Spinner;
