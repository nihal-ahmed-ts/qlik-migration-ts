import enigma from 'enigma.js';
import WebSocket from 'ws';
import { createRequire } from 'module';

// enigma.js ships its JSON schemas as CommonJS; load via require.
const require = createRequire(import.meta.url);

// The QIX schema MUST be compatible with the engine image's version, or calls
// silently misbehave ("method not found"). Override with QIX_SCHEMA to match
// whatever `ls node_modules/enigma.js/schemas/` shows for your engine.
//   docker-compose engine: qlikcore/engine:12.1170.0  -> a 12.x schema.
const SCHEMA_VERSION = process.env.QIX_SCHEMA || '12.1306.0';
let schema;
try {
  schema = require(`enigma.js/schemas/${SCHEMA_VERSION}.json`);
} catch (e) {
  throw new Error(
    `QIX schema "${SCHEMA_VERSION}" not found in enigma.js/schemas/. ` +
    `Run: ls node_modules/enigma.js/schemas/  and set QIX_SCHEMA to a listed ` +
    `version matching your engine image. Original error: ${e.message}`
  );
}

const ENGINE_HOST = process.env.ENGINE_HOST || 'localhost';
const ENGINE_PORT = process.env.ENGINE_PORT || '9076';

/**
 * Opens a QIX session for a given app and returns { session, global, doc }.
 * appId is the filename the engine sees under /apps, e.g. "MyApp.qvf".
 */
export async function openApp(appId) {
  // A unique identity per connection keeps sessions isolated.
  const identity = `extract-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const url = `ws://${ENGINE_HOST}:${ENGINE_PORT}/app/${encodeURIComponent(appId)}/identity/${identity}`;

  const session = enigma.create({
    schema,
    url,
    createSocket: (u) => new WebSocket(u),
    // Suspend on unexpected close rather than throwing mid-extraction.
    suspendOnClose: false,
  });

  const global = await session.open();
  const doc = await global.openDoc(appId);
  return { session, global, doc };
}
