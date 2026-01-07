// ============================================================================
// Type Definitions for ArchiFlow Web App v3
// ============================================================================

// ----------------------------------------------------------------------------
// Core Types
// ----------------------------------------------------------------------------

// All agent types supported by the backend
export type AgentType =
  | 'coding'          // CodingAgent - Software development tasks
  | 'codingv2'        // CodingAgentV2 - Claude Code based
  | 'codingv3'        // CodingAgentV3 - Structured workflows
  | 'simple'          // SimpleAgent - General conversation
  | 'simplev2'        // SimpleAgent v2 - With profiles
  | 'analyzer'        // CodebaseAnalyzerAgent
  | 'reviewer'        // CodeReviewAgent
  | 'product'         // ProductManagerAgent
  | 'architect'       // TechLeadAgent
  | 'ppt'             // PPTAgent - Presentation creation
  | 'research'        // ResearchAgent
  | 'prompt_refiner'  // PromptRefinerAgent
  | 'comic';          // ComicAgent - Comic book creation

export type WorkflowType = 'phase_heavy' | 'chat_heavy';

export type UIBehavior = 'approval_required' | 'continuous_monitoring';

export type PhaseStatus = 'pending' | 'in_progress' | 'awaiting_approval' | 'approved' | 'completed' | 'failed';

export type MessageType = 'user' | 'agent' | 'system';

export type ArtifactType = 'markdown' | 'json' | 'image' | 'pdf' | 'folder' | 'code' | 'pptx';

// ----------------------------------------------------------------------------
// Agent Metadata (for UI display)
// ----------------------------------------------------------------------------

export interface AgentMetadata {
  type: AgentType;
  name: string;
  description: string;
  icon: string; // Lucide icon name
  color: string; // Tailwind color class
  category: 'creative' | 'development' | 'analysis' | 'planning' | 'utility';
  workflowType: WorkflowType;
  requiresProjectDir: boolean;
  requiresApiKey?: string; // e.g., 'GOOGLE_API_KEY'
  features: string[];
  placeholder?: string; // Input placeholder text
}

// Agent catalog for UI
export const AGENT_CATALOG: AgentMetadata[] = [
  // Creative Agents
  {
    type: 'comic',
    name: 'Comic Generator',
    description: 'Create professional comic books with AI-generated artwork',
    icon: 'BookOpen',
    color: 'orange',
    category: 'creative',
    workflowType: 'phase_heavy',
    requiresProjectDir: false,
    requiresApiKey: 'GOOGLE_API_KEY',
    features: ['Script Generation', 'Visual Specs', 'Character Design', 'Panel Generation', 'PDF Export'],
    placeholder: 'Describe your comic idea... (e.g., "A superhero cat saving the city")'
  },
  {
    type: 'ppt',
    name: 'Presentation Creator',
    description: 'Create stunning presentations with AI-generated slides and images',
    icon: 'Presentation',
    color: 'purple',
    category: 'creative',
    workflowType: 'phase_heavy',
    requiresProjectDir: true,
    requiresApiKey: 'GOOGLE_API_KEY',
    features: ['Outline Generation', 'Slide Descriptions', 'Image Generation', 'PPTX/PDF Export'],
    placeholder: 'What is your presentation about? (e.g., "AI in healthcare")'
  },

  // Analysis Agents
  {
    type: 'reviewer',
    name: 'Code Reviewer',
    description: 'Get thorough code reviews with actionable feedback',
    icon: 'FileSearch',
    color: 'indigo',
    category: 'analysis',
    workflowType: 'chat_heavy',
    requiresProjectDir: true,
    features: ['Security Review', 'Performance Analysis', 'Best Practices', 'Suggestions'],
    placeholder: 'Paste a diff or describe what to review...'
  },
  {
    type: 'research',
    name: 'Research Agent',
    description: 'Comprehensive research and reporting on any topic',
    icon: 'Globe',
    color: 'cyan',
    category: 'analysis',
    workflowType: 'chat_heavy',
    requiresProjectDir: false,
    features: ['Web Search', 'Content Analysis', 'Report Generation', 'Citations'],
    placeholder: 'What would you like to research?'
  },

  // Planning Agents
  {
    type: 'product',
    name: 'Product Manager',
    description: 'Brainstorm features and create product requirements',
    icon: 'Lightbulb',
    color: 'yellow',
    category: 'planning',
    workflowType: 'phase_heavy',
    requiresProjectDir: true,
    features: ['Discovery', 'Exploration', 'Prioritization', 'PRD Generation', 'User Stories'],
    placeholder: 'Describe your product idea or feature...'
  },
  {
    type: 'architect',
    name: 'Tech Architect',
    description: 'Design system architecture and technical specifications',
    icon: 'Building2',
    color: 'slate',
    category: 'planning',
    workflowType: 'phase_heavy',
    requiresProjectDir: true,
    features: ['Architecture Design', 'RFC Generation', 'ADR Writing', 'Phase Planning'],
    placeholder: 'Describe the system you want to architect...'
  },

  // Utility Agents
  {
    type: 'simple',
    name: 'General Assistant',
    description: 'General-purpose AI assistant for various tasks',
    icon: 'Bot',
    color: 'gray',
    category: 'utility',
    workflowType: 'chat_heavy',
    requiresProjectDir: false,
    features: ['File Operations', 'Web Access', 'Code Execution', 'General Q&A'],
    placeholder: 'How can I help you today?'
  },
  {
    type: 'simplev2',
    name: 'Specialized Assistant',
    description: 'Customizable assistant with role-based profiles',
    icon: 'Users',
    color: 'pink',
    category: 'utility',
    workflowType: 'chat_heavy',
    requiresProjectDir: false,
    features: ['Multiple Profiles', 'Custom Roles', 'Adaptive Behavior'],
    placeholder: 'What task can I help with?'
  },
  {
    type: 'prompt_refiner',
    name: 'Prompt Refiner',
    description: 'Analyze and improve your prompts for better results',
    icon: 'Wand2',
    color: 'violet',
    category: 'utility',
    workflowType: 'chat_heavy',
    requiresProjectDir: false,
    features: ['Quality Scoring', 'Refinement Suggestions', 'CRAFT Framework', 'Clipboard Copy'],
    placeholder: 'Paste a prompt to analyze and refine...'
  }
];

// Helper function to get agent metadata
export function getAgentMetadata(type: AgentType): AgentMetadata | undefined {
  return AGENT_CATALOG.find(a => a.type === type);
}

// Group agents by category
export function getAgentsByCategory(): Record<string, AgentMetadata[]> {
  return AGENT_CATALOG.reduce((acc, agent) => {
    if (!acc[agent.category]) {
      acc[agent.category] = [];
    }
    acc[agent.category].push(agent);
    return acc;
  }, {} as Record<string, AgentMetadata[]>);
}

// ----------------------------------------------------------------------------
// Workflow Types
// ----------------------------------------------------------------------------

export interface WorkflowPhase {
  phase_id: string;
  name: string;
  description: string;
  order: number;
  status: PhaseStatus;
  input_artifacts: string[];
  output_artifacts: string[];
  requires_approval: boolean;
  approval_prompt?: string;
  detection_pattern?: string;
  ui_behavior: UIBehavior;
  progress_source?: string; // e.g., 'todo_list.json' for continuous phases
}

export interface Workflow {
  agent_type: AgentType;
  workflow_type: WorkflowType;
  current_phase: string;
  phases: WorkflowPhase[];
  total_phases: number;
  approval_phases: string[];
  continuous_phases: string[];
  progress?: number; // 0-100 for continuous phases
}

// ----------------------------------------------------------------------------
// Artifact Types
// ----------------------------------------------------------------------------

export interface Artifact {
  id: string;
  name: string;
  type: ArtifactType;
  path: string;
  size?: number;
  content?: string;
  url?: string; // For images
  preview?: string; // Text preview
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ArtifactFolder {
  name: string;
  path: string;
  artifacts: Artifact[];
  folders: ArtifactFolder[];
}

// ----------------------------------------------------------------------------
// Chat Types
// ----------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  type: MessageType;
  content: string;
  timestamp: string;
  phase?: string;
  tool_calls?: ToolCall[];
  metadata?: Record<string, unknown>;
}

export interface ToolCall {
  name: string;
  parameters: Record<string, unknown>;
  result?: string;
  error?: string;
}

// ----------------------------------------------------------------------------
// Session Types
// ----------------------------------------------------------------------------

export interface Session {
  session_id: string;
  agent_type: AgentType;
  user_prompt: string | null;  // Can be null if no initial prompt provided
  project_directory?: string;
  status: 'running' | 'paused' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  workflow?: Workflow;
  artifacts?: Artifact[];
  messages?: ChatMessage[];
}

// Session creation request
export interface CreateSessionRequest {
  agent_type: AgentType;
  user_prompt?: string;  // Optional - can send first message via chat
  project_directory?: string;
  options?: Record<string, unknown>;
}

// ----------------------------------------------------------------------------
// UI State Types
// ----------------------------------------------------------------------------

export interface ApprovalDialogState {
  isOpen: boolean;
  phaseId: string | null;
  phaseName: string;
  artifacts: Artifact[];
  approvalPrompt: string;
}

export interface SelectedArtifactState {
  artifact: Artifact | null;
  isEditing: boolean;
}

export interface WorkflowPanelState {
  expandedPhases: Set<string>;
}

// ----------------------------------------------------------------------------
// Comment Types
// ----------------------------------------------------------------------------

/**
 * Status of a comment.
 */
export type CommentStatus = 'pending' | 'resolved' | 'applied' | 'submitted';

/**
 * A comment on a document.
 */
export interface Comment {
  id: string;
  session_id: string;
  file_path: string;
  line_number: number;
  end_line_number?: number;  // Phase 3: Support for multi-line/range comments
  selected_text: string;
  comment_text: string;
  author: string;
  status: CommentStatus;
  created_at: string;
  updated_at: string;
}

/**
 * Request data for creating a comment.
 */
export interface CommentCreate {
  file_path: string;
  line_number: number;
  end_line_number?: number;  // Phase 3: Support for multi-line/range comments
  selected_text?: string;
  comment_text: string;
  author?: string;
}

/**
 * Request data for updating a comment.
 */
export interface CommentUpdate {
  comment_text?: string;
  status?: CommentStatus;
}

/**
 * Response from listing comments.
 */
export interface CommentListResponse {
  comments: Comment[];
  total_count: number;
  file_path?: string;
}

// ----------------------------------------------------------------------------
// API/WebSocket Event Types
// ----------------------------------------------------------------------------

export interface WebSocketEvent {
  type: string;
  data: unknown;
}

export interface WorkflowUpdateEvent extends WebSocketEvent {
  type: 'workflow.update';
  data: {
    phase_id: string;
    status: PhaseStatus;
    progress?: number;
  };
}

export interface ArtifactUpdateEvent extends WebSocketEvent {
  type: 'artifact.update';
  data: {
    artifact: Artifact;
    action: 'created' | 'updated' | 'deleted';
  };
}

export interface MessageEvent extends WebSocketEvent {
  type: 'message.new';
  data: {
    message: ChatMessage;
  };
}

export interface ApprovalRequestedEvent extends WebSocketEvent {
  type: 'approval.requested';
  data: {
    phase_id: string;
    phase_name: string;
    artifacts: Artifact[];
    approval_prompt: string;
  };
}

export interface SessionCreatedEvent extends WebSocketEvent {
  type: 'session.created';
  data: {
    session: Session;
  };
}

export interface SessionErrorEvent extends WebSocketEvent {
  type: 'session.error';
  data: {
    error: string;
    details?: string;
  };
}
