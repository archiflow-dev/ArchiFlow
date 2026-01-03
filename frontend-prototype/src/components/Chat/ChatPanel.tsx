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
  RefreshCw
} from 'lucide-react';
import { useChatStore } from '../../store';
import { useWorkflowStore } from '../../store/workflowStore';
import { formatTimestamp, cn } from '../../lib/utils';
import type { ChatMessage, ToolCall } from '../../types';

export function ChatPanel() {
  const { messages, addMessage } = useChatStore();
  const { workflow } = useWorkflowStore();
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const handleSend = () => {
    if (!input.trim()) return;

    const currentPhase = workflow?.phases.find(p => p.phase_id === workflow.current_phase);

    addMessage({
      id: `msg-${Date.now()}`,
      type: 'user',
      content: input,
      timestamp: new Date().toISOString(),
      phase: currentPhase?.name
    });

    setInput('');
    setIsTyping(true);

    // Simulate agent response
    setTimeout(() => {
      setIsTyping(false);
      addMessage({
        id: `msg-${Date.now()}`,
        type: 'agent',
        content: 'I received your message. This is a mock response that would normally come from the ArchiFlow agent.',
        timestamp: new Date().toISOString(),
        phase: currentPhase?.name
      });
    }, 1500);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-850">
      {/* Header */}
      <div className="flex-shrink-0 h-9 px-3 flex items-center justify-between border-b border-gray-700 bg-gray-800/50">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Chat
        </span>
        <div className="flex items-center gap-1">
          <button className="p-1 text-gray-500 hover:text-gray-300 transition-colors" title="Clear chat">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button className="p-1 text-gray-500 hover:text-gray-300 transition-colors" title="More options">
            <MoreVertical className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full px-6 text-center">
            <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
              <Bot className="w-6 h-6 text-gray-600" />
            </div>
            <p className="text-gray-500 text-sm">No messages yet</p>
            <p className="text-gray-600 text-xs mt-1">Start a conversation with the agent</p>
          </div>
        ) : (
          <div className="py-4 space-y-1">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {/* Typing indicator */}
            {isTyping && (
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
              placeholder="Type a message..."
              rows={1}
              className="w-full resize-none px-3 py-2 pr-10 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className={cn(
                'absolute right-2 bottom-2 p-1.5 rounded transition-colors',
                input.trim()
                  ? 'text-blue-400 hover:text-blue-300 hover:bg-blue-500/20'
                  : 'text-gray-600'
              )}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>

          {/* Quick actions */}
          <div className="flex items-center gap-2">
            <button className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors" title="Attach file">
              <Paperclip className="w-4 h-4" />
            </button>
            <span className="text-xs text-gray-600">Press Enter to send, Shift+Enter for new line</span>
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
      <div className="flex justify-center px-3 py-2">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800/50 rounded-full">
          <Info className="w-3.5 h-3.5 text-gray-500" />
          <span className="text-xs text-gray-500">{message.content}</span>
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
              <div className="text-[10px] text-gray-500 uppercase mb-1">Tool Calls</div>
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
