// Dev server for visual work on the 3D views, beside the usual one: Vite on 5175, talking to a mock-mode
// backend on 8103 (so it does not collide with 5173 / 8000).
//   node frontend/scripts/dev-polish.mjs
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { createServer } from "vite";

process.env.VITE_API_BASE ||= "http://localhost:8103";
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const server = await createServer({ root, configFile: join(root, "vite.config.ts"), server: { port: 5175, strictPort: true } });
await server.listen();
server.printUrls();
