import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Chatbot } from '@/Chatbot';

class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readonly url: string;
  readyState = MockWebSocket.OPEN;
  sent: string[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send = (data: string) => {
    this.sent.push(data);
  };

  close = () => {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  };

  receive = (frame: unknown) => {
    this.onmessage?.({ data: JSON.stringify(frame) } as MessageEvent);
  };
}

const sessionResponse = (id: string) =>
  Promise.resolve({
    ok: true,
    status: 201,
    json: () => Promise.resolve({ id }),
  } as Response);

const openReadyChat = async () => {
  fireEvent.click(screen.getByRole('button', { name: 'Open assistant' }));
  await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
  const socket = MockWebSocket.instances[0];
  socket.receive({ object: 'session.ready' });
  await screen.findByText('Connected');
  return socket;
};

describe('Chatbot', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal(
      'fetch',
      vi.fn(() => sessionResponse('session-1'))
    );
    HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('creates a session, sends a prompt, and renders tool activity and the final answer', async () => {
    render(<Chatbot selectedTeam="Team Bravo" />);
    const socket = await openReadyChat();

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/agents/sessions',
      expect.objectContaining({ method: 'POST' })
    );
    expect(socket.url).toMatch(/\/api\/v1\/agents\/sessions\/session-1\/ws$/);

    socket.receive({
      object: 'agent.event',
      replay: true,
      event: { type: 'turn.completed', payload: { text: 'Previous summary' } },
    });
    expect(await screen.findByText('Previous summary')).toBeInTheDocument();

    const input = screen.getByLabelText('Message Execution Partner');
    fireEvent.change(input, { target: { value: 'What is at risk?' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(JSON.parse(socket.sent[0])).toEqual({
      command: 'prompt',
      prompt:
        '[Jira context: Scope Jira queries to Agile Team = "Team Bravo". Use jira_search or acli and do not query other teams unless requested.]\n\nWhat is at risk?',
    });
    expect(screen.getByLabelText('Jira context: Team Bravo')).toBeInTheDocument();
    expect(screen.getByText('What is at risk?')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Assistant is responding');

    socket.receive({
      object: 'agent.event',
      event: {
        type: 'tool.requested',
        payload: { tool_call_id: 'call-1', tool: 'get_team_context', arguments: {} },
      },
    });
    socket.receive({
      object: 'agent.event',
      event: {
        type: 'tool.completed',
        payload: { tool_call_id: 'call-1', tool: 'get_team_context', result: { risks: 2 } },
      },
    });
    socket.receive({
      object: 'agent.event',
      event: { type: 'text.delta', payload: { text: 'Two risks' } },
    });
    socket.receive({
      object: 'agent.event',
      event: { type: 'turn.completed', payload: { text: 'Two risks need attention.' } },
    });

    expect(await screen.findByText('get team context')).toBeInTheDocument();
    expect(screen.getByText('finished')).toBeInTheDocument();
    expect(screen.getByText('Two risks need attention.')).toBeInTheDocument();
    expect(screen.queryByText('Two risks')).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('preserves the conversation when closed and starts a clean new chat', async () => {
    render(<Chatbot selectedTeam={null} />);
    const firstSocket = await openReadyChat();
    const input = screen.getByLabelText('Message Execution Partner');
    fireEvent.change(input, { target: { value: 'Keep this' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    fireEvent.click(screen.getAllByRole('button', { name: 'Close assistant' })[0]);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open assistant' }));

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(2));
    expect(screen.getByText('Keep this')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Start a new chat' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(firstSocket.readyState).toBe(MockWebSocket.CLOSED);
    expect(screen.queryByText('Keep this')).not.toBeInTheDocument();
  });

  it('supports quick prompts, interruption, replay, and visible protocol errors', async () => {
    render(<Chatbot selectedTeam={null} />);
    const socket = await openReadyChat();

    fireEvent.click(screen.getByRole('button', { name: 'What should I focus on today?' }));
    fireEvent.click(screen.getByRole('button', { name: 'Stop response' }));
    expect(JSON.parse(socket.sent[1])).toEqual({ command: 'interrupt' });

    socket.receive({
      object: 'agent.event',
      replay: true,
      event: { type: 'turn.interrupted', payload: {} },
    });
    socket.receive({ object: 'command.rejected', reason: 'A turn is already running' });
    expect(await screen.findByRole('alert')).toHaveTextContent('A turn is already running');

    socket.receive({ object: 'agent.error', reason: 'Agent turn failed' });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Agent turn failed'));
  });

  it('retries failed session creation and connects the new session', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 503,
    } as Response);
    render(<Chatbot selectedTeam={null} />);
    fireEvent.click(screen.getByRole('button', { name: 'Open assistant' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not start chat (503)');

    fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }));
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(MockWebSocket.instances[0].url).toMatch(/\/api\/v1\/agents\/sessions\/session-1\/ws$/);

    MockWebSocket.instances[0].receive({ object: 'session.ready' });
    expect(await screen.findByText('Connected')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows websocket failures', async () => {
    render(<Chatbot selectedTeam={null} />);
    const socket = await openReadyChat();
    socket.onerror?.();
    expect(await screen.findByRole('alert')).toHaveTextContent('Chat connection failed');
  });
});
