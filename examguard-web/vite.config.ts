import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Three pages from one build, all served by the ExamGuard server (see examguard/webui.py):
//   /         landing page (peserta or staf)
//   /admin/   Admin Web (PRD §27)
//   /portal/  Candidate Portal (PRD §28)
// `npm run dev` proxies API calls to a server on :8080, so no CORS is needed.
const server = process.env.EXAMGUARD_SERVER ?? "http://127.0.0.1:8080";

/** Dev server: deep links such as /portal/reset-password?token=... load the app's index.html. */
function spaFallback(): Plugin {
  return {
    name: "examguard-spa-fallback",
    configureServer(dev) {
      dev.middlewares.use((req, _res, next) => {
        const url = req.url ?? "";
        const m = url.match(/^\/(admin|portal)(\/[^?]*)?(\?.*)?$/);
        if (m && !(m[2] ?? "").includes(".")) req.url = `/${m[1]}/index.html${m[3] ?? ""}`;
        next();
      });
    },
  };
}

export default defineConfig({
  base: "/",
  plugins: [react(), spaFallback()],
  server: {
    port: 5173,
    proxy: { "/api": server, "/healthz": server },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      input: { landing: "index.html", admin: "admin/index.html", portal: "portal/index.html" },
    },
  },
});
