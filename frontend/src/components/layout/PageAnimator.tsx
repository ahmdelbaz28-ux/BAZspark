import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useRef } from "react";
import { useLocation } from "react-router";

interface PageAnimatorProps {
	children: React.ReactNode;
}

/**
 * PageAnimator wraps the main content area and triggers a GSAP stagger animation
 * on any child element with the `.stagger-card` class whenever the route changes.
 * This provides a smooth, consistent entry motion across all 66 pages without
 * having to manually wire up GSAP in each component.
 */
export const PageAnimator: React.FC<PageAnimatorProps> = ({ children }) => {
	const location = useLocation();
	const containerRef = useRef<HTMLDivElement>(null);

	useGSAP(
		() => {
			// Reset state and animate in
			gsap.fromTo(
				".stagger-card",
				{ y: 20, opacity: 0 },
				{ y: 0, opacity: 1, duration: 0.4, stagger: 0.05, ease: "power2.out" },
			);
		},
		{ dependencies: [location.pathname], scope: containerRef },
	);

	return (
		<div ref={containerRef} className="h-full w-full">
			{children}
		</div>
	);
};
