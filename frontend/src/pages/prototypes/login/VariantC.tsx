/** @internal Design prototype — excluded from production via PrototypeSwitcher feature flag */

/**
 * VariantC.tsx — Dark Portal Login
 *
 * Refactored to use shared LoginVariantProps and shared sub-components.
 * Now includes the Remember Me checkbox (was missing before).
 * Error label i18n inconsistency fixed (was hardcoded "Authentication Error").
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef } from "react";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";
import {
	ApiKeyInputField,
	LanguageToggle,
	LoginErrorAlert,
	LoginSubmitButton,
	LoginSuccessView,
	RememberCheckbox,
	RequestAccessModal,
	SupportModal,
} from "./shared";
import type { LoginVariantProps } from "./types";

// ── Particle Canvas (unique to VariantC) ────────────────────────────────

/** CSPRNG float in [0, 1) using crypto.getRandomValues — satisfies SonarCloud typescript:S2245. */
function randomFloat(): number {
	const buf = new Uint32Array(1);
	crypto.getRandomValues(buf);
	return buf[0] / 0x100000000;
}

function ParticleCanvas() {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;

		let animId: number;
		const particles: {
			x: number;
			y: number;
			vx: number;
			vy: number;
			r: number;
			a: number;
		}[] = [];

		const resize = () => {
			canvas.width = window.innerWidth;
			canvas.height = window.innerHeight;
		};
		resize();
		window.addEventListener("resize", resize);

		for (let i = 0; i < 60; i++) {
			// NOSONAR: typescript:S2245 — crypto-backed randomFloat is used here, see helper above
			particles.push({
				x: randomFloat() * canvas.width,
				y: randomFloat() * canvas.height,
				vx: (randomFloat() - 0.5) * 0.3,
				vy: (randomFloat() - 0.5) * 0.3,
				r: randomFloat() * 1.5 + 0.5,
				a: randomFloat() * 0.4 + 0.1,
			});
		}

		const draw = () => {
			ctx.clearRect(0, 0, canvas.width, canvas.height);
			for (const p of particles) {
				p.x += p.vx;
				p.y += p.vy;
				if (p.x < 0) p.x = canvas.width;
				if (p.x > canvas.width) p.x = 0;
				if (p.y < 0) p.y = canvas.height;
				if (p.y > canvas.height) p.y = 0;
				ctx.beginPath();
				ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
				ctx.fillStyle = `rgba(56, 189, 248, ${p.a})`;
				ctx.fill();
			}
			for (let i = 0; i < particles.length; i++) {
				for (let j = i + 1; j < particles.length; j++) {
					const dx = particles[i].x - particles[j].x;
					const dy = particles[i].y - particles[j].y;
					const dist = Math.hypot(dx, dy);
					if (dist < 120) {
						ctx.beginPath();
						ctx.moveTo(particles[i].x, particles[i].y);
						ctx.lineTo(particles[j].x, particles[j].y);
						ctx.strokeStyle = `rgba(56, 189, 248, ${0.08 * (1 - dist / 120)})`;
						ctx.lineWidth = 0.5;
						ctx.stroke();
					}
				}
			}
			animId = requestAnimationFrame(draw);
		};
		draw();

		return () => {
			cancelAnimationFrame(animId);
			window.removeEventListener("resize", resize);
		};
	}, []);

	return (
		<canvas
			ref={canvasRef}
			style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
		/>
	);
}

// ── VariantC Component ──────────────────────────────────────────────────

export function VariantC(props: Readonly<LoginVariantProps>) {
	const {
		lang,
		t,
		apiKey,
		setApiKey,
		showKey,
		setShowKey,
		remember,
		setRemember,
		submitting,
		error,
		isSuccess,
		showSupportModal,
		setShowSupportModal,
		showRequestModal,
		setShowRequestModal,
		handleSubmit,
		handleAutoFillTestKey,
		toggleLanguage,
	} = props;

	return (
		<div
			dir={lang === "ar" ? "rtl" : "ltr"}
			style={{
				minHeight: "100vh",
				display: "flex",
				alignItems: "center",
				justifyContent: "center",
				backgroundColor: "#020409",
				position: "relative",
				overflow: "hidden",
			}}
		>
			<div
				style={{
					position: "absolute",
					inset: 0,
					background:
						"radial-gradient(ellipse 100% 60% at 50% 0%, rgba(6,78,112,0.15), transparent), radial-gradient(ellipse 80% 50% at 50% 100%, rgba(124,58,237,0.08), transparent)",
				}}
			/>
			<ParticleCanvas />

			<div
				style={{
					position: "absolute",
					top: "1.5rem",
					right: "2rem",
					zIndex: 10,
				}}
			>
				<LanguageToggle lang={lang} toggleLanguage={toggleLanguage} />
			</div>

			<motion.div
				initial={{ opacity: 0 }}
				animate={{ opacity: 1 }}
				transition={{ duration: 1 }}
				style={{
					width: "100%",
					maxWidth: "440px",
					padding: "1rem",
					position: "relative",
					zIndex: 1,
				}}
			>
				<motion.div
					initial={{ opacity: 0, y: 30 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ delay: 0.2, duration: 0.6 }}
					style={{ textAlign: "center", marginBottom: "2rem" }}
				>
					<motion.div
						initial={{ scale: 0.8 }}
						animate={{ scale: 1 }}
						transition={{ delay: 0.4, type: "spring", stiffness: 200 }}
					>
						<BazSparkLogo size={56} animated />
					</motion.div>
					<h1
						style={{
							fontSize: "1.75rem",
							fontWeight: 900,
							color: "#ffffff",
							marginTop: "1rem",
							letterSpacing: "-0.02em",
						}}
					>
						BAZSPARK
					</h1>
					<p
						style={{
							fontSize: "0.7rem",
							color: "#94a3b8",
							fontFamily: "monospace",
							letterSpacing: "0.15em",
							marginTop: "0.25rem",
							textTransform: "uppercase",
						}}
					>
						{t.topBadge}
					</p>
				</motion.div>

				<motion.div
					initial={{ opacity: 0, y: 30 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ delay: 0.5, duration: 0.6 }}
				>
					<div
						style={{
							backgroundColor: "rgba(10,14,26,0.6)",
							border: "1px solid rgba(56,189,248,0.1)",
							borderRadius: "1rem",
							padding: "2rem",
							backdropFilter: "blur(16px)",
							boxShadow: "0 32px 64px rgba(0,0,0,0.5)",
						}}
					>
						<AnimatePresence mode="wait">
							{!isSuccess ? (
								<motion.div
									key="form"
									initial={{ opacity: 1 }}
									exit={{ opacity: 0, y: -10 }}
								>
									<form onSubmit={handleSubmit}>
										<div
											style={{
												display: "flex",
												alignItems: "center",
												gap: "0.75rem",
												marginBottom: "1.5rem",
											}}
										>
											<div
												style={{
													width: "0.25rem",
													height: "1.5rem",
													borderRadius: "9999px",
													background:
														"linear-gradient(180deg, #38bdf8, #7c3aed)",
												}}
											/>
											<div>
												<div
													style={{
														fontSize: "0.65rem",
														fontWeight: 600,
														color: "#94a3b8",
														textTransform: "uppercase",
														letterSpacing: "0.08em",
													}}
												>
													{t.formTitle}
												</div>
												<div
													style={{
														fontSize: "0.7rem",
														color: "#94a3b8",
														marginTop: "0.1rem",
													}}
												>
													{t.formSubtitle}
												</div>
											</div>
										</div>

										<LoginErrorAlert lang={lang} error={error} />
										<ApiKeyInputField
											t={t}
											apiKey={apiKey}
											setApiKey={setApiKey}
											showKey={showKey}
											setShowKey={setShowKey}
											submitting={submitting}
										/>
										<p
											style={{
												fontSize: "0.6rem",
												color: "#475569",
												marginBottom: "0.75rem",
											}}
										>
											{t.inputHint}
										</p>
										<RememberCheckbox
											t={t}
											remember={remember}
											setRemember={setRemember}
											submitting={submitting}
										/>
										<LoginSubmitButton
											t={t}
											submitting={submitting}
											disabled={submitting || !apiKey.trim()}
										/>

										<div
											style={{
												display: "flex",
												gap: "0.5rem",
												marginTop: "1rem",
											}}
										>
											<button
												type="button"
												onClick={() => setShowSupportModal(true)}
												style={{
													flex: 1,
													background: "none",
													border: "1px solid rgba(255,255,255,0.08)",
													borderRadius: "0.5rem",
													padding: "0.4rem",
													fontSize: "0.6rem",
													fontWeight: 600,
													color: "#38bdf8",
													cursor: "pointer",
													transition: "background 0.2s",
												}}
											>
												{t.supportLink}
											</button>
											<button
												type="button"
												onClick={() => setShowRequestModal(true)}
												style={{
													flex: 1,
													background: "none",
													border: "1px solid rgba(255,255,255,0.08)",
													borderRadius: "0.5rem",
													padding: "0.4rem",
													fontSize: "0.6rem",
													fontWeight: 600,
													color: "#f87171",
													cursor: "pointer",
													transition: "background 0.2s",
												}}
											>
												{t.requestAccessLink}
											</button>
										</div>
									</form>
								</motion.div>
							) : (
								<LoginSuccessView t={t} />
							)}
						</AnimatePresence>
					</div>
				</motion.div>

				<div
					style={{
						textAlign: "center",
						marginTop: "1.5rem",
						fontSize: "0.6rem",
						fontFamily: "monospace",
						color: "#475569",
					}}
				>
					AES-256 Encryption · System v8.1 · All connections secure
				</div>
			</motion.div>

			<SupportModal
				t={t}
				showSupportModal={showSupportModal}
				setShowSupportModal={setShowSupportModal}
			/>
			<RequestAccessModal
				t={t}
				showRequestModal={showRequestModal}
				setShowRequestModal={setShowRequestModal}
				handleAutoFillTestKey={handleAutoFillTestKey}
			/>
		</div>
	);
}
