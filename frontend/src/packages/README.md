# Packages — Deep Modules

Each package under `src/packages/<name>/` is a **deep module**: a lot of behaviour behind a small interface.

## Layout

```
src/packages/
  <name>/
    index.ts      ← entry point (public). Import this from outside.
    client.ts     ← another entry point (optional). Expose several small ones.
    lib/          ← implementation: hidden from outside, free to import each other.
    tests/        ← co-located tests + fixtures (a subfolder, so private).
```

- **Entry points** are the files at a package's root. They are the **only** files that code outside the package may import.
- **Subfolders** (`lib/`, `tests/`, or any other) are **private**. No code outside the package may import from them — not even another package's tests.
- Tests import only through **entry points**, just like production code.

## Rules (enforced by `lint:boundaries`)

1. **Entry-point boundary** — code outside a package (app code or another package) may import only that package's entry points (its root files), never anything in its subfolders.
2. **Intra-package freedom** — a package's own files import each other freely.
3. **Tests through the entry points** — files under `<pkg>/tests/` may import any package's entry points and their own `tests/` fixtures, but never any package's subfolder internals (not even their own).
4. **No cycles** — no dependency cycles between packages.

## Discourage barrel files

Do **not** create one giant `index.ts` that re-exports an entire subtree. Prefer exposing several small entry points (`index.ts`, `client.ts`, `server.ts`) instead. If a file is implementation detail, put it in a subfolder — it's automatically private.

## Running the check

```bash
npm run lint:boundaries
```

This runs as part of `npm run ci`.