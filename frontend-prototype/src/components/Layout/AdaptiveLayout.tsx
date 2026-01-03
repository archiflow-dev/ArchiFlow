import { useSessionStore } from '../../store';
import { CreateSessionLayout } from './CreateSessionLayout';
import { VSCodeLayout } from './VSCodeLayout';
import { ApprovalDialog } from '../Common/ApprovalDialog';

export function AdaptiveLayout() {
  const { currentSession } = useSessionStore();

  // No session selected - show session creation page
  if (!currentSession) {
    return <CreateSessionLayout />;
  }

  // Use unified VSCode-like layout for all session types
  return (
    <>
      <VSCodeLayout />
      <ApprovalDialog />
    </>
  );
}
