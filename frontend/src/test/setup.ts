import "@testing-library/jest-dom";
import { cleanup } from "@testing-library/react";

// V302 FIX: Use the GLOBAL afterEach (injected by vitest's `globals: true` config)
// instead of importing it from "vitest". In Vitest 4.x, the imported afterEach
// requires an active suite context and throws "Vitest failed to find the current
// suite" when called in a setup file. The global version works correctly here.
// TypeScript recognizes the global because tsconfig.json includes "vitest/globals"
// in its `types` array.
afterEach(() => {
	cleanup();
});
