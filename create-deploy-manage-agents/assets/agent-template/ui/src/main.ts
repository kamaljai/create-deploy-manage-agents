// Renders the agent's A2UI v0.9 task surface and sends user actions back to the agent.
import {ContextProvider} from '@lit/context';
import {renderMarkdown} from '@a2ui/markdown-it';
import {MessageProcessor, type ActionPayload} from '@a2ui/web_core/v0_9';
import {A2uiSurface, Context, basicCatalog} from '@a2ui/lit/v0_9';

// Keep the <a2ui-surface> element registration in the bundle.
void A2uiSurface;

const VERSION = 'v0.9';
const host = document.getElementById('app')!;

// Text components render Markdown through this sanitizing (DOMPurify) renderer.
new ContextProvider(host, {context: Context.markdown, initialValue: renderMarkdown});

function showError(message: string): void {
  const el = document.createElement('p');
  el.className = 'error';
  el.textContent = message;
  host.append(el);
}

async function streamMessages(response: Response): Promise<void> {
  if (!response.ok || !response.body) {
    showError(`Agent request failed (${response.status})`);
    return;
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const {value, done} = await reader.read();
    if (done) break;
    buffer += value;
    let newline: number;
    while ((newline = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) processor.processMessages([JSON.parse(line)]);
    }
  }
}

async function sendAction(action: ActionPayload): Promise<void> {
  try {
    const response = await fetch('/a2ui/action', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({version: VERSION, action}),
    });
    await streamMessages(response);
  } catch (error) {
    showError(`Could not reach the agent: ${String(error)}`);
  }
}

const processor = new MessageProcessor([basicCatalog], sendAction);

processor.onSurfaceCreated(surface => {
  const element = document.createElement('a2ui-surface') as HTMLElement & {surface: unknown};
  element.surface = surface;
  host.replaceChildren(element);
});

try {
  const response = await fetch('/a2ui/surface');
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  processor.processMessages(await response.json());
} catch (error) {
  host.textContent = '';
  showError(`Could not load the agent UI: ${String(error)}`);
}
