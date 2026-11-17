// Copy the production build into the server package so `examguard serve` serves it at /, /admin/ and /portal/.
//   npm run build && npm run install-to-server
// Override the target with EXAMGUARD_SERVER_DIR (default: ../examguard-server).
import { cpSync, existsSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const serverDir = resolve(process.env.EXAMGUARD_SERVER_DIR ?? "../examguard-server");
const pkg = resolve(serverDir, "src/examguard");
if (!existsSync(pkg)) {
  console.error(`examguard-server not found at ${serverDir} (set EXAMGUARD_SERVER_DIR)`);
  process.exit(1);
}
for (const page of ["dist/index.html", "dist/admin/index.html", "dist/portal/index.html"]) {
  if (!existsSync(page)) {
    console.error(`${page} missing — run \`npm run build\` first`);
    process.exit(1);
  }
}
const target = resolve(pkg, "webui/site");
rmSync(target, { recursive: true, force: true });
rmSync(resolve(pkg, "webui/admin"), { recursive: true, force: true });   // layout before Phase 3b
cpSync("dist", target, { recursive: true });
console.log(`Web UI (landing, Admin Web, Candidate Portal) installed to ${target}`);
