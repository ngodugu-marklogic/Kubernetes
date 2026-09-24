import { useEffect, useRef, useState } from 'react';

type ConnectionState = 'connecting' | 'disconnected' | 'error' | 'ready';
type Message = {
  id: string;
  role: 'assistant' | 'user';
  text: string;
};
type ToolActivity = {
  id: string;
  name: string;
  status: 'failed' | 'finished' | 'running';
  summary?: string;
};
type JsonRecord = Record<string, unknown>;

const quickPrompts = [
  'What should I focus on today?',
  'Help me identify delivery risks',
  'Summarize our current priorities',
];

interface ChatbotProps {
  selectedTeam: string | null;
}

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const stringValue = (value: unknown) => (typeof value === 'string' ? value : '');

const summarize = (value: unknown) => {
  if (value === undefined || value === null) return '';
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  return text.length > 600 ? `${text.slice(0, 600)}…` : text;
};

const Icon = ({ name }: { name: 'chat' | 'close' | 'new' | 'send' | 'stop' }) => {
  const paths = {
    chat: (
      <path d="M5 6.5A3.5 3.5 0 0 1 8.5 3h7A3.5 3.5 0 0 1 19 6.5v5a3.5 3.5 0 0 1-3.5 3.5H11l-4.7 3.5.9-3.8A3.5 3.5 0 0 1 5 11.5z" />
    ),
    close: <path d="m7 7 10 10M17 7 7 17" />,
    new: <path d="M12 5v14M5 12h14" />,
    send: <path d="m4 5 16 7-16 7 3-7zm3 7h13" />,
    stop: <path d="M7 7h10v10H7z" />,
  };
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      {paths[name]}
    </svg>
  );
};

export const Chatbot = ({ selectedTeam }: ChatbotProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string>();
  const [connection, setConnection] = useState<ConnectionState>('disconnected');
  const [messages, setMessages] = useState<Message[]>([]);
  const [tools, setTools] = useState<ToolActivity[]>([]);
  const [prompt, setPrompt] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState('');
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const socketRef = useRef<WebSocket | undefined>(undefined);
  const assistantIdRef = useRef<string | undefined>(undefined);
  const messagesRef = useRef(messages);
  const logEndRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);

  const nextId = (prefix: string) => `${prefix}-${++idRef.current}`;

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    if (isOpen) logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [isOpen, messages, tools, isStreaming]);

  useEffect(() => {
    if (!isOpen || sessionId) return;
    const controller = new AbortController();

    void fetch('/api/v1/agents/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Execution Partner chat' }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not start chat (${response.status})`);
        const body: unknown = await response.json();
        if (!isRecord(body) || !stringValue(body.id)) throw new Error('Invalid session response');
        setSessionId(stringValue(body.id));
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setConnection('error');
        setError(reason instanceof Error ? reason.message : 'Could not start chat');
      });

    return () => controller.abort();
  }, [connectionAttempt, isOpen, sessionId]);

  useEffect(() => {
    if (!isOpen || !sessionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(
      `${protocol}//${window.location.host}/api/v1/agents/sessions/${sessionId}/ws`
    );
    socketRef.current = socket;

    const updateAssistant = (text: string, final: boolean) => {
      if (!text) return;
      const currentId = assistantIdRef.current;
      if (currentId) {
        setMessages((current) =>
          current.map((message) =>
            message.id === currentId
              ? { ...message, text: final ? text : `${message.text}${text}` }
              : message
          )
        );
      } else {
        const id = nextId('assistant');
        assistantIdRef.current = id;
        setMessages((current) => [...current, { id, role: 'assistant', text }]);
      }
      if (final) assistantIdRef.current = undefined;
    };

    const updateTool = (payload: JsonRecord, status: ToolActivity['status'], eventType: string) => {
      const name =
        stringValue(payload.tool) || stringValue(payload.name) || stringValue(payload.tool_name);
      const eventId =
        stringValue(payload.tool_call_id) ||
        stringValue(payload.call_id) ||
        stringValue(payload.id);
      const summary =
        status === 'failed'
          ? summarize(payload.error ?? payload.reason)
          : status === 'finished'
            ? summarize(payload.result)
            : summarize(payload.arguments ?? payload.input);
      setTools((current) => {
        const index = current.findIndex(
          (tool) =>
            tool.status === 'running' &&
            ((eventId && tool.id === eventId) || (!eventId && tool.name === name))
        );
        const activity = {
          id: eventId || (index >= 0 ? current[index].id : nextId('tool')),
          name: name || 'Tool',
          status,
          summary,
        };
        if (index < 0 || eventType === 'tool.requested') return [...current, activity];
        return current.map((tool, toolIndex) => (toolIndex === index ? activity : tool));
      });
    };

    socket.onmessage = (messageEvent) => {
      let frame: unknown;
      try {
        frame = JSON.parse(String(messageEvent.data));
      } catch {
        setError('Received an unreadable response from the agent');
        return;
      }
      if (!isRecord(frame)) return;
      const object = stringValue(frame.object);
      if (object === 'session.ready') {
        setConnection('ready');
        return;
      }
      if (object === 'command.rejected' || object === 'agent.error') {
        setError(stringValue(frame.reason) || 'The agent could not complete that request');
        setIsStreaming(false);
        return;
      }
      if (object !== 'agent.event' || !isRecord(frame.event)) return;
      if (frame.replay === true && messagesRef.current.length > 0) return;

      const eventType = stringValue(frame.event.type);
      const payload = isRecord(frame.event.payload) ? frame.event.payload : {};
      if (eventType === 'text.delta') {
        updateAssistant(stringValue(payload.text) || stringValue(payload.delta), false);
      } else if (eventType.startsWith('tool.')) {
        const status =
          eventType === 'tool.requested'
            ? 'running'
            : eventType === 'tool.failed'
              ? 'failed'
              : 'finished';
        updateTool(payload, status, eventType);
      } else if (eventType === 'turn.completed') {
        updateAssistant(stringValue(payload.text), true);
        setIsStreaming(false);
      } else if (eventType === 'turn.interrupted') {
        assistantIdRef.current = undefined;
        setIsStreaming(false);
      } else if (eventType === 'turn.failed') {
        assistantIdRef.current = undefined;
        setError(stringValue(payload.error) || stringValue(payload.reason) || 'Agent turn failed');
        setIsStreaming(false);
      }
    };
    socket.onerror = () => {
      setConnection('error');
      setError('Chat connection failed');
      setIsStreaming(false);
    };
    socket.onclose = () => {
      if (socketRef.current === socket) {
        socketRef.current = undefined;
        setConnection((current) => (current === 'error' ? current : 'disconnected'));
        setIsStreaming(false);
      }
    };

    return () => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
      if (socketRef.current === socket) socketRef.current = undefined;
    };
  }, [connectionAttempt, isOpen, sessionId]);

  const sendPrompt = (value = prompt) => {
    const text = value.trim();
    const socket = socketRef.current;
    if (!text || connection !== 'ready' || isStreaming || !socket) return;
    setMessages((current) => [...current, { id: nextId('user'), role: 'user', text }]);
    setPrompt('');
    setError('');
    setIsStreaming(true);
    assistantIdRef.current = undefined;
    const scopedPrompt = selectedTeam
      ? `[Jira context: Scope Jira queries to Agile Team = ${JSON.stringify(selectedTeam)}. Use jira_search or acli and do not query other teams unless requested.]\n\n${text}`
      : text;
    socket.send(JSON.stringify({ command: 'prompt', prompt: scopedPrompt }));
  };

  const stop = () => {
    socketRef.current?.send(JSON.stringify({ command: 'interrupt' }));
  };

  const retryConnection = () => {
    socketRef.current?.close();
    socketRef.current = undefined;
    setError('');
    setConnection('connecting');
    setIsStreaming(false);
    setConnectionAttempt((attempt) => attempt + 1);
  };

  const newChat = () => {
    socketRef.current?.close();
    socketRef.current = undefined;
    assistantIdRef.current = undefined;
    setSessionId(undefined);
    setMessages([]);
    setTools([]);
    setPrompt('');
    setError('');
    setConnection('connecting');
    setIsStreaming(false);
    setConnectionAttempt((attempt) => attempt + 1);
  };

  return (
    <aside className="chatbot">
      {isOpen && (
        <section className="chat-dialog" role="dialog" aria-label="Execution Partner assistant">
          <header className="chat-header">
            <div className="chat-heading">
              <span className="chat-avatar">
                <Icon name="chat" />
              </span>
              <div>
                <h2>Execution Partner</h2>
                <p className={`connection connection-${connection}`}>
                  <span aria-hidden="true" />
                  {connection === 'ready'
                    ? 'Connected'
                    : connection === 'connecting'
                      ? 'Connecting…'
                      : connection === 'error'
                        ? 'Connection issue'
                        : 'Disconnected'}
                </p>
              </div>
            </div>
            <div className="chat-actions">
              <button type="button" onClick={newChat} aria-label="Start a new chat">
                <Icon name="new" />
              </button>
              <button type="button" onClick={() => setIsOpen(false)} aria-label="Close assistant">
                <Icon name="close" />
              </button>
            </div>
          </header>

          <div className="chat-log" role="log" aria-live="polite">
            {messages.length === 0 && tools.length === 0 && (
              <div className="chat-welcome">
                <span className="welcome-mark">
                  <Icon name="chat" />
                </span>
                <h3>How can I help?</h3>
                <p>Ask about priorities, risks, or your team’s delivery work.</p>
                <div className="quick-prompts">
                  {quickPrompts.map((quickPrompt) => (
                    <button
                      type="button"
                      key={quickPrompt}
                      onClick={() => sendPrompt(quickPrompt)}
                      disabled={connection !== 'ready'}
                    >
                      {quickPrompt}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((message) => (
              <article className={`chat-message chat-message-${message.role}`} key={message.id}>
                <span>{message.role === 'assistant' ? 'Partner' : 'You'}</span>
                <p>{message.text}</p>
              </article>
            ))}
            {tools.map((tool) => (
              <details className={`tool-activity tool-${tool.status}`} key={tool.id}>
                <summary>
                  <span className="tool-indicator" aria-hidden="true" />
                  <strong>{tool.name.replace(/_/g, ' ')}</strong>
                  <span>{tool.status}</span>
                </summary>
                {tool.summary && <pre>{tool.summary}</pre>}
              </details>
            ))}
            {isStreaming && (
              <div className="typing-indicator" role="status">
                <span />
                <span />
                <span />
                <span className="sr-only">Assistant is responding</span>
              </div>
            )}
            {error && (
              <div className="chat-error" role="alert">
                <p>{error}</p>
                {connection === 'error' && (
                  <button type="button" onClick={retryConnection}>
                    Retry connection
                  </button>
                )}
              </div>
            )}
            <div ref={logEndRef} />
          </div>

          <form
            className="chat-composer"
            onSubmit={(event) => {
              event.preventDefault();
              sendPrompt();
            }}
          >
            {selectedTeam && (
              <div className="chat-context" aria-label={`Jira context: ${selectedTeam}`}>
                <span aria-hidden="true">Jira</span>
                <strong>{selectedTeam}</strong>
              </div>
            )}
            <label htmlFor="chat-prompt" className="sr-only">
              Message Execution Partner
            </label>
            <textarea
              id="chat-prompt"
              rows={1}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  sendPrompt();
                }
              }}
              placeholder="Ask about your team’s work…"
              disabled={connection !== 'ready'}
            />
            {isStreaming ? (
              <button
                type="button"
                className="composer-action stop"
                onClick={stop}
                aria-label="Stop response"
              >
                <Icon name="stop" />
              </button>
            ) : (
              <button
                type="submit"
                className="composer-action"
                disabled={!prompt.trim() || connection !== 'ready'}
                aria-label="Send message"
              >
                <Icon name="send" />
              </button>
            )}
            <p>Enter to send · Shift + Enter for a new line</p>
          </form>
        </section>
      )}

      <button
        type="button"
        className={`chat-launcher${isOpen ? ' is-open' : ''}`}
        onClick={() => {
          if (!isOpen) {
            setConnection('connecting');
            setError('');
          }
          setIsOpen(!isOpen);
        }}
        aria-label={isOpen ? 'Close assistant' : 'Open assistant'}
        aria-expanded={isOpen}
      >
        <Icon name={isOpen ? 'close' : 'chat'} />
        {!isOpen && <span className="launcher-pulse" aria-hidden="true" />}
      </button>
    </aside>
  );
};
