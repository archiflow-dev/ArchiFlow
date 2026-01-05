/**
 * Services barrel export.
 */

// Base API
export { api, ApiError, API_BASE, checkApiHealth, getDownloadUrl } from './api';
export type { RequestOptions } from './api';

// Session API
export { sessionApi } from './sessionApi';
export type {
  SessionCreateRequest,
  SessionUpdateRequest,
  SessionResponse,
  SessionListResponse,
  SessionListParams,
  SessionStatusApi,
} from './sessionApi';

// Agent API
export { agentApi } from './agentApi';
export type {
  AgentInfo,
  AgentCapability,
  AgentCategory,
  AgentListResponse,
  AgentListParams,
  WorkflowDefinition,
  WorkflowPhaseDefinition,
} from './agentApi';

// Artifact API
export { artifactApi } from './artifactApi';
export type {
  ArtifactInfo,
  ArtifactContent,
  ArtifactListResponse,
  ArtifactCreateRequest,
  ArtifactUpdateRequest,
} from './artifactApi';

// Workflow API
export { workflowApi } from './workflowApi';
export type {
  WorkflowState,
  WorkflowPhase,
  PhaseStatusApi,
  ApprovalRequest,
  ApprovalResponse,
} from './workflowApi';

// Message API
export { messageApi } from './messageApi';
export type {
  MessageResponse,
  MessageListResponse,
  MessageCreateRequest,
  MessageListParams,
  MessageRoleApi,
  ToolCallInfo,
} from './messageApi';

// WebSocket
export {
  WebSocketClient,
  getWebSocketClient,
  initWebSocket,
} from './websocket';
export type {
  ConnectionStatus,
  WebSocketEvent,
  AgentMessageEvent,
  MessageChunkEvent,
  ToolCallEvent,
  ToolResultEvent,
  WorkflowUpdateEvent,
  ArtifactUpdateEvent,
  SessionUpdateEvent,
  AgentEventWrapper,
  WaitingForInputEvent,
  AgentFinishedEvent,
  ErrorEvent,
  WebSocketEventType,
  EventHandler,
  StoreCallbacks,
} from './websocket';
