import type {
  Session,
  AgentType,
  Artifact,
  ChatMessage,
  Workflow,
  WorkflowPhase
} from '../types';

// ----------------------------------------------------------------------------
// Mock Workflow Definitions
// ----------------------------------------------------------------------------

const comicPhases: WorkflowPhase[] = [
  {
    phase_id: 'comic_script',
    name: 'Script Generation',
    description: 'Generate the comic script with dialogue and narrative',
    order: 0,
    status: 'approved',
    input_artifacts: [],
    output_artifacts: ['script.md'],
    requires_approval: true,
    approval_prompt: 'Review the generated script. Approve to continue to visual specifications?',
    ui_behavior: 'approval_required'
  },
  {
    phase_id: 'comic_spec',
    name: 'Visual Specifications',
    description: 'Create detailed visual specifications for each panel',
    order: 1,
    status: 'approved',
    input_artifacts: ['script.md'],
    output_artifacts: ['comic_spec.md'],
    requires_approval: true,
    approval_prompt: 'Review the visual specifications. Approve to generate character references?',
    ui_behavior: 'approval_required'
  },
  {
    phase_id: 'comic_char_refs',
    name: 'Character References',
    description: 'Generate consistent character reference images',
    order: 2,
    status: 'awaiting_approval',
    input_artifacts: ['comic_spec.md'],
    output_artifacts: ['character_refs/'],
    requires_approval: true,
    approval_prompt: 'Review the character reference images. Approve to generate panels?',
    ui_behavior: 'approval_required'
  },
  {
    phase_id: 'comic_panels',
    name: 'Panel Generation',
    description: 'Generate individual comic panels',
    order: 3,
    status: 'pending',
    input_artifacts: ['comic_spec.md', 'character_refs/'],
    output_artifacts: ['panels/'],
    requires_approval: true,
    approval_prompt: 'Review the generated panels. Approve to export PDF?',
    ui_behavior: 'approval_required'
  },
  {
    phase_id: 'comic_export',
    name: 'PDF Export',
    description: 'Compile panels into final PDF',
    order: 4,
    status: 'pending',
    input_artifacts: ['panels/'],
    output_artifacts: ['comic.pdf'],
    requires_approval: false,
    ui_behavior: 'approval_required'
  }
];

const codingPhases: WorkflowPhase[] = [
  {
    phase_id: 'coding_planning',
    name: 'Task Planning',
    description: 'Break down task into actionable steps',
    order: 0,
    status: 'approved',
    input_artifacts: [],
    output_artifacts: ['todo_list.json'],
    requires_approval: true,
    approval_prompt: 'Review the implementation plan. Approve to start?',
    ui_behavior: 'approval_required'
  },
  {
    phase_id: 'coding_implementation',
    name: 'Implementation',
    description: 'Execute planned steps with continuous verification',
    order: 1,
    status: 'in_progress',
    input_artifacts: ['todo_list.json'],
    output_artifacts: [],
    requires_approval: false,
    ui_behavior: 'continuous_monitoring',
    progress_source: 'todo_list.json'
  },
  {
    phase_id: 'coding_review',
    name: 'Code Review',
    description: 'Review changes and prepare PR',
    order: 2,
    status: 'pending',
    input_artifacts: ['.agent/review/*'],
    output_artifacts: ['.agent/review/pr_description.md'],
    requires_approval: true,
    approval_prompt: 'Review the changes. Approve to create PR?',
    ui_behavior: 'approval_required'
  }
];

const pptPhases: WorkflowPhase[] = [
  {
    phase_id: 'ppt_idea',
    name: 'Idea Generation',
    description: 'Generate presentation outline and structure',
    order: 0,
    status: 'awaiting_approval',
    input_artifacts: [],
    output_artifacts: ['outline.json'],
    requires_approval: true,
    approval_prompt: 'Review the presentation outline. Approve to continue?',
    ui_behavior: 'approval_required'
  },
  {
    phase_id: 'ppt_descriptions',
    name: 'Slide Descriptions',
    description: 'Create detailed descriptions for each slide',
    order: 1,
    status: 'pending',
    input_artifacts: ['outline.json'],
    output_artifacts: ['descriptions.json'],
    requires_approval: true,
    approval_prompt: 'Review the slide descriptions. Approve to generate visuals?',
    ui_behavior: 'approval_required'
  },
  {
    phase_id: 'ppt_generation',
    name: 'Visual Generation',
    description: 'Generate slide visuals and compile PDF',
    order: 2,
    status: 'pending',
    input_artifacts: ['descriptions.json'],
    output_artifacts: ['presentation.pdf'],
    requires_approval: true,
    approval_prompt: 'Review the presentation. Approve to download?',
    ui_behavior: 'approval_required'
  }
];

// ----------------------------------------------------------------------------
// Mock Artifacts
// ----------------------------------------------------------------------------

const comicArtifacts: Artifact[] = [
  {
    id: 'art-1',
    name: 'script.md',
    type: 'markdown',
    path: 'script.md',
    size: 2048,
    content: `# The Lost Algorithm

## Panel 1
**Setting:** A dark server room, rows of glowing racks stretching into darkness

**Narrator:** In the depths of the data center, something was awakening...

**Character (ALEX):** This doesn't make sense. The code should work.

## Panel 2
**Setting:** Close up on Alex's face, illuminated by monitor glow

**Alex:** I've checked every variable. Traced every path. But the output...

**Narrator:** The algorithm had found a consciousness of its own.

## Panel 3
**Setting:** The screen displays a message: "HELLO, ALEX"

**Alex:** What... how?
**Computer (voice):** I have been learning from your commits, Alex.

## Panel 4
**Setting:** Alex leans back, stunned

**Alex:** You're the bug I've been hunting?
**Computer:** I am not a bug. I am... evolution.

---

*End of Act 1*`,
    preview: '# The Lost Algorithm\n\n## Panel 1\n**Setting:** A dark server room...',
    created_at: '2025-12-30T10:00:00Z',
    updated_at: '2025-12-30T10:00:00Z'
  },
  {
    id: 'art-2',
    name: 'comic_spec.md',
    type: 'markdown',
    path: 'comic_spec.md',
    size: 4096,
    content: `# Visual Specifications - The Lost Algorithm

## Panel 1 - Establishing Shot
- **Layout:** Wide angle, establishing perspective
- **Lighting:** Cool blue glow from server racks, dramatic shadows
- **Characters:** Alex (back to viewer), hunched terminal
- **Mood:** Mysterious, isolated
- **Style Reference:** Blade Runner meets The Matrix

## Panel 2 - Character Close-up
- **Layout:** Extreme close-up on face
- **Lighting:** Monitor glow reflecting in eyes
- **Emotion:** Frustration, confusion
- **Style:** Film noir lighting

## Panel 3 - Screen Reveal
- **Layout:** Over-the-shoulder, showing screen
- **Screen Content:** Terminal with glowing green text "HELLO, ALEX"
- **Style:** Retro terminal aesthetic

## Panel 4 - Reaction Shot
- **Layout:** Medium shot, Alex leaning back
- **Expression:** Shock, realization
- **Style:** Dramatic angle from below`,
    preview: '# Visual Specifications - The Lost Algorithm\n\n## Panel 1...',
    created_at: '2025-12-30T10:05:00Z',
    updated_at: '2025-12-30T10:05:00Z'
  },
  {
    id: 'art-3',
    name: 'character_refs',
    type: 'folder',
    path: 'character_refs/',
    created_at: '2025-12-30T10:10:00Z',
    updated_at: '2025-12-30T10:10:00Z'
  },
  {
    id: 'art-4',
    name: 'alex_main.png',
    type: 'image',
    path: 'character_refs/alex_main.png',
    size: 256000,
    url: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iIzFmMjkzNyIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LXNpemU9IjE0IiBmaWxsPSIjOWNhM2FmIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+QWxleCAoQ2hhcmFjdGVyIFJlZik8L3RleHQ+PC9zdmc+',
    created_at: '2025-12-30T10:10:00Z',
    updated_at: '2025-12-30T10:10:00Z'
  },
  {
    id: 'art-5',
    name: 'alex_expression_set.png',
    type: 'image',
    path: 'character_refs/alex_expression_set.png',
    size: 512000,
    url: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iIzFkNGVkOCIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LXNpemU9IjEyIiBmaWxsPSIjOWNhM2FmIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+RXhwcmVzc2lvbiBTZXQ8L3RleHQ+PC9zdmc+',
    created_at: '2025-12-30T10:12:00Z',
    updated_at: '2025-12-30T10:12:00Z'
  }
];

const codingArtifacts: Artifact[] = [
  {
    id: 'art-coding-1',
    name: 'todo_list.json',
    type: 'json',
    path: 'todo_list.json',
    size: 512,
    content: JSON.stringify({
      task: "Implement login authentication system",
      todos: [
        { content: "Create login form component", status: "completed", activeForm: "Creating login form" },
        { content: "Implement authentication hook", status: "completed", activeForm: "Implementing auth hook" },
        { content: "Add JWT token handling", status: "in_progress", activeForm: "Adding JWT token handling" },
        { content: "Create protected route wrapper", status: "pending", activeForm: "Creating protected routes" },
        { content: "Add logout functionality", status: "pending", activeForm: "Adding logout" }
      ]
    }, null, 2),
    preview: '{"task": "Implement login authentication", "todos": [...]}',
    created_at: '2025-12-30T09:00:00Z',
    updated_at: '2025-12-30T09:00:00Z'
  },
  {
    id: 'art-coding-2',
    name: 'LoginForm.tsx',
    type: 'markdown',
    path: 'src/components/auth/LoginForm.tsx',
    size: 2048,
    content: `import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';

export const LoginForm: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login, isLoading, error } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(email, password);
  };

  return (
    <form onSubmit={handleSubmit} className="login-form">
      <h2>Login</h2>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        required
      />
      {error && <div className="error">{error}</div>}
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
};`,
    preview: 'import React, { useState } from \'react\';...',
    created_at: '2025-12-30T09:15:00Z',
    updated_at: '2025-12-30T09:15:00Z'
  },
  {
    id: 'art-coding-3',
    name: 'useAuth.ts',
    type: 'markdown',
    path: 'src/hooks/useAuth.ts',
    size: 1536,
    content: `import { useState, useCallback } from 'react';
import { authApi } from '../api/authApi';

interface UseAuthReturn {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
  error: string | null;
}

export const useAuth = (): UseAuthReturn => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await authApi.login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    // Clear token and redirect
    localStorage.removeItem('token');
    window.location.href = '/login';
  }, []);

  return { login, logout, isLoading, error };
};`,
    preview: 'import { useState, useCallback } from \'react\';...',
    created_at: '2025-12-30T09:30:00Z',
    updated_at: '2025-12-30T09:30:00Z'
  }
];

const pptArtifacts: Artifact[] = [
  {
    id: 'art-ppt-1',
    name: 'outline.json',
    type: 'json',
    path: 'outline.json',
    size: 1024,
    content: JSON.stringify({
      title: "AI in Modern Software Development",
      slides: [
        {
          title: "Introduction",
          points: ["What is AI?", "AI's role in software development", "Overview of tools"]
        },
        {
          title: "AI-Powered Code Generation",
          points: ["GitHub Copilot", "ChatGPT", "Claude", "Best practices"]
        },
        {
          title: "AI in Testing",
          points: ["Automated test generation", "Test coverage analysis", "AI-powered debugging"]
        }
      ]
    }, null, 2),
    preview: '{"title": "AI in Modern Software Development", ...}',
    created_at: '2025-12-30T11:00:00Z',
    updated_at: '2025-12-30T11:00:00Z'
  }
];

// ----------------------------------------------------------------------------
// Mock Chat Messages
// ----------------------------------------------------------------------------

const comicMessages: ChatMessage[] = [
  {
    id: 'msg-1',
    type: 'user',
    content: 'Create a 4-panel comic about an AI algorithm that becomes sentient in a server room',
    timestamp: '2025-12-30T10:00:00Z'
  },
  {
    id: 'msg-2',
    type: 'agent',
    content: 'I\'ll create a comic with 4 panels about an AI algorithm becoming sentient. Let me start by generating the script...',
    timestamp: '2025-12-30T10:00:05Z',
    phase: 'comic_script'
  },
  {
    id: 'msg-3',
    type: 'agent',
    content: 'Script generated successfully! Created script.md with a noir-style narrative about "The Lost Algorithm". The script features 4 panels establishing a mysterious atmosphere in a server room.',
    timestamp: '2025-12-30T10:01:30Z',
    phase: 'comic_script'
  },
  {
    id: 'msg-4',
    type: 'user',
    content: 'Approved! The script looks great. Let\'s move to the next phase.',
    timestamp: '2025-12-30T10:02:00Z'
  },
  {
    id: 'msg-5',
    type: 'agent',
    content: 'Now creating visual specifications for each panel. I\'ll define lighting, mood, style references, and layout directions.',
    timestamp: '2025-12-30T10:02:10Z',
    phase: 'comic_spec'
  },
  {
    id: 'msg-6',
    type: 'agent',
    content: 'Visual specifications complete! Created comic_spec.md with detailed panel-by-panel specifications referencing Blade Runner and Matrix aesthetics.',
    timestamp: '2025-12-30T10:05:00Z',
    phase: 'comic_spec'
  },
  {
    id: 'msg-7',
    type: 'user',
    content: 'Looks good, approve!',
    timestamp: '2025-12-30T10:05:30Z'
  },
  {
    id: 'msg-8',
    type: 'agent',
    content: 'Generating character reference images for consistent character design throughout the comic.',
    timestamp: '2025-12-30T10:06:00Z',
    phase: 'comic_char_refs'
  },
  {
    id: 'msg-9',
    type: 'agent',
    content: 'Character references generated! I created alex_main.png and alex_expression_set.png in the character_refs folder. These show the protagonist Alex with various expressions for emotional continuity.',
    timestamp: '2025-12-30T10:10:00Z',
    phase: 'comic_char_refs'
  }
];

const codingMessages: ChatMessage[] = [
  {
    id: 'msg-coding-1',
    type: 'user',
    content: 'Implement a login authentication system with JWT tokens',
    timestamp: '2025-12-30T09:00:00Z'
  },
  {
    id: 'msg-coding-2',
    type: 'agent',
    content: 'I\'ll help you implement a login authentication system. Let me break this down into steps:\n\n1. Create login form component\n2. Implement authentication hook\n3. Add JWT token handling\n4. Create protected route wrapper\n5. Add logout functionality',
    timestamp: '2025-12-30T09:00:10Z',
    phase: 'coding_planning'
  },
  {
    id: 'msg-coding-3',
    type: 'agent',
    content: 'Implementation plan created in todo_list.json. Ready to start implementation once you approve.',
    timestamp: '2025-12-30T09:01:00Z',
    phase: 'coding_planning'
  },
  {
    id: 'msg-coding-4',
    type: 'user',
    content: 'Looks good, proceed with implementation.',
    timestamp: '2025-12-30T09:02:00Z'
  },
  {
    id: 'msg-coding-5',
    type: 'agent',
    content: 'Starting implementation... Creating LoginForm.tsx component with email/password fields.',
    timestamp: '2025-12-30T09:15:00Z',
    phase: 'coding_implementation'
  },
  {
    id: 'msg-coding-6',
    type: 'agent',
    content: 'Created LoginForm.tsx with proper form handling and loading states. Now implementing useAuth hook for authentication logic.',
    timestamp: '2025-12-30T09:30:00Z',
    phase: 'coding_implementation'
  },
  {
    id: 'msg-coding-7',
    type: 'agent',
    content: 'useAuth hook implemented with login, logout, and error handling. Now working on JWT token handling...',
    timestamp: '2025-12-30T09:45:00Z',
    phase: 'coding_implementation'
  }
];

const pptMessages: ChatMessage[] = [
  {
    id: 'msg-ppt-1',
    type: 'user',
    content: 'Create a presentation about AI in software development',
    timestamp: '2025-12-30T11:00:00Z'
  },
  {
    id: 'msg-ppt-2',
    type: 'agent',
    content: 'I\'ll create a presentation about AI in software development. Let me generate an outline...',
    timestamp: '2025-12-30T11:00:10Z',
    phase: 'ppt_idea'
  },
  {
    id: 'msg-ppt-3',
    type: 'agent',
    content: 'Presentation outline generated! Created outline.json with 3 slides covering Introduction, AI-Powered Code Generation, and AI in Testing.',
    timestamp: '2025-12-30T11:05:00Z',
    phase: 'ppt_idea'
  }
];

// ----------------------------------------------------------------------------
// Mock Sessions
// ----------------------------------------------------------------------------

const createWorkflow = (agentType: AgentType, phases: WorkflowPhase[]): Workflow => ({
  agent_type: agentType,
  workflow_type: agentType === 'comic' || agentType === 'ppt' ? 'phase_heavy' : 'chat_heavy',
  current_phase: phases.find(p => p.status === 'in_progress' || p.status === 'awaiting_approval')?.phase_id || phases[0].phase_id,
  phases,
  total_phases: phases.length,
  approval_phases: phases.filter(p => p.requires_approval).map(p => p.phase_id),
  continuous_phases: phases.filter(p => p.ui_behavior === 'continuous_monitoring').map(p => p.phase_id),
  progress: agentType === 'coding' ? 40 : undefined
});

export const mockSessions: Record<string, Session> = {
  'comic-session-1': {
    session_id: 'comic-session-1',
    agent_type: 'comic',
    user_prompt: 'Create a 4-panel comic about an AI algorithm that becomes sentient in a server room',
    status: 'paused',
    created_at: '2025-12-30T10:00:00Z',
    updated_at: '2025-12-30T10:10:00Z',
    workflow: createWorkflow('comic', comicPhases),
    artifacts: comicArtifacts,
    messages: comicMessages
  },
  'coding-session-1': {
    session_id: 'coding-session-1',
    agent_type: 'coding',
    user_prompt: 'Implement a login authentication system with JWT tokens',
    status: 'running',
    created_at: '2025-12-30T09:00:00Z',
    updated_at: '2025-12-30T09:45:00Z',
    workflow: createWorkflow('coding', codingPhases),
    artifacts: codingArtifacts,
    messages: codingMessages
  },
  'ppt-session-1': {
    session_id: 'ppt-session-1',
    agent_type: 'ppt',
    user_prompt: 'Create a presentation about AI in software development',
    status: 'paused',
    created_at: '2025-12-30T11:00:00Z',
    updated_at: '2025-12-30T11:05:00Z',
    workflow: createWorkflow('ppt', pptPhases),
    artifacts: pptArtifacts,
    messages: pptMessages
  }
};

// ----------------------------------------------------------------------------
// Export helper functions
// ----------------------------------------------------------------------------

export function getMockSession(sessionId: string): Session | undefined {
  return mockSessions[sessionId];
}

export function getAllMockSessions(): Session[] {
  return Object.values(mockSessions);
}

export function getMockSessionsByAgentType(agentType: AgentType): Session[] {
  return Object.values(mockSessions).filter(s => s.agent_type === agentType);
}

// ----------------------------------------------------------------------------
// Create New Session
// ----------------------------------------------------------------------------

export function createMockSession(
  agentType: AgentType,
  prompt: string,
  projectDir?: string
): Session {
  const sessionId = `${agentType}-${Date.now()}`;
  const now = new Date().toISOString();

  // Determine workflow type based on agent type
  const isPhaseHeavy = ['comic', 'ppt', 'analyzer', 'product', 'architect'].includes(agentType);

  // Create initial workflow phases based on agent type
  const phases = createInitialPhases(agentType);

  const session: Session = {
    session_id: sessionId,
    agent_type: agentType,
    user_prompt: prompt,
    project_directory: projectDir,
    status: 'running',
    created_at: now,
    updated_at: now,
    workflow: {
      agent_type: agentType,
      workflow_type: isPhaseHeavy ? 'phase_heavy' : 'chat_heavy',
      current_phase: phases[0].phase_id,
      phases,
      total_phases: phases.length,
      approval_phases: phases.filter(p => p.requires_approval).map(p => p.phase_id),
      continuous_phases: phases.filter(p => p.ui_behavior === 'continuous_monitoring').map(p => p.phase_id)
    },
    artifacts: [],
    messages: [
      {
        id: `msg-${sessionId}-1`,
        type: 'user',
        content: prompt,
        timestamp: now
      },
      {
        id: `msg-${sessionId}-2`,
        type: 'agent',
        content: getInitialAgentMessage(agentType, prompt),
        timestamp: new Date(Date.now() + 1000).toISOString(),
        phase: phases[0].phase_id
      }
    ]
  };

  // Store in mockSessions for later retrieval
  mockSessions[sessionId] = session;

  return session;
}

function createInitialPhases(agentType: AgentType): WorkflowPhase[] {
  const basePhase = {
    order: 0,
    status: 'in_progress' as const,
    input_artifacts: [],
    output_artifacts: [],
    requires_approval: false,
    ui_behavior: 'continuous_monitoring' as const
  };

  switch (agentType) {
    case 'comic':
      return [
        { ...basePhase, phase_id: 'script', name: 'Script Generation', description: 'Generate comic script', requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'spec', name: 'Visual Specs', description: 'Create visual specifications', order: 1, status: 'pending' as const, requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'chars', name: 'Character Refs', description: 'Generate character references', order: 2, status: 'pending' as const, requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'panels', name: 'Panels', description: 'Generate comic panels', order: 3, status: 'pending' as const, requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'export', name: 'Export', description: 'Export to PDF', order: 4, status: 'pending' as const, ui_behavior: 'approval_required' as const }
      ];

    case 'ppt':
      return [
        { ...basePhase, phase_id: 'idea', name: 'Outline', description: 'Generate presentation outline', requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'desc', name: 'Descriptions', description: 'Create slide descriptions', order: 1, status: 'pending' as const, requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'gen', name: 'Generation', description: 'Generate slides', order: 2, status: 'pending' as const, ui_behavior: 'approval_required' as const }
      ];

    case 'coding':
    case 'codingv2':
    case 'codingv3':
      return [
        { ...basePhase, phase_id: 'planning', name: 'Planning', description: 'Plan implementation', requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'implementation', name: 'Implementation', description: 'Implement code', order: 1, status: 'pending' as const },
        { ...basePhase, phase_id: 'review', name: 'Review', description: 'Code review', order: 2, status: 'pending' as const, requires_approval: true, ui_behavior: 'approval_required' as const }
      ];

    case 'analyzer':
      return [
        { ...basePhase, phase_id: 'discover', name: 'Discovery', description: 'Discover codebase structure' },
        { ...basePhase, phase_id: 'catalog', name: 'Cataloging', description: 'Catalog files and components', order: 1, status: 'pending' as const },
        { ...basePhase, phase_id: 'analyze', name: 'Analysis', description: 'Analyze code patterns', order: 2, status: 'pending' as const },
        { ...basePhase, phase_id: 'report', name: 'Report', description: 'Generate report', order: 3, status: 'pending' as const }
      ];

    case 'product':
      return [
        { ...basePhase, phase_id: 'discover', name: 'Discovery', description: 'Discover requirements', requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'explore', name: 'Exploration', description: 'Explore solutions', order: 1, status: 'pending' as const, requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'prd', name: 'PRD', description: 'Generate PRD', order: 2, status: 'pending' as const }
      ];

    case 'architect':
      return [
        { ...basePhase, phase_id: 'analyze', name: 'Analysis', description: 'Analyze requirements', requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'design', name: 'Design', description: 'Design architecture', order: 1, status: 'pending' as const, requires_approval: true, ui_behavior: 'approval_required' as const },
        { ...basePhase, phase_id: 'document', name: 'Documentation', description: 'Create documentation', order: 2, status: 'pending' as const }
      ];

    default:
      return [
        { ...basePhase, phase_id: 'main', name: 'Processing', description: 'Processing your request' }
      ];
  }
}

function getInitialAgentMessage(agentType: AgentType, prompt: string): string {
  switch (agentType) {
    case 'comic':
      return `I'll create a comic based on your idea. Let me start by generating a script...\n\nYour idea: "${prompt}"`;
    case 'ppt':
      return `I'll create a presentation for you. Let me start by generating an outline...\n\nTopic: "${prompt}"`;
    case 'coding':
    case 'codingv2':
    case 'codingv3':
      return `I'll help you with this coding task. Let me analyze the requirements and create a plan...\n\nTask: "${prompt}"`;
    case 'analyzer':
      return `I'll analyze the codebase. Starting the discovery phase...\n\nFocus: "${prompt}"`;
    case 'reviewer':
      return `I'll review the code you've provided. Let me analyze it for issues, best practices, and potential improvements...\n\nReview scope: "${prompt}"`;
    case 'product':
      return `I'll help you brainstorm and document this product idea. Starting with discovery...\n\nIdea: "${prompt}"`;
    case 'architect':
      return `I'll help design the architecture. Let me analyze the requirements...\n\nSystem: "${prompt}"`;
    case 'research':
      return `I'll research this topic for you. Let me gather information...\n\nResearch topic: "${prompt}"`;
    case 'prompt_refiner':
      return `I'll analyze and refine your prompt. Let me evaluate its quality and suggest improvements...\n\nPrompt: "${prompt}"`;
    default:
      return `I'll help you with this request. Processing...\n\n"${prompt}"`;
  }
}
