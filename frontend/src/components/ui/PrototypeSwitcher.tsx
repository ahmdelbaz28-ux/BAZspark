import { useCallback, useEffect } from "react";
import { useSearchParams } from "react-router";

interface PrototypeSwitcherProps {
	readonly variants: readonly {
		readonly key: string;
		readonly label: string;
	}[];
}

export function PrototypeSwitcher({ variants }: PrototypeSwitcherProps) {
	const [searchParams, setSearchParams] = useSearchParams();
	const current = searchParams.get("variant") ?? variants[0]?.key ?? "A";

	const goTo = useCallback(
		(key: string) => {
			const next = new URLSearchParams(searchParams);
			next.set("variant", key);
			setSearchParams(next, { replace: true });
		},
		[searchParams, setSearchParams],
	);

	const prev = () => {
		const idx = variants.findIndex((v) => v.key === current);
		goTo(variants[(idx - 1 + variants.length) % variants.length].key);
	};

	const next = () => {
		const idx = variants.findIndex((v) => v.key === current);
		goTo(variants[(idx + 1) % variants.length].key);
	};

	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			const target = e.target as HTMLElement;
			if (
				target.tagName === "INPUT" ||
				target.tagName === "TEXTAREA" ||
				target.isContentEditable
			)
				return;
			if (e.key === "ArrowLeft") {
				e.preventDefault();
				prev();
			}
			if (e.key === "ArrowRight") {
				e.preventDefault();
				next();
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	});

	if (import.meta.env.PROD) return null;

	const label = variants.find((v) => v.key === current)?.label ?? current;

	return (
		<div
			style={{
				position: "fixed",
				bottom: "1rem",
				left: "50%",
				transform: "translateX(-50%)",
				zIndex: 9999,
				display: "flex",
				alignItems: "center",
				gap: "0.75rem",
				padding: "0.5rem 1rem",
				borderRadius: "9999px",
				backgroundColor: "rgba(12, 17, 32, 0.95)",
				border: "1px solid rgba(56, 189, 248, 0.3)",
				boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
				fontSize: "0.75rem",
				fontFamily: "monospace",
				backdropFilter: "blur(8px)",
				userSelect: "none",
			}}
		>
			<button
				type="button"
				onClick={prev}
				style={{
					background: "none",
					border: "none",
					color: "#38bdf8",
					cursor: "pointer",
					padding: "0.25rem 0.5rem",
					fontWeight: 700,
					fontSize: "0.875rem",
				}}
				aria-label="Previous variant"
			>
				◀
			</button>
			<span style={{ color: "#94a3b8" }}>
				<span style={{ color: "#38bdf8", fontWeight: 700 }}>{current}</span>
				{" — "}
				<span style={{ color: "#cbd5e1" }}>{label}</span>
			</span>
			<button
				type="button"
				onClick={next}
				style={{
					background: "none",
					border: "none",
					color: "#38bdf8",
					cursor: "pointer",
					padding: "0.25rem 0.5rem",
					fontWeight: 700,
					fontSize: "0.875rem",
				}}
				aria-label="Next variant"
			>
				▶
			</button>
			<span style={{ color: "#475569", fontSize: "0.65rem" }}>← →</span>
		</div>
	);
}
