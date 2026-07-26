/**
 * Example deep module test — imports ONLY through the entry point.
 *
 * Tests exercise the package through its public API, not internal implementation.
 * This file imports `../index` (the entry point), never `../lib/impl`.
 */

import { describe, it, expect } from "vitest";
import { greet } from "../index";

describe("example package", () => {
  it("should greet a user", () => {
    const result = greet("World");
    expect(result).toBe("Hello, World! Welcome to BAZSpark.");
  });
});