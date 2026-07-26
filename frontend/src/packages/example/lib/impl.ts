/**
 * Internal implementation — PRIVATE.
 *
 * This file is in a subfolder (`lib/`), so it is NOT importable from outside
 * the package. Only the package's own entry points (root files) may import it.
 */

/**
 * Format a greeting string.
 *
 * @param name - The name to include in the greeting.
 * @returns A formatted greeting.
 */
export function formatGreeting(name: string): string {
  return `Hello, ${name}! Welcome to BAZSpark.`;
}