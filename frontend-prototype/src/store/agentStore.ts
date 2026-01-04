import { create } from 'zustand';
import { agentApi, type AgentInfo, type AgentCategory } from '../services';
import type { AgentMetadata, AgentType } from '../types';

// ============================================================================
// Helper: Convert API response to frontend AgentMetadata type
// ============================================================================

function mapAgentInfo(info: AgentInfo): AgentMetadata {
  return {
    type: info.id as AgentType,
    name: info.name,
    description: info.description,
    icon: info.icon,
    color: info.color,
    category: info.category as AgentMetadata['category'],
    workflowType: info.workflow_type,
    requiresProjectDir: info.supports_artifacts, // Approximate mapping
    features: info.capabilities.map((c) => c.name),
    placeholder: info.example_prompts[0] ?? `Enter your ${info.name} prompt...`,
  };
}

// ============================================================================
// Store Interface
// ============================================================================

interface AgentState {
  agents: AgentMetadata[];
  categories: AgentCategory[];
  isLoading: boolean;
  error: string | null;
  isLoaded: boolean;

  // Actions
  loadAgents: () => Promise<void>;
  getByType: (type: AgentType) => AgentMetadata | undefined;
  getByCategory: (category: string) => AgentMetadata[];
  searchAgents: (query: string) => Promise<void>;
  clearError: () => void;
}

// ============================================================================
// Store Implementation
// ============================================================================

export const useAgentStore = create<AgentState>((set, get) => ({
  agents: [],
  categories: [],
  isLoading: false,
  error: null,
  isLoaded: false,

  loadAgents: async () => {
    // Skip if already loaded
    if (get().isLoaded) return;

    set({ isLoading: true, error: null });

    try {
      const response = await agentApi.list();
      const agents = response.agents.map(mapAgentInfo);
      set({
        agents,
        categories: response.categories,
        isLoading: false,
        isLoaded: true,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load agents',
        isLoading: false,
      });
    }
  },

  getByType: (type) => {
    return get().agents.find((a) => a.type === type);
  },

  getByCategory: (category) => {
    const { agents } = get();
    return category === 'all'
      ? agents
      : agents.filter((a) => a.category === category);
  },

  searchAgents: async (query) => {
    set({ isLoading: true, error: null });

    try {
      const response = await agentApi.list({ search: query });
      const agents = response.agents.map(mapAgentInfo);
      set({ agents, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to search agents',
        isLoading: false,
      });
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));
