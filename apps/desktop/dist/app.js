const endpointInput = document.querySelector('#endpoint');
const form = document.querySelector('#connection-form');
const retryButton = document.querySelector('#retry-button');
const statusText = document.querySelector('#status-text');
const statusIndicator = document.querySelector('#status-indicator');
const workspaceState = document.querySelector('#workspace-state');
const errorText = document.querySelector('#connection-error');
const storageKey = 'researchos-desktop-endpoint';

function normalizedEndpoint(value) {
  const candidate = value.trim().replace(/\/+$/, '');
  const url = new URL(candidate);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error('只支持 HTTP 或 HTTPS 地址。');
  return url.toString().replace(/\/$/, '');
}

function setState(state, message) {
  statusIndicator.className = `status-indicator ${state}`.trim();
  statusText.textContent = message;
  workspaceState.textContent = state === 'ready' ? 'Ready' : state === 'error' ? 'Unavailable' : 'Checking';
}

async function probe(endpoint, navigateOnSuccess) {
  errorText.hidden = true;
  setState('', '正在检查工作区');
  try {
    await fetch(`${endpoint}/login`, { method: 'GET', mode: 'no-cors', cache: 'no-store' });
    setState('ready', '工作区已就绪');
    localStorage.setItem(storageKey, endpoint);
    if (navigateOnSuccess) window.location.assign(`${endpoint}/login`);
    return true;
  } catch {
    setState('error', '当前地址尚未就绪');
    return false;
  }
}

async function connect() {
  try {
    const endpoint = normalizedEndpoint(endpointInput.value);
    endpointInput.value = endpoint;
    const ready = await probe(endpoint, false);
    if (!ready) {
      errorText.textContent = '无法连接该工作区。请确认 Web 服务已经启动，或检查部署地址。';
      errorText.hidden = false;
      return;
    }
    window.location.assign(`${endpoint}/login`);
  } catch (error) {
    setState('error', '地址格式不正确');
    errorText.textContent = error instanceof Error ? error.message : '请输入有效地址。';
    errorText.hidden = false;
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  void connect();
});

retryButton.addEventListener('click', () => {
  void connect();
});

const savedEndpoint = localStorage.getItem(storageKey) || 'http://localhost:3000';
endpointInput.value = savedEndpoint;
void probe(savedEndpoint, false);
