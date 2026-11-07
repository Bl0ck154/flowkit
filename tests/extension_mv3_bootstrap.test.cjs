const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.join(__dirname, '..', 'extension', 'background.js'),
  'utf8',
);

const lifecycleListeners = { alarm: [], installed: [], startup: [] };
const sockets = [];
const intervals = new Map();
let nextIntervalId = 1;
let storageReads = 0;
let tabCreates = 0;

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;

  constructor(url) {
    this.url = url;
    this.readyState = FakeWebSocket.CONNECTING;
    this.messages = [];
    sockets.push(this);
  }

  send(message) {
    this.messages.push(JSON.parse(message));
  }
}

function event(bucket) {
  return {
    addListener(listener) {
      if (bucket) bucket.push(listener);
    },
  };
}

const chrome = {
  action: { setBadgeBackgroundColor() {}, setBadgeText() {} },
  alarms: { clear() {}, create() {}, onAlarm: event(lifecycleListeners.alarm) },
  runtime: {
    getManifest() {
      return {
        version: '0.3.1',
        host_permissions: ['https://flow.google.com/*'],
      };
    },
    onInstalled: event(lifecycleListeners.installed),
    onMessage: event(),
    onStartup: event(lifecycleListeners.startup),
    sendMessage: async () => {},
  },
  scripting: { executeScript: async () => {} },
  storage: {
    local: {
      async get() {
        storageReads += 1;
        return {
          callbackSecret: 'persisted-secret',
          flowKey: 'persisted-flow-key',
          metrics: { tokenCapturedAt: 1234 },
        };
      },
      async set() {},
    },
  },
  tabs: {
    create: async () => {
      tabCreates += 1;
      return { id: 123, discarded: false };
    },
    get: async (id) => ({ id, discarded: false }),
    query: async () => [],
    reload: async () => {},
    remove: async () => {},
    sendMessage: async () => {},
    update: async () => {},
  },
  webRequest: { onBeforeSendHeaders: event() },
};

const context = vm.createContext({
  URL,
  WebSocket: FakeWebSocket,
  chrome,
  clearInterval(id) { intervals.delete(id); },
  clearTimeout() {},
  console,
  fetch: async () => ({ ok: true }),
  navigator: { userAgent: 'FlowkitBootstrapTest/1.0' },
  setInterval(callback, ms) { const id = nextIntervalId++; intervals.set(id, { callback, ms }); return id; },
  setTimeout() { return 1; },
});

vm.runInContext(source, context, { filename: 'background.js' });

setImmediate(async () => {
  await Promise.resolve();
  await Promise.resolve();

  assert.equal(storageReads, 1, 'cold worker start must hydrate storage exactly once');
  assert.equal(sockets.length, 1, 'cold worker start must connect after hydration');

  await lifecycleListeners.startup[0]();
  await lifecycleListeners.installed[0]();
  await lifecycleListeners.alarm[0]({ name: 'keepAlive' });
  assert.equal(storageReads, 1, 'lifecycle events must reuse initialization');
  assert.equal(sockets.length, 1, 'lifecycle events must not duplicate the socket');

  const socket = sockets[0];
  socket.readyState = FakeWebSocket.OPEN;
  socket.onopen();

  await lifecycleListeners.alarm[0]({ name: 'token-refresh' });
  assert.equal(tabCreates, 0, 'passive token refresh must never create a Flow tab');

  assert.equal(socket.messages[0].type, 'extension_ready');
  assert.equal(socket.messages[0].flowKeyPresent, true);
  assert.equal(socket.messages[0].extensionVersion, '0.3.1');
  assert.equal(socket.messages[0].flowUrlSupported, true);
  assert.ok(socket.messages[0].tokenAge > 0);
  assert.deepEqual(socket.messages[1], {
    type: 'token_captured',
    flowKey: 'persisted-flow-key',
  });

  const heartbeat = [...intervals.values()].find(({ ms }) => ms === 20000);
  assert.ok(heartbeat, 'active WebSocket must have a 20s MV3 keepalive');
  heartbeat.callback();
  assert.equal(socket.messages[2].type, 'ping', 'heartbeat must ping local agent');
  socket.onclose();
  assert.ok(
    ![...intervals.values()].some(({ ms }) => ms === 20000),
    'socket close must release the 20s keepalive',
  );

  console.log('Flowkit MV3 cold-start bootstrap regression test passed');
});
