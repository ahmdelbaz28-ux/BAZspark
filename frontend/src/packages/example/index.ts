/**
 * Example deep module — entry point.
 *
 * This is a PUBLIC entry point. Other code imports this, not `lib/` internals.
 * The implementation lives in subfolders and is hidden from outside consumers.
 */

import { formatGreeting } from "./lib/impl";

/**
 * Greet a user by name.
 *
 * @param name - The name to greet.
 * @returns A formatted greeting string.
 */
export function greet(name: string): string {
  return formatGreeting(name);
}