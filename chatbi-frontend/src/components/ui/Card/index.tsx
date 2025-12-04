import React, { forwardRef } from 'react';
import { motion } from 'framer-motion';
import type { HTMLMotionProps } from 'framer-motion';
import { cn } from '../../../lib/utils';
import * as styles from './styles.css';

export interface CardProps extends Omit<HTMLMotionProps<'div'>, 'ref' | 'children'> {
  children?: React.ReactNode;
  variant?: 'default' | 'glass' | 'bordered' | 'glow';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hoverable?: boolean;
  header?: React.ReactNode;
  footer?: React.ReactNode;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      children,
      variant = 'default',
      padding = 'md',
      hoverable = false,
      header,
      footer,
      className,
      ...props
    },
    ref
  ) => {
    return (
      <motion.div
        ref={ref}
        className={cn(
          styles.card({ variant, padding }),
          hoverable && styles.hoverable,
          className
        )}
        whileHover={hoverable ? { y: -4, scale: 1.01 } : undefined}
        transition={{ duration: 0.2 }}
        {...props}
      >
        {header && <div className={styles.header}>{header}</div>}
        <div className={styles.content}>{children}</div>
        {footer && <div className={styles.footer}>{footer}</div>}
      </motion.div>
    );
  }
);

Card.displayName = 'Card';

// Card Title sub-component
export const CardTitle: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => <h3 className={cn(styles.title, className)}>{children}</h3>;

// Card Description sub-component
export const CardDescription: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => <p className={cn(styles.description, className)}>{children}</p>;

export default Card;
