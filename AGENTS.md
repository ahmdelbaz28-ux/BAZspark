# AGENTS.md — Workspace Skill Configuration

## Active Skills

The following skills are installed and active for this workspace. **Use them before any response.**

### 0. `using-superpowers` (META — always active)

- **Location:** `.agents/skills/using-superpowers/SKILL.md`
- **References:** `.agents/skills/using-superpowers/references/`
- **When:** EVERY conversation. Establishes the rule that skills must be invoked before ANY action.
- **Scope:** Enforces skill-first behavior, prevents rationalization, sets priority order for multi-skill tasks.

### 1. `vercel-react-best-practices`

- **Location:** `.agents/skills/vercel-react-best-practices/`
- **Rules:** `.agents/skills/vercel-react-best-practices/rules/`
- **Full guide:** `.agents/skills/vercel-react-best-practices/AGENTS.md`
- **When:** Any React/Next.js code generation, refactoring, or review.
- **Scope:** 70 rules across 8 categories (waterfalls, bundle, server, client, re-renders, rendering, JS perf, advanced).

### 2. `frontend-design`

- **Location:** `.agents/skills/frontend-design/SKILL.md`
- **When:** Building new UI or reshaping existing UI. Distinctive, intentional visual design.
- **Scope:** Aesthetic direction, typography, palette, layout, copy, motion, restraint.

### 3. `superdesign`

- **Location:** `.agents/skills/superdesign/SKILL.md`
- **References:** `.agents/skills/superdesign/references/`
- **When:** Building or refactoring design systems, creating component libraries, establishing design tokens, implementing consistent UI patterns.
- **Scope:** Design token systems, component architecture, accessibility standards, safety-critical UI patterns, visual design principles.

### 4. `security-audit`

- **Location:** `.agents/skills/security-audit/SKILL.md`
- **References:** `.agents/skills/security-audit/` (RECONNAISSANCE.md, HUNTING.md, ATTACK-CLASSES.md, VALIDATION-AND-REPORTING.md, CLIENT-SIDE.md, AI-AND-LLM.md, WEB-PROTOCOL-AND-AUTH.md, MEMORY-SAFETY-AND-BINARY.md)
- **When:** Security audits, vulnerability reviews, penetration testing code reviews, finding exploitable bugs.
- **Scope:** 6-phase methodology — Recon, Hunt, Validate, Report, Structured Output, Independent Verification. Focuses on exploitable vulnerabilities with real impact, not theoretical concerns.

### 5. `resolving-merge-conflicts`

- **Location:** `.agents/skills/resolving-merge-conflicts/SKILL.md`
- **When:** Resolving in-progress git merge/rebase conflicts.
- **Scope:** 5-step methodology — state analysis, root cause search, hunk resolution preserving intent, automated checks verification, merge completion.

### 6. `rag-blueprint`

- **Location:** `.agents/skills/rag-blueprint/SKILL.md`
- **When:** Building, deploying, configuring, or optimizing Retrieval-Augmented Generation (RAG), NeMo Guardrails, VLM, hybrid search, NV-Ingest, reranking, and LLM reasoning pipelines.
- **Scope:** NVIDIA RAG Blueprint operations — multimodal ingestion, NeMo guardrails, Agentic RAG, Qdrant/Neo4j hybrid search, Nemotron reranking, and observability.

## Rules

1. **Always invoke a relevant skill before acting.** If a skill applies to the task, use it — no exceptions.
2. **Read the full rule files** from the `rules/` directory when working on specific React patterns.
3. **Plan before code.** For design tasks, brainstorm a token system (color, type, layout, signature) before writing CSS/JSX.
4. **Critique your own work.** After implementing, review against the skill guidelines before presenting.

## Skill Priority (from using-superpowers)

When multiple skills apply, process skills come first — they set the approach, then implementation skills carry it out.

- **Multi-skill tasks:** process skill first → implementation skill next
- **User instructions** (this file) override skills, which override default behavior
- If you think there is even a 1% chance a skill applies, invoke it

## Project Context

- **Stack:** React + Vite (client-only SPA), TypeScript, Tailwind CSS, GSAP
- **Packages are deep modules** — see [frontend/src/packages/README.md](./frontend/src/packages/README.md) before adding or importing one.
- **Not Next.js** — skip server-side rules (RSC, `next/dynamic`, `next/script`, `after()`, server actions).
- **Most relevant rules:** Bundle size (barrel imports, dynamic imports), re-render optimization, JS perf, rendering perf.

## Agent skills

### Issue tracker

GitHub issues. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout. See `docs/agents/domain.md`.

## CI/CD Policy (MANDATORY)

All agents **MUST** adhere to the [**CI/CD Policy**](./CI-CD-POLICY.md) — 12
mandatory rules governing every code change:

| Rule | Summary | Critical For Agents |
|------|---------|---------------------|
| R1 | Root Cause First — never fix symptoms | ✅ Before any code change |
| R2 | CI/CD Ownership — every failure is an incident | ✅ When diagnosing CI |
| R3 | GitHub Actions Validation — validate ALL changes | ✅ Before workflow edits |
| R4 | Safe Push — local validation before any push | ✅ **Every commit** |
| R5 | Safe Merge — pipeline must be green | ✅ Before merging PRs |
| R6 | Failure Investigation — produce full report | ✅ When CI fails |
| R7 | Regression Prevention — evaluate all risks | ✅ After every fix |
| R8 | Git Safety — no force push, no history rewrite | ✅ **Absolute rule** |
| R9 | Dependency Safety — never blindly update | ✅ Before dep upgrades |
| R10 | Secure Deployment — verify everything | ✅ Before deploying |
| R11 | No Assumptions — always verify | ✅ **Always** |
| R12 | Completion Criteria — ALL checks must pass | ✅ Before declaring done |

## Deployment & Branching Policy (Strict Instructions)

1. **Feature Branching:** All modifications/fixes must be pushed to the remote via a separate, dedicated feature branch (do not commit directly to main).
2. **Safe Push & Test (per CI/CD Rule 4):** Perform a safe push of the feature branch after local validation.
3. **Merge Conflict & Issue Check:** Test the remote branch integration to verify if merging it with `main` will cause any issues, conflicts, or compilation errors. Solve any detected issues/conflicts first in the feature branch.
4. **Safe Merging (per CI/CD Rule 5):** Perform the merge to `main` only after full pipeline verification.
5. **Clean Up:** Delete the local/remote feature branch and clean up any temporary or cache files.
