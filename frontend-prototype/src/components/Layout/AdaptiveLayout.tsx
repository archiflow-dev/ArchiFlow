import { useSessionStore } from '../../store';
import { CreateSessionLayout } from './CreateSessionLayout';
import { VSCodeLayout } from './VSCodeLayout';
import { ApprovalDialog } from '../Common/ApprovalDialog';
import { useEffect } from 'react';

export function AdaptiveLayout() {
  const { currentSession } = useSessionStore();

  // Debug logging
  useEffect(() => {
    console.log('[AdaptiveLayout] currentSession:', currentSession);
  }, [currentSession]);

  // No session selected - show session creation page
  if (!currentSession) {
    console.log('[AdaptiveLayout] Showing CreateSessionLayout (no session)');
    return <CreateSessionLayout />;
  }

  console.log('[AdaptiveLayout] Showing VSCodeLayout with session:', currentSession.session_id);

  // Use unified VSCode-like layout for all session types
  return (
    <>
      <VSCodeLayout />
      <ApprovalDialog />
    </>
  );
}
