/**
 * 自定义下拉选择组件
 * 替代原生select，支持深色主题
 */
import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown } from 'lucide-react';
import { cn } from '../../../lib/utils';
import * as styles from './styles.css';

export interface SelectOption {
  value: string;
  label: string;
}

interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

const CustomSelect: React.FC<CustomSelectProps> = ({
  value,
  onChange,
  options,
  placeholder = '请选择',
  disabled = false,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  // 点击外部关闭（需要同时检查containerRef和dropdownRef）
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      const isInsideContainer = containerRef.current?.contains(target);
      const isInsideDropdown = dropdownRef.current?.contains(target);
      if (!isInsideContainer && !isInsideDropdown) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // 计算下拉位置
  useEffect(() => {
    if (isOpen && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setDropdownStyle({
        position: 'fixed',
        top: rect.bottom + 4,
        left: rect.left,
        width: rect.width,
        maxHeight: '320px',
        overflowY: 'auto',
        zIndex: 10000,
      });
    }
  }, [isOpen]);

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
    }
  };

  const handleSelect = (optValue: string) => {
    onChange(optValue);
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className={cn(styles.customSelectContainer, className)}>
      <div
        className={styles.customSelectTrigger}
        data-open={isOpen}
        data-disabled={disabled}
        onClick={handleToggle}
      >
        {selectedOption ? (
          <span>{selectedOption.label}</span>
        ) : (
          <span className={styles.customSelectPlaceholder}>{placeholder}</span>
        )}
        <span className={styles.customSelectArrow} data-open={isOpen}>
          <ChevronDown size={16} />
        </span>
      </div>
      {isOpen &&
        createPortal(
          <div ref={dropdownRef} className={styles.customSelectDropdown} style={dropdownStyle}>
            {options.map((opt) => (
              <div
                key={opt.value}
                className={styles.customSelectOption}
                data-selected={opt.value === value}
                onClick={() => handleSelect(opt.value)}
              >
                {opt.label}
              </div>
            ))}
          </div>,
          document.body
        )}
    </div>
  );
};

export default CustomSelect;
