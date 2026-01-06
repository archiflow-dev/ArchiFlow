import { useState, useMemo } from 'react';
import {
  Zap,
  Presentation,
  BookOpen,
  Search,
  FileSearch,
  Globe,
  Lightbulb,
  Building2,
  Bot,
  Users,
  Wand2,
  Play,
  ChevronRight,
  Sparkles,
  AlertCircle,
  Check
} from 'lucide-react';
import { useSessionStore } from '../../store/sessionStore';
import type { AgentType, AgentMetadata } from '../../types';
import { AGENT_CATALOG, getAgentsByCategory } from '../../types';
import { cn } from '../../lib/utils';
import { Button } from '../Common/Button';

// Icon mapping
const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  Presentation,
  BookOpen,
  Search,
  FileSearch,
  Globe,
  Lightbulb,
  Building2,
  Bot,
  Users,
  Wand2
};

// Category metadata
const CATEGORIES = {
  creative: { name: 'Creative', icon: Sparkles, color: 'text-orange-400' },
  development: { name: 'Development', icon: Code, color: 'text-green-400' },
  analysis: { name: 'Analysis', icon: Search, color: 'text-blue-400' },
  planning: { name: 'Planning', icon: Lightbulb, color: 'text-yellow-400' },
  utility: { name: 'Utility', icon: Bot, color: 'text-gray-400' }
};

// Get color classes for an agent
function getAgentColors(color: string) {
  const colors: Record<string, { bg: string; text: string; border: string; hover: string }> = {
    orange: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/50', hover: 'hover:border-orange-500' },
    purple: { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/50', hover: 'hover:border-purple-500' },
    green: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/50', hover: 'hover:border-green-500' },
    emerald: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/50', hover: 'hover:border-emerald-500' },
    teal: { bg: 'bg-teal-500/20', text: 'text-teal-400', border: 'border-teal-500/50', hover: 'hover:border-teal-500' },
    blue: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/50', hover: 'hover:border-blue-500' },
    indigo: { bg: 'bg-indigo-500/20', text: 'text-indigo-400', border: 'border-indigo-500/50', hover: 'hover:border-indigo-500' },
    cyan: { bg: 'bg-cyan-500/20', text: 'text-cyan-400', border: 'border-cyan-500/50', hover: 'hover:border-cyan-500' },
    yellow: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/50', hover: 'hover:border-yellow-500' },
    slate: { bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/50', hover: 'hover:border-slate-500' },
    gray: { bg: 'bg-gray-500/20', text: 'text-gray-400', border: 'border-gray-500/50', hover: 'hover:border-gray-500' },
    pink: { bg: 'bg-pink-500/20', text: 'text-pink-400', border: 'border-pink-500/50', hover: 'hover:border-pink-500' },
    violet: { bg: 'bg-violet-500/20', text: 'text-violet-400', border: 'border-violet-500/50', hover: 'hover:border-violet-500' }
  };
  return colors[color] || colors.gray;
}

interface AgentCardProps {
  agent: AgentMetadata;
  isSelected: boolean;
  onSelect: () => void;
}

function AgentCard({ agent, isSelected, onSelect }: AgentCardProps) {
  const Icon = ICONS[agent.icon] || Bot;
  const colors = getAgentColors(agent.color);

  return (
    <button
      onClick={onSelect}
      className={cn(
        'relative text-left p-4 rounded-xl border-2 transition-all',
        'bg-gray-800/50 hover:bg-gray-800',
        isSelected
          ? `${colors.border} ring-2 ring-offset-2 ring-offset-gray-900 ring-${agent.color}-500/50`
          : 'border-gray-700 hover:border-gray-600'
      )}
    >
      {/* Selected indicator */}
      {isSelected && (
        <div className={cn('absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center', colors.bg)}>
          <Check className={cn('w-3 h-3', colors.text)} />
        </div>
      )}

      {/* Icon */}
      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center mb-3', colors.bg)}>
        <Icon className={cn('w-5 h-5', colors.text)} />
      </div>

      {/* Title */}
      <h3 className="font-medium text-white mb-1">{agent.name}</h3>

      {/* Description */}
      <p className="text-sm text-gray-400 mb-3 line-clamp-2">{agent.description}</p>

      {/* Workflow type badge */}
      <div className="flex items-center gap-2">
        <span className={cn(
          'px-2 py-0.5 rounded text-xs font-medium',
          agent.workflowType === 'phase_heavy'
            ? 'bg-blue-500/20 text-blue-400'
            : 'bg-purple-500/20 text-purple-400'
        )}>
          {agent.workflowType === 'phase_heavy' ? 'Phase-Heavy' : 'Chat-Heavy'}
        </span>
        {agent.requiresApiKey && (
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400">
            API Key
          </span>
        )}
      </div>
    </button>
  );
}

export function CreateSessionLayout() {
  const { createSession, isLoading } = useSessionStore();
  const [selectedAgent, setSelectedAgent] = useState<AgentType | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const agentsByCategory = useMemo(() => getAgentsByCategory(), []);
  const selectedAgentMeta = useMemo(
    () => AGENT_CATALOG.find(a => a.type === selectedAgent),
    [selectedAgent]
  );

  const handleCreateSession = async () => {
    if (!selectedAgent) {
      setError('Please select an agent type');
      return;
    }

    setError(null);

    try {
      await createSession(selectedAgent);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
    }
  };

  const canCreate = selectedAgent && !isLoading;

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">ArchiFlow</h1>
              <p className="text-sm text-gray-400">AI-Powered Agent Workflows</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto px-6 py-8">
          {/* Page Title */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white mb-2">Create New Session</h2>
            <p className="text-gray-400">
              Select an agent type to get started. You can provide your task in the chat after starting the session.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left: Agent Selection */}
            <div className="lg:col-span-2 space-y-6">
              {/* Category Tabs */}
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setActiveCategory(null)}
                  className={cn(
                    'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    activeCategory === null
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
                  )}
                >
                  All Agents
                </button>
                {Object.entries(CATEGORIES).map(([key, { name, icon: Icon, color }]) => (
                  <button
                    key={key}
                    onClick={() => setActiveCategory(key)}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                      activeCategory === key
                        ? 'bg-gray-700 text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
                    )}
                  >
                    <Icon className={cn('w-4 h-4', color)} />
                    {name}
                  </button>
                ))}
              </div>

              {/* Agent Grid */}
              <div className="space-y-6">
                {Object.entries(agentsByCategory)
                  .filter(([category]) => activeCategory === null || category === activeCategory)
                  .map(([category, agents]) => (
                    <div key={category}>
                      {activeCategory === null && (
                        <div className="flex items-center gap-2 mb-3">
                          {(() => {
                            const { icon: Icon, color } = CATEGORIES[category as keyof typeof CATEGORIES];
                            return <Icon className={cn('w-4 h-4', color)} />;
                          })()}
                          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                            {CATEGORIES[category as keyof typeof CATEGORIES].name}
                          </h3>
                        </div>
                      )}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {agents.map(agent => (
                          <AgentCard
                            key={agent.type}
                            agent={agent}
                            isSelected={selectedAgent === agent.type}
                            onSelect={() => setSelectedAgent(agent.type)}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            {/* Right: Session Configuration */}
            <div className="lg:col-span-1">
              <div className="sticky top-8 space-y-6">
                {/* Selected Agent Info */}
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                    Session Configuration
                  </h3>

                  {selectedAgentMeta ? (
                    <div className="space-y-4">
                      {/* Agent summary */}
                      <div className="flex items-start gap-3 p-3 bg-gray-700/50 rounded-lg">
                        {(() => {
                          const Icon = ICONS[selectedAgentMeta.icon] || Bot;
                          const colors = getAgentColors(selectedAgentMeta.color);
                          return (
                            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', colors.bg)}>
                              <Icon className={cn('w-5 h-5', colors.text)} />
                            </div>
                          );
                        })()}
                        <div>
                          <h4 className="font-medium text-white">{selectedAgentMeta.name}</h4>
                          <p className="text-xs text-gray-400 mt-0.5">{selectedAgentMeta.description}</p>
                        </div>
                      </div>

                      {/* Features */}
                      <div>
                        <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">Features</h4>
                        <div className="flex flex-wrap gap-1.5">
                          {selectedAgentMeta.features.map((feature, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300"
                            >
                              {feature}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* API Key Warning */}
                      {selectedAgentMeta.requiresApiKey && (
                        <div className="flex items-start gap-2 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                          <AlertCircle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                          <div className="text-xs text-yellow-400">
                            <strong>Note:</strong> This agent requires the {selectedAgentMeta.requiresApiKey} environment variable to be set.
                          </div>
                        </div>
                      )}

                      {/* Error Message */}
                      {error && (
                        <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                          <div className="text-xs text-red-400">{error}</div>
                        </div>
                      )}

                      {/* Create Button */}
                      <Button
                        variant="primary"
                        size="lg"
                        className="w-full"
                        onClick={handleCreateSession}
                        disabled={!canCreate}
                        isLoading={isLoading}
                      >
                        <Play className="w-4 h-4 mr-2" />
                        Start Session
                        <ChevronRight className="w-4 h-4 ml-2" />
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <div className="w-16 h-16 rounded-full bg-gray-700 flex items-center justify-center mx-auto mb-4">
                        <Bot className="w-8 h-8 text-gray-500" />
                      </div>
                      <p className="text-gray-500 text-sm">
                        Select an agent from the list to configure your session
                      </p>
                    </div>
                  )}
                </div>

                {/* Quick Tips */}
                <div className="bg-gray-800/50 rounded-xl border border-gray-700/50 p-4">
                  <h4 className="text-xs font-medium text-gray-500 uppercase mb-3">Quick Tips</h4>
                  <ul className="space-y-2 text-xs text-gray-400">
                    <li className="flex items-start gap-2">
                      <ChevronRight className="w-3 h-3 mt-0.5 text-gray-600" />
                      <span><strong className="text-gray-300">Phase-Heavy</strong> agents work step-by-step with approvals</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <ChevronRight className="w-3 h-3 mt-0.5 text-gray-600" />
                      <span><strong className="text-gray-300">Chat-Heavy</strong> agents work continuously with monitoring</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <ChevronRight className="w-3 h-3 mt-0.5 text-gray-600" />
                      <span>Be specific in your prompts for better results</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="flex-shrink-0 border-t border-gray-800 py-4">
        <div className="max-w-6xl mx-auto px-6 text-center text-sm text-gray-600">
          ArchiFlow v0.1.0 - AI-Powered Agent Workflow Management
        </div>
      </footer>
    </div>
  );
}
