import * as React from "react";

const MOBILE_BREAKPOINT = 768;

export function useIsMobile() {
	// Lazy initializer so the initial render already has the correct value
	// (avoids react-hooks/set-state-in-effect: no setState needed on mount).
	const [isMobile, setIsMobile] = React.useState<boolean | undefined>(() => {
		if (typeof window === "undefined") return undefined;
		return window.innerWidth < MOBILE_BREAKPOINT;
	});

	React.useEffect(() => {
		const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
		const onChange = () => {
			setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
		};
		mql.addEventListener("change", onChange);
		// No setState on mount — initial state already correct from lazy initializer.
		return () => mql.removeEventListener("change", onChange);
	}, []);

	return !!isMobile;
}
