import "framer-motion";

declare module "framer-motion" {
	interface MotionProps {
		initial?: unknown;
		animate?: unknown;
		exit?: unknown;
		transition?: unknown;
		variants?: unknown;
		whileHover?: unknown;
		whileTap?: unknown;
		whileFocus?: unknown;
		whileInView?: unknown;
		whileDrag?: unknown;
		onAnimationComplete?: unknown;
		layout?: unknown;
		layoutId?: string;
	}
}
