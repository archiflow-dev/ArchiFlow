import { useEffect, useRef, useState } from 'react';
import {
  Send,
  Bot,
  User,
  Info,
  Loader2,
  Paperclip,
  MoreVertical,
  Copy,
  RefreshCw,
  Wifi,
  WifiOff,
  Wrench
} from 'lucide-react';
import { useChatStore } from '../../store';
import { useWorkflowStore } from '../../store/workflowStore';
import { useSessionStore } from '../../store/sessionStore';
import { useCommandHistoryStore } from '../../store/commandHistoryStore';
import { useWebSocket } from '../../hooks/useWebSocket';
import { formatTimestamp, cn } from '../../lib/utils';
import type { ChatMessage, ToolCall } from '../../types';

export function ChatPanel() {
  const { messages, streamingMessages, clearMessages } = useChatStore();
  const { workflow } = useWorkflowStore();
  const { currentSession } = useSessionStore();
  const { addToHistory, navigateUp, navigateDown, resetIndex } = useCommandHistoryStore();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Initialize WebSocket connection
  const {
    status,
    isConnected,
    isAgentProcessing,
    sendMessage,
  } = useWebSocket({
    sessionId: currentSession?.session_id,
    autoConnect: true,
    syncStores: true,
  });

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessages]);

  // Auto-resize textarea with better multi-line support
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      // Allow more expansion for multi-line input
      const scrollHeight = inputRef.current.scrollHeight;
      inputRef.current.style.height = Math.min(scrollHeight, 200) + 'px';
    }
  }, [input]);

  const handleSend = () => {
    if (!input.trim() || !isConnected || isAgentProcessing) return;

    console.log('[ChatPanel] 📤 Sending message:', {
      content: input,
      sessionId: currentSession?.session_id,
      isConnected,
      isAgentProcessing,
      timestamp: new Date().toISOString()
    });

    // Add to command history before sending
    addToHistory(input);

    sendMessage(input);
    setInput('');
    // Reset history index when sending
    resetIndex();
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    // Handle command history navigation
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      const previousCommand = navigateUp();
      if (previousCommand) {
        setInput(previousCommand);
        // Move cursor to end
        setTimeout(() => {
          if (inputRef.current) {
            inputRef.current.selectionStart = inputRef.current.selectionEnd = previousCommand.length;
          }
        }, 0);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextCommand = navigateDown();
      setInput(nextCommand);
      // Move cursor to end
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.selectionStart = inputRef.current.selectionEnd = nextCommand.length;
        }
      }, 0);
      return;
    }

    // Enter to send, Shift+Enter for new line
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    // Allow Ctrl+Enter to also send (common convention)
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    clearMessages();
  };

  // Get streaming message content for display
  const getStreamingContent = (): { id: string; content: string }[] => {
    const result: { id: string; content: string }[] = [];
    streamingMessages.forEach((msg, id) => {
      result.push({ id, content: msg.content });
    });
    return result;
  };

  const streamingContent = getStreamingContent();

  return (
    <div className="flex flex-col h-full bg-gray-850">
      {/* Header */}
      <div className="flex-shrink-0 h-9 px-3 flex items-center justify-between border-b border-gray-700 bg-gray-800/50">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Chat
            </span>
            {/* Connection status indicator */}
            <ConnectionIndicator status={status} />
          </div>
          {/* Project context indicator */}
          {currentSession && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span className="px-2 py-0.5 bg-gray-800 rounded">
                {currentSession.session_id?.slice(0, 8)}
              </span>
              {currentSession.project_directory && (
                <span className="text-gray-600" title={currentSession.project_directory}>
                  {currentSession.project_directory.split(/[\\/]/).slice(-2).join('/')}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleClearChat}
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
            title="Clear chat"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button className="p-1 text-gray-500 hover:text-gray-300 transition-colors" title="More options">
            <MoreVertical className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {messages.length === 0 && streamingContent.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full px-6 text-center">
            <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
              <Bot className="w-6 h-6 text-gray-600" />
            </div>
            <p className="text-gray-500 text-sm">No messages yet</p>
            <p className="text-gray-600 text-xs mt-1">
              {isConnected
                ? 'Start a conversation with the agent'
                : 'Connecting to server...'}
            </p>
          </div>
        ) : (
          <div className="py-4 space-y-1">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {/* Streaming messages */}
            {streamingContent.map(({ id, content }) => (
              <StreamingMessageBubble key={id} content={content} />
            ))}

            {/* Typing indicator */}
            {isAgentProcessing && streamingContent.length === 0 && (
              <div className="flex items-start gap-2 px-3 py-2">
                <div className="w-7 h-7 rounded-full bg-blue-600/20 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-blue-400" />
                </div>
                <div className="bg-gray-800 rounded-lg px-3 py-2 flex items-center gap-1">
                  <Loader2 className="w-3.5 h-3.5 text-gray-400 animate-spin" />
                  <span className="text-xs text-gray-400">Thinking...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex-shrink-0 p-3 border-t border-gray-700 bg-gray-800/30">
        <div className="flex flex-col gap-2">
          <div className="relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder={
                !isConnected
                  ? 'Connecting...'
                  : isAgentProcessing
                  ? 'Agent is processing...'
                  : 'Type a message... (Enter=send, Shift+Enter=new line)'
              }
              disabled={!isConnected}
              rows={1}
              className={cn(
                'w-full resize-none px-3 py-2 pr-10 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50',
                'transition-all duration-200',
                'min-h-[40px] max-h-[200px]',
                'overflow-y-auto',
                !isConnected && 'opacity-50 cursor-not-allowed'
              )}
              style={{ fieldSizing: 'content' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || !isConnected || isAgentProcessing}
              className={cn(
                'absolute right-2 bottom-2 p-1.5 rounded transition-colors',
                input.trim() && isConnected && !isAgentProcessing
                  ? 'text-blue-400 hover:text-blue-300 hover:bg-blue-500/20'
                  : 'text-gray-600'
              )}
            >
              {isAgentProcessing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>

          {/* Quick actions */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors" title="Attach file">
                <Paperclip className="w-4 h-4" />
              </button>
            </div>
            <div className="text-xs text-gray-600">
              <span className="mr-3">↑↓ = history</span>
              <span className="mr-3">Enter = send</span>
              <span>Shift+Enter = new line</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Connection status indicator
interface ConnectionIndicatorProps {
  status: 'disconnected' | 'connecting' | 'connected' | 'error';
}

function ConnectionIndicator({ status }: ConnectionIndicatorProps) {
  const statusConfig = {
    disconnected: { icon: WifiOff, color: 'text-gray-500', label: 'Disconnected' },
    connecting: { icon: Wifi, color: 'text-yellow-500 animate-pulse', label: 'Connecting' },
    connected: { icon: Wifi, color: 'text-green-500', label: 'Connected' },
    error: { icon: WifiOff, color: 'text-red-500', label: 'Error' },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-1" title={config.label}>
      <Icon className={cn('w-3 h-3', config.color)} />
    </div>
  );
}

// Streaming message bubble (for in-progress messages)
interface StreamingMessageBubbleProps {
  content: string;
}

function StreamingMessageBubble({ content }: StreamingMessageBubbleProps) {
  return (
    <div className="flex items-start gap-2 px-3 py-2">
      <div className="w-7 h-7 rounded-full bg-blue-600/20 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-blue-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-gray-400">Agent</span>
          <span className="px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded text-[10px]">
            Streaming...
          </span>
        </div>
        <div className="bg-gray-800 rounded-lg px-3 py-2 max-w-[95%]">
          <div className="text-sm text-gray-200 whitespace-pre-wrap break-words">
            {content}
            <span className="inline-block w-2 h-4 ml-1 bg-blue-400 animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  );
}

interface MessageBubbleProps {
  message: ChatMessage;
}

function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.type === 'user';
  const isSystem = message.type === 'system';
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  if (isSystem) {
    return (
      <div className="flex items-start gap-2 px-3 py-2">
        <div className="w-7 h-7 rounded-full bg-gray-600/20 flex items-center justify-center flex-shrink-0">
          <Info className="w-4 h-4 text-gray-400" />
        </div>
        <div className="bg-gray-800/50 rounded-lg px-3 py-2 max-w-[95%]">
          <div className="text-sm text-gray-300 whitespace-pre-wrap break-words">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      'group flex items-start gap-2 px-3 py-2 hover:bg-gray-800/30 transition-colors',
      isUser ? 'flex-row-reverse' : ''
    )}>
      {/* Avatar */}
      <div className={cn(
        'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0',
        isUser ? 'bg-green-600/20' : 'bg-blue-600/20'
      )}>
        {isUser ? (
          <User className="w-4 h-4 text-green-400" />
        ) : (
          <Bot className="w-4 h-4 text-blue-400" />
        )}
      </div>

      {/* Message content */}
      <div className={cn(
        'flex-1 min-w-0',
        isUser && 'flex flex-col items-end'
      )}>
        {/* Header with phase badge */}
        <div className={cn(
          'flex items-center gap-2 mb-1',
          isUser && 'flex-row-reverse'
        )}>
          <span className="text-xs font-medium text-gray-400">
            {isUser ? 'You' : 'Agent'}
          </span>
          {message.phase && (
            <span className="px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded text-[10px]">
              {message.phase}
            </span>
          )}
          <span className="text-[10px] text-gray-600">
            {formatTimestamp(message.timestamp)}
          </span>
        </div>

        {/* Content */}
        <div className={cn(
          'rounded-lg px-3 py-2 max-w-[95%]',
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-200'
        )}>
          <div className="text-sm whitespace-pre-wrap break-words">
            {message.content}
          </div>

          {/* Tool calls */}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-700/50">
              <div className="text-[10px] text-gray-500 uppercase mb-1 flex items-center gap-1">
                <Wrench className="w-3 h-3" />
                Tool Calls
              </div>
              <div className="flex flex-wrap gap-1">
                {message.tool_calls.map((tool: ToolCall, idx: number) => (
                  <span
                    key={idx}
                    className={cn(
                      'px-1.5 py-0.5 rounded text-[10px]',
                      tool.result ? 'bg-green-500/20 text-green-400' :
                      tool.error ? 'bg-red-500/20 text-red-400' :
                      'bg-gray-700 text-gray-400'
                    )}
                  >
                    {tool.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Actions (shown on hover) */}
        {!isUser && (
          <div className="flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleCopy}
              className="p-1 text-gray-600 hover:text-gray-400 transition-colors"
              title={copied ? 'Copied!' : 'Copy message'}
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
