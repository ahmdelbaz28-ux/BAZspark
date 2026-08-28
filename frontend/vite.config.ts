// NOSONAR
/// <reference types="vitest" />

import * as path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { mockupPreviewPlugin } from "./mockupPreviewPlugin.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const port = process.env.PORT ? Number(process.env.PORT) : 5173;
const basePath = process.env.BASE_PATH || "/";

const isTest = process.argv.some((arg) => arg.includes("vitest"));
const isProduction = process.env.NODE_ENV === "production";

// Injects the API URL into the CSP connect-src directive at build time
function cspInjectPlugin(): import("vite").Plugin {
        return {
                name: "csp-inject",
                transformIndexHtml(html) {
                        const apiUrl = process.env.VITE_API_URL || "/api/v1";
                        // V158 FIX (root cause): Previous logic fell back to `origin = apiUrl`
                        // for relative URLs like "/api/v1". This produced an INVALID CSP
                        // `connect-src` entry: "/api/v1" is not a valid CSP source (CSP
                        // requires 'self', 'none', a scheme-host-port tuple, or wildcards).
                        // Browsers log a console error:
                        //   "The source list for the Content Security Policy directive
                        //    'connect-src' contains an invalid source: '/api/v1'. It will be
                        //    ignored."
                        // This caused all 8 Playwright visual smoke tests in
                        // tests/visual/smoke.spec.ts to fail with "Console errors on /<page>".
                        //
                        // Root-cause fix: when apiUrl is a relative URL (no scheme+host),
                        // the CSP already covers it via the 'self' source that is hardcoded
                        // in index.html's connect-src directive. So we emit an EMPTY string
                        // for relative URLs — adding nothing to CSP — which is correct
                        // because relative API calls are same-origin and 'self' covers them.
                        //
                        // For absolute URLs (e.g., "https://api.fireai.example.com"), we
                        // extract the origin and also derive the matching ws/wss origin.
                        let origin = "";
                        let wsOrigin = "";
                        try {
                                const parsed = new URL(apiUrl);
                                // If URL parsing succeeded and we have a protocol + host, it's absolute
                                if (parsed.protocol && parsed.host) {
                                        origin = parsed.origin;
                                        wsOrigin = origin.startsWith("https")
                                                ? origin.replace("https", "wss")
                                                : "";
                                }
                                // Else: leave origin/wsOrigin empty (relative URL — 'self' covers it)
                        } catch {
                                // URL() threw — apiUrl is a relative path like "/api/v1".
                                // Leave origin/wsOrigin empty; 'self' in CSP covers same-origin calls.
                        }
                        const cspConnect = [origin, wsOrigin].filter(Boolean).join(" ");
                        return html.replaceAll("__CSP_CONNECT_SRC__", cspConnect);
                },
        };
}

export default defineConfig({
        base: basePath,
        plugins: [
                !isProduction && !isTest && mockupPreviewPlugin(),
                react(),
                isTest ? null : tailwindcss(),
                isTest ? null : cspInjectPlugin(),
                // F-05 FIX (Engineering Review): the `preview-api-mock` plugin has been
                // REMOVED. The previous version intercepted every /api/* request during
                // `vite preview` and returned a canned `success: true` response — which
                // meant Lighthouse / preview audits would always see a "healthy" backend
                // even when the real FastAPI backend was broken or returning 502s. This
                // masked real integration defects and made every "Lighthouse 100/100/100"
                // claim in the documentation meaningless.
                //
                // If you need a mock backend for Lighthouse audits, run a real mock
                // server (e.g. MSW in `server` mode, or a tiny FastAPI stub) on the
                // configured API port. Do NOT inline the mock into vite preview — it
                // destroys the audit's signal.
        ].filter(Boolean),
        optimizeDeps: {
                // Force pre-bundle lucide-react so its 1,583+ internal modules are
                // bundled into a single optimized chunk by esbuild on dev startup.
                // Without this, the first page load triggers a cascade of
                // transform requests for each icon module, adding 200-800ms to
                // cold-start time per import.
                include: ["lucide-react", "framer-motion"],
        },
        resolve: {
                alias: {
                        "@": path.resolve(__dirname, "src"),
                },
        },
        build: {
                outDir: path.resolve(__dirname, "dist"),
                emptyOutDir: true,
                // V242: Generate "hidden" source maps in production so Lighthouse's
                // valid-source-maps audit passes (it checks for .map files alongside
                // the JS chunks). "hidden" = the .map files are emitted but the
                // `//# sourceMappingURL=` comment is NOT added to the JS, so
                // browsers/devtools won't auto-load them. This satisfies Lighthouse
                // (the .map files exist for error-stack resolution in monitoring)
                // while preserving the security posture (no automatic source exposure
                // to end users). In development, full source maps are still emitted.
                sourcemap: isProduction ? "hidden" : true,
                minify: "terser",
                terserOptions: {
                        // SECURITY: Remove console.log/debugger in production.
                        // Keep console.error and console.warn — they're useful for
                        // runtime error tracking and don't leak sensitive info.
                        format: {
                                comments: false,
                        },
                        module: true,
                        toplevel: true,
                        compress: {
                                drop_console: false, // V242: don't drop — let Lighthouse see we have no errors
                                pure_funcs: isProduction
                                        ? ["console.log", "console.debug", "console.info"]
                                        : [],
                                drop_debugger: true,
                        },
                },

                // V242: Code splitting — separate vendor chunks to reduce initial bundle.
                // lucide-react is split into its own chunk (~100kB) so it's only loaded
                // when icons render, not on the initial page paint.
                rollupOptions: {
                        output: {
                                manualChunks(id) {
                                        if (
                                                id.includes("node_modules/react/") ||
                                                id.includes("node_modules/react-dom/") ||
                                                id.includes("node_modules/react-router/") ||
                                                id.includes("node_modules/react-router-dom/")
                                        ) {
                                                return "vendor-react";
                                        }
                                        if (id.includes("node_modules/@radix-ui/")) {
                                                return "vendor-ui";
                                        }
                                        if (id.includes("node_modules/@tanstack/")) {
                                                return "vendor-tanstack";
                                        }
                                        if (
                                                id.includes("node_modules/i18next/") ||
                                                id.includes("node_modules/react-i18next/")
                                        ) {
                                                return "vendor-i18n";
                                        }
                                        if (id.includes("node_modules/recharts/")) {
                                                return "vendor-chart";
                                        }
                                        if (id.includes("node_modules/three/")) {
                                                return "vendor-3d";
                                        }
                                        if (id.includes("node_modules/lucide-react/")) {
                                                return "vendor-icons";
                                        }
                                },
                        },
                        // V216/V287 FIX (Gate 4b — Visual Regression):
                        // REMOVED `external: ["gsap/SplitText", "gsap/DrawSVGPlugin", "gsap/CustomEase"]`.
                        //
                        // These gsap subpaths are NOT external — they ship as proper ES
                        // modules inside node_modules/gsap/ (CustomEase.js, DrawSVGPlugin.js,
                        // SplitText.js) and are resolvable via the gsap package.json exports
                        // map ("./*.js": { "import": "./*.js" }). Marking them as `external`
                        // told Rollup to leave them as bare specifiers in the production
                        // bundle, expecting the runtime environment to resolve them via an
                        // import map. But the production HTML has NO import map, so the
                        // browser failed with:
                        //     TypeError: Failed to resolve module specifier "gsap/CustomEase".
                        //     Relative references must start with "/", "./", or "../".
                        //
                        // This error propagated to React's ErrorRecovery boundary (logged
                        // as "[BAZSPARK] Fatal error caught by boundary"), which the visual
                        // smoke tests' expectNoConsoleErrors helper caught → Gate 4b failed.
                        //
                        // Without `external`, Rollup bundles these subpaths into chunks
                        // and the browser resolves the relative chunk URLs at runtime.
                        // The try/catch in useGsapAnimations.ts::loadClubPlugins still
                        // gracefully degrades if a plugin is somehow unavailable.
                },
                chunkSizeWarningLimit: 600,
                // V242: Aggressive module preloading for faster navigation.
                modulePreload: { polyfill: true },
                // V242: ES2020 target — modern browsers support optional chaining,
                // nullish coalescing, and class fields natively. Skipping the
                // down-level transpilation reduces bundle size and parse time.
                target: "es2020",
        },
        server: {
                port,
                // SECURITY: Bind to localhost only (not 0.0.0.0) to prevent network exposure
                host: process.env.VITE_DEV_HOST || "localhost",
                // SECURITY: Restrict allowed hosts to prevent DNS rebinding attacks
                allowedHosts: process.env.VITE_ALLOWED_HOSTS
                        ? process.env.VITE_ALLOWED_HOSTS.split(",")
                        : ["localhost"],
                // SECURITY: Enable fs.strict to prevent path traversal outside project root
                fs: {
                        strict: true,
                },
                // Security headers for development server
                headers: {
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "DENY",
                        "X-XSS-Protection": "1; mode=block",
                        "Referrer-Policy": "strict-origin-when-cross-origin",
                        // V190 FIX: frame-ancestors MUST be delivered via HTTP header (not
                        // <meta>). The <meta> CSP tag is honored for most directives but
                        // NOT for frame-ancestors per CSP3 spec. Set it here so the dev
                        // server enforces clickjacking protection. Production (Vercel/HF
                        // Space) must set the same header via their config.
                        "Content-Security-Policy-Frame-Ancestors": "'none'",
                },
                proxy: {
                        "/api": {
                                target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
                                changeOrigin: true,
                        },
                        "/ws": {
                                target: process.env.VITE_API_PROXY_TARGET || "ws://localhost:8000",
                                ws: true,
                        },
                },
        },
        preview: {
                port,
                host: "localhost",
                allowedHosts: ["localhost"],
        },
        ...(isTest
                ? {
                                test: {
                                        globals: true,
                                        environment: "jsdom",
                                        setupFiles: ["./src/test/setup.ts"],
                                        css: true,
                                        // V242: Use forks pool instead of threads — more reliable
                                        // teardown for jsdom + React testing-library.
                                        pool: "forks",
                                        // V301 FIX: Vitest 4 removed poolOptions — singleFork is now
                                        // a top-level option. Without this, Vitest 4 ignores the
                                        // deprecated poolOptions.forks.singleFork, causing
                                        // EnvironmentTeardownError race conditions where apiKey.ts
                                        // is imported after env teardown in parallel test workers.
                                        singleFork: true,
                                        // V242: Give the pool enough time to tear down jsdom + React.
                                        // V300: Increased from 30000 to 60000 to prevent teardown
                                        // race conditions in CI with slow runners.
                                        teardownTimeout: 60000,
                                        // V242: Don't hang the process if a test leaves a timer open.
                                        // V301: Increased from 30000 to 60000 to prevent CI timeout
                                        // on slow runners where the Vite server takes longer to close.
                                        closeTimeout: 60000,
                                        // V242: Force exit after all tests pass. The Vite dev server
                                        // inside Vitest sometimes keeps the process alive due to
                                        // jsdom's internal timers. This is safe because we're in CI
                                        // and don't need the server after tests complete.
                                        forceExit: true,
                                        // P0-13 FIX: Generate lcov coverage report for SonarCloud.
                                        coverage: {
                                                provider: "v8",
                                                reporter: ["html", "lcov", "text-summary"],
                                                reportsDirectory: "coverage",
                                        },
                                        // V156 FIX: Exclude Playwright visual tests from Vitest collection.
                                        // tests/visual/*.spec.ts are Playwright test files (use @playwright/test's
                                        // test() function). When Vitest discovers them, it fails with:
                                        //   "Playwright Test did not expect test() to be called here"
                                        // because Playwright's test() is not the same as Vitest's test().
                                        // These tests must be run with `npx playwright test`, not `npx vitest`.
                                        // Excluding them here makes `npm run test` (Vitest) pass 100%.
                                        exclude: [
                                                "**/node_modules/**",
                                                "**/dist/**",
                                                "**/cypress/**",
                                                "**/.{idea,git,cache,output,temp}/**",
                                                "**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*",
                                                "tests/**",
                                        ],
                                },
                        }
                : {}),
});
