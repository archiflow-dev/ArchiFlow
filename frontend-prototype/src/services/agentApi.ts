/**
 * Agent API client.
 *
 * Handles agent metadata and discovery.
 */

import { api } from './api';

// ============================================================================
// Types
// ============================================================================

export interface AgentCapability {
  name: string;
  description: string;
}

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  color: string;
  workflow_type: 'phase_heavy' | 'chat_heavy';
  capabilities: AgentCapability[];
  supports_streaming: boolean;
  supports_artifacts: boolean;
  supports_workflow: boolean;
  example_prompts: string[];
  tags: string[];
}

export interface AgentCategory {
  id: string;
  name: string;
  description?: string;
  count: number;
}

export interface AgentListResponse {
  agents: AgentInfo[];
  total: number;
  categories: AgentCategory[];
}

export interface AgentListParams {
  category?: string;
  search?: string;
}

export interface WorkflowPhaseDefinition {
  id: string;
  name: string;
  description?: string;
  order: number;
  requires_approval: boolean;
  artifacts: string[];
}

export interface WorkflowDefinition {
  agent_type: string;
  workflow_type: string;
  phases: WorkflowPhaseDefinition[];
  total_phases: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all available agents.
 */
export async function listAgents(params: AgentListParams = {}): Promise<AgentListResponse> {
  return api.get<AgentListResponse>('/agents/', { params });
}

/**
 * Get a specific agent by type.
 */
export async function getAgent(agentType: string): Promise<AgentInfo> {
  return api.get<AgentInfo>(`/agents/${agentType}`);
}

/**
 * Get the workflow definition for an agent.
 */
export async function getAgentWorkflow(agentType: string): Promise<WorkflowDefinition> {
  return api.get<WorkflowDefinition>(`/agents/${agentType}/workflow`);
}

/**
 * List all agent categories.
 */
export async function listCategories(): Promise<{ categories: AgentCategory[] }> {
  return api.get<{ categories: AgentCategory[] }>('/agents/categories');
}

// ============================================================================
// Namespace export
// ============================================================================

export const agentApi = {
  list: listAgents,
  get: getAgent,
  getWorkflow: getAgentWorkflow,
  listCategories,
};
