/**
 * useReducedMotion — React hook that checks the user's
 * `prefers-reduced-motion` OS accessibility setting.
 *
 * Returns `true` when the user has requested reduced motion,
 * `false` otherwise. Updates reactively when the setting changes
 * (e.g., user toggles it in system preferences while the app is open).
 *
 * Usage:
 * ```tsx
 * const reducedMotion = useReducedMotion();
 * // Use in JSX:
 * <div className={reducedMotion ? 'static' : 'animate-float'} />
 * ```
 *
 * The hook uses `window.matchMedia` internally and is SSR-safe
 * (returns `false` when `window` is not available).
 *
 * @returns {boolean} `true` if the user prefers reduced motion.
 */

import { useCallback, useEffect, useState } from "react";

function getPrefersReducedMotion(): boolean {
	if (typeof window === "undefined") return false;
	return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function useReducedMotion(): boolean {
	const [prefersReducedMotion, setPrefersReducedMotion] = useState(
		getPrefersReducedMotion,
	);

	const handleChange = useCallback(() => {
		setPrefersReducedMotion(getPrefersReducedMotion());
	}, []);

	useEffect(() => {
		const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
		// Modern browsers support addEventListener on MediaQueryList
		mq.addEventListener("change", handleChange);
		return () => mq.removeEventListener("change", handleChange);
	}, [handleChange]);

	return prefersReducedMotion;
}
