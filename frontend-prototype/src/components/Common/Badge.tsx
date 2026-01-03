import { cn } from '../../lib/utils';
import { getPhaseStatusColor, getPhaseStatusIcon } from '../../lib/utils';
import type { PhaseStatus } from '../../types';

interface BadgeProps {
  status: PhaseStatus;
  showIcon?: boolean;
  className?: string;
}

export function Badge({ status, showIcon = true, className }: BadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold',
      getPhaseStatusColor(status),
      className
    )}>
      {showIcon && <span className="text-sm">{getPhaseStatusIcon(status)}</span>}
      <span className="capitalize">{status.replace('_', ' ')}</span>
    </span>
  );
}

interface StatusBadgeProps {
  status: 'running' | 'paused' | 'completed' | 'failed';
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const colors = {
    running: 'bg-blue-100 text-blue-800',
    paused: 'bg-yellow-100 text-yellow-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800'
  };

  const icons = {
    running: '⟳',
    paused: '⏸',
    completed: '✓',
    failed: '✕'
  };

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold',
      colors[status],
      className
    )}>
      <span className="text-sm">{icons[status]}</span>
      <span className="capitalize">{status}</span>
    </span>
  );
}
