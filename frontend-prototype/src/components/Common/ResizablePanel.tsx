import { useState, useCallback, useEffect, useRef } from 'react';
import { cn } from '../../lib/utils';

interface ResizablePanelProps {
  direction: 'horizontal' | 'vertical';
  onResize: (delta: number) => void;
  className?: string;
}

export function ResizablePanel({ direction, onResize, className }: ResizablePanelProps) {
  const [isDragging, setIsDragging] = useState(false);
  const startPosRef = useRef(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    startPosRef.current = direction === 'horizontal' ? e.clientX : e.clientY;
  }, [direction]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const currentPos = direction === 'horizontal' ? e.clientX : e.clientY;
      const delta = currentPos - startPosRef.current;
      startPosRef.current = currentPos;
      onResize(delta);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, direction, onResize]);

  return (
    <div
      className={cn(
        'flex-shrink-0 relative group',
        direction === 'horizontal' ? 'w-1 cursor-col-resize' : 'h-1 cursor-row-resize',
        isDragging && 'bg-blue-500',
        className
      )}
      onMouseDown={handleMouseDown}
    >
      {/* Visual indicator */}
      <div
        className={cn(
          'absolute transition-colors',
          direction === 'horizontal'
            ? 'top-0 bottom-0 left-0 right-0 group-hover:bg-blue-500/50'
            : 'left-0 right-0 top-0 bottom-0 group-hover:bg-blue-500/50',
          isDragging && 'bg-blue-500'
        )}
      />

      {/* Extended hit area */}
      <div
        className={cn(
          'absolute',
          direction === 'horizontal'
            ? 'top-0 bottom-0 -left-1 -right-1'
            : 'left-0 right-0 -top-1 -bottom-1'
        )}
      />
    </div>
  );
}
