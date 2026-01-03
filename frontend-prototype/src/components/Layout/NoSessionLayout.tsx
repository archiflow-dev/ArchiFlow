import { useSessionStore } from '../../store';
import { Zap, Code, Presentation, BookOpen } from 'lucide-react';

export function NoSessionLayout() {
  const { setCurrentSession } = useSessionStore();

  const handleSelectSession = (sessionId: string) => {
    setCurrentSession(sessionId);
  };

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-white">
              ArchiFlow
            </h1>
          </div>
          <p className="text-lg text-gray-400">
            AI-Powered Agent Workflow Management
          </p>
        </div>

        {/* Session Selection */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-8">
          <h2 className="text-xl font-semibold text-white mb-2">
            Select a Session to Continue
          </h2>
          <p className="text-gray-400 mb-6">
            Choose from the mock sessions below to explore different agent workflows:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Comic Agent Session */}
            <SessionCard
              sessionId="comic-session-1"
              agentType="comic"
              title="Comic Generator"
              description="Create a 4-panel comic about a sentient AI"
              prompt="Create a 4-panel comic about an AI algorithm that becomes sentient in a server room"
              status="paused"
              workflowType="Phase-Heavy"
              onSelect={handleSelectSession}
              features={[
                { name: 'Script Generation', status: 'done' },
                { name: 'Visual Specs', status: 'done' },
                { name: 'Character Refs', status: 'paused' },
                { name: 'Panel Generation', status: 'pending' },
                { name: 'PDF Export', status: 'pending' }
              ]}
            />

            {/* Coding Agent Session */}
            <SessionCard
              sessionId="coding-session-1"
              agentType="coding"
              title="Login Authentication"
              description="Implement JWT-based login system"
              prompt="Implement a login authentication system with JWT tokens"
              status="running"
              workflowType="Chat-Heavy"
              onSelect={handleSelectSession}
              features={[
                { name: 'Planning', status: 'done' },
                { name: 'Implementation', status: 'running', progress: 40 },
                { name: 'Review', status: 'pending' }
              ]}
            />

            {/* PPT Agent Session */}
            <SessionCard
              sessionId="ppt-session-1"
              agentType="ppt"
              title="AI Presentation"
              description="Create slides about AI in software development"
              prompt="Create a presentation about AI in software development"
              status="paused"
              workflowType="Phase-Heavy"
              onSelect={handleSelectSession}
              features={[
                { name: 'Outline', status: 'paused' },
                { name: 'Descriptions', status: 'pending' },
                { name: 'Generation', status: 'pending' }
              ]}
            />
          </div>

          {/* Legend */}
          <div className="mt-8 pt-6 border-t border-gray-700">
            <h3 className="text-sm font-medium text-gray-400 mb-3">
              Workflow Types
            </h3>
            <div className="flex gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-blue-500"></div>
                <span className="text-gray-400">
                  <strong className="text-gray-300">Phase-Heavy:</strong> Step-by-step with approvals
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-purple-500"></div>
                <span className="text-gray-400">
                  <strong className="text-gray-300">Chat-Heavy:</strong> Continuous flow with monitoring
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-gray-600">
          ArchiFlow Web App v3 Prototype
        </div>
      </div>
    </div>
  );
}

interface Feature {
  name: string;
  status: 'done' | 'running' | 'paused' | 'pending';
  progress?: number;
}

interface SessionCardProps {
  sessionId: string;
  agentType: string;
  title: string;
  description: string;
  prompt: string;
  status: string;
  workflowType: string;
  onSelect: (sessionId: string) => void;
  features: Feature[];
}

function SessionCard({
  sessionId,
  agentType,
  title,
  description,
  prompt,
  status,
  workflowType,
  onSelect,
  features
}: SessionCardProps) {
  const isPhaseHeavy = workflowType === 'Phase-Heavy';

  const getIcon = () => {
    switch (agentType) {
      case 'comic':
        return <BookOpen className="w-6 h-6" />;
      case 'coding':
        return <Code className="w-6 h-6" />;
      case 'ppt':
        return <Presentation className="w-6 h-6" />;
      default:
        return <Zap className="w-6 h-6" />;
    }
  };

  const getStatusIcon = (s: Feature['status']) => {
    switch (s) {
      case 'done':
        return '✓';
      case 'running':
        return '⟳';
      case 'paused':
        return '⏸';
      default:
        return '○';
    }
  };

  const getStatusColor = (s: Feature['status']) => {
    switch (s) {
      case 'done':
        return 'text-green-400';
      case 'running':
        return 'text-blue-400';
      case 'paused':
        return 'text-yellow-400';
      default:
        return 'text-gray-500';
    }
  };

  return (
    <button
      onClick={() => onSelect(sessionId)}
      className="text-left bg-gray-850 border border-gray-700 rounded-xl p-5 hover:border-blue-500 hover:bg-gray-800 transition-all group"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
          agentType === 'comic' ? 'bg-orange-500/20 text-orange-400' :
          agentType === 'coding' ? 'bg-green-500/20 text-green-400' :
          'bg-purple-500/20 text-purple-400'
        }`}>
          {getIcon()}
        </div>
        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold ${
          isPhaseHeavy ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
        }`}>
          {workflowType}
        </span>
      </div>

      {/* Title & Description */}
      <h3 className="font-semibold text-white mb-1 group-hover:text-blue-400 transition-colors">
        {title}
      </h3>
      <p className="text-sm text-gray-400 mb-3">
        {description}
      </p>

      {/* Prompt */}
      <div className="bg-gray-800 rounded-lg p-3 mb-4 border border-gray-700">
        <p className="text-xs text-gray-300 italic line-clamp-2">
          "{prompt}"
        </p>
      </div>

      {/* Features */}
      <div className="space-y-1.5 mb-4">
        {features.map((feature, idx) => (
          <div key={idx} className="text-xs flex items-center gap-2">
            <span className={`w-4 text-center ${getStatusColor(feature.status)}`}>
              {getStatusIcon(feature.status)}
            </span>
            <span className="text-gray-400">{feature.name}</span>
            {feature.progress !== undefined && (
              <span className="text-blue-400 ml-auto">({feature.progress}%)</span>
            )}
          </div>
        ))}
      </div>

      {/* Status Badge */}
      <div className="flex items-center justify-between">
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
          status === 'running'
            ? 'bg-blue-500/20 text-blue-400'
            : status === 'paused'
            ? 'bg-yellow-500/20 text-yellow-400'
            : 'bg-gray-700 text-gray-400'
        }`}>
          <span>{status === 'running' ? '⟳' : status === 'paused' ? '⏸' : '✓'}</span>
          <span className="capitalize">{status}</span>
        </span>
        <span className="text-xs text-blue-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
          Open →
        </span>
      </div>
    </button>
  );
}
