/**
 * LoginPage.tsx — BAZSPARK Login (Redesigned with Premium Spacing, Typography & HUD)
 *
 * Design Concept:
 *   - 50/50 Split layout (Left: Product Showcase and Brand Details; Right: System Access Sign-In Card)
 *   - Premium Spacing & Typography: Clean margins, line-heights, letter-spacing and breathing room.
 *   - BrandNetworkBackground: Canvas rendering floating sensor nodes (connections) and rising sparks (particles)
 *   - BrandSafetyHUD: Visual CAD loop routing simulation with isometric sweeps and a scrolling diagnostic ticker
 *   - Glowing Metrics Grid: Key marketing data points (80% Time Saved, 100% Compliant, Zero Collisions)
 *   - Dynamic 3D perspective grid animation in the background scrolling forward
 *   - Coral-red flame branding and solid coral-red submit button
 *   - Fully functional with original API authentication, key visibility toggle, and remember-me state
 *   - Staggered entrance animations using framer-motion
 *   - Floating Label Authorization Input (Material Design style)
 *   - Dynamic Key Strength Indicator
 *   - Animated Success Transition overlay before redirection
 */

import {
	AlertCircle,
	Brain,
	Compass,
	Eye,
	EyeOff,
	KeyRound,
	Loader2,
	Settings,
	ShieldCheck,
} from "lucide-react";
import { useState, useEffect, useRef, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { BazSparkLogo, BazSparkWordmark } from "@/components/auth/BazSparkLogo";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { motion, AnimatePresence } from "framer-motion";

/**
 * BrandNetworkBackground — Chaotic Particle System
 *
 * Renders a chaotic canvas of:
 * - Morphing node shapes (circle ↔ triangle ↔ square ↔ hexagon)
 * - Falling data stream characters (Matrix-style code rain)
 * - Motion trails behind active particles
 * - HSL color cycling across the full spectrum over time
 */
function BrandNetworkBackground() {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;

		let animationFrameId: number;
		let width = (canvas.width = window.innerWidth);
		let height = (canvas.height = window.innerHeight);

		const handleResize = () => {
			if (!canvas) return;
			width = canvas.width = window.innerWidth;
			height = canvas.height = window.innerHeight;
		};
		window.addEventListener("resize", handleResize);

		// ─── Global time for color cycling ────────────────────────────
		let globalTime = 0;

		// ─── Shape types ──────────────────────────────────────────────
		type ShapeType = "circle" | "triangle" | "square" | "hexagon";
		const SHAPE_ORDER: ShapeType[] = ["circle", "triangle", "square", "hexagon"];

		// ─── Draw a polygon by number of sides ────────────────────────
		function drawPolygon(
			ctx: CanvasRenderingContext2D,
			cx: number,
			cy: number,
			radius: number,
			sides: number,
			rotation = 0,
		) {
			if (sides < 3) {
				ctx.arc(cx, cy, radius, 0, Math.PI * 2);
				return;
			}
			ctx.moveTo(
				cx + radius * Math.cos(rotation),
				cy + radius * Math.sin(rotation),
			);
			for (let i = 1; i <= sides; i++) {
				const angle = rotation + (i * Math.PI * 2) / sides;
				ctx.lineTo(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle));
			}
			ctx.closePath();
		}

		// ─── Shape → side count with interpolation ───────────────────
		function getSidesForShape(shape: ShapeType): number {
			switch (shape) {
				case "circle":
					return 0; // arc
				case "triangle":
					return 3;
				case "square":
					return 4;
				case "hexagon":
					return 6;
			}
		}

		// ─── Draw morphed shape between two shapes ────────────────────
		function drawMorphedShape(
			ctx: CanvasRenderingContext2D,
			cx: number,
			cy: number,
			radius: number,
			morphProgress: number,
			shapeA: ShapeType,
			shapeB: ShapeType,
			rotation: number,
		) {
			// Interpolate side count
			const sidesA = getSidesForShape(shapeA);
			const sidesB = getSidesForShape(shapeB);
			let sides = sidesA + (sidesB - sidesA) * morphProgress;

			// Build vertices (interpolated)
			if (sides < 3) {
				// Treat as circle (arc)
				ctx.beginPath();
				ctx.arc(cx, cy, radius, 0, Math.PI * 2);
				ctx.fill();
				if (radius > 2) {
					ctx.stroke();
				}
				return;
			}

			const integerSides = Math.round(sides);
			// For fractional morph between shapes with same side count, interpolate radii
			ctx.beginPath();
			const vertexAngleStart = rotation;
			ctx.moveTo(
				cx + radius * Math.cos(vertexAngleStart),
				cy + radius * Math.sin(vertexAngleStart),
			);
			for (let i = 1; i <= integerSides; i++) {
				const angle = vertexAngleStart + (i * Math.PI * 2) / integerSides;
				ctx.lineTo(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle));
			}
			ctx.closePath();
			ctx.fill();
			if (radius > 2) {
				ctx.stroke();
			}
		}

		// ─── Morphed particle ─────────────────────────────────────────
		interface MorphedNode {
			x: number;
			y: number;
			vx: number;
			vy: number;
			radius: number;
			shapeA: ShapeType;
			shapeB: ShapeType;
			morphProgress: number; // 0-1
			morphSpeed: number;
			rotation: number;
			rotationSpeed: number;
			// Trail history
			trail: { x: number; y: number }[];
			// HSL hue offset for this particle
			hueOffset: number;
		}

		// ─── Data stream droplet ──────────────────────────────────────
		interface DataStream {
			x: number;
			y: number;
			speed: number;
			chars: string[];
			length: number;
			opacity: number;
			hue: number;
		}

		// ─── Glitch burst ─────────────────────────────────────────────
		interface GlitchBurst {
			x: number;
			y: number;
			life: number;
			maxLife: number;
			segments: { dx: number; dy: number; w: number; h: number; alpha: number }[];
		}

		// ─── Node count ───────────────────────────────────────────────
		const nodesCount = Math.min(40, Math.floor((width * height) / 35000));
		const nodes: MorphedNode[] = [];
		for (let i = 0; i < nodesCount; i++) {
			const r = Math.random() * 3.5 + 1.5;
			nodes.push({
				x: Math.random() * width,
				y: Math.random() * height,
				vx: (Math.random() - 0.5) * 0.6,
				vy: (Math.random() - 0.5) * 0.6,
				radius: r,
				shapeA: SHAPE_ORDER[Math.floor(Math.random() * SHAPE_ORDER.length)],
				shapeB: SHAPE_ORDER[Math.floor(Math.random() * SHAPE_ORDER.length)],
				morphProgress: Math.random(),
				morphSpeed: 0.003 + Math.random() * 0.012,
				rotation: Math.random() * Math.PI * 2,
				rotationSpeed: (Math.random() - 0.5) * 0.02,
				trail: [],
				hueOffset: Math.random() * 360,
			});
		}

		// ─── Data streams ─────────────────────────────────────────────
		const streamCount = Math.min(12, Math.floor((width * height) / 80000));
		const streams: DataStream[] = [];
		const STREAM_CHARS = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン";
		for (let i = 0; i < streamCount; i++) {
			const len = 4 + Math.floor(Math.random() * 10);
			const chars: string[] = [];
			for (let j = 0; j < len; j++) {
				chars.push(STREAM_CHARS[Math.floor(Math.random() * STREAM_CHARS.length)]);
			}
			streams.push({
				x: Math.random() * width,
				y: Math.random() * -height,
				speed: 1.5 + Math.random() * 4,
				chars,
				length: len,
				opacity: 0.08 + Math.random() * 0.2,
				hue: Math.random() * 360,
			});
		}

		// ─── Glitch bursts ────────────────────────────────────────────
		const glitches: GlitchBurst[] = [];

		function spawnGlitch() {
			const numSegments = 3 + Math.floor(Math.random() * 6);
			const segments = [];
			const gx = Math.random() * width;
			const gy = Math.random() * height;
			for (let i = 0; i < numSegments; i++) {
				segments.push({
					dx: (Math.random() - 0.5) * 60,
					dy: (Math.random() - 0.5) * 8,
					w: 4 + Math.random() * 30,
					h: 2 + Math.random() * 4,
					alpha: 0.4 + Math.random() * 0.6,
				});
			}
			glitches.push({ x: gx, y: gy, life: 0, maxLife: 6 + Math.random() * 10, segments });
		}

		let glitchTimer = 0;

		// ─── Anim loop ────────────────────────────────────────────────
		const animate = () => {
			globalTime += 0.005;
			const hueBase = (globalTime * 60) % 360; // Slowly cycle hue

			// Semi-transparent clear for motion trails (fade effect)
			ctx.fillStyle = "rgba(5, 7, 15, 0.18)";
			ctx.fillRect(0, 0, width, height);

			// ═══════════ 1. DATA STREAMS ═══════════
			ctx.font = "10px monospace";
			for (const stream of streams) {
				stream.y += stream.speed;
				if (stream.y > height + 20) {
					stream.y = -stream.length * 14;
					stream.x = Math.random() * width;
					stream.hue = (stream.hue + 30 + Math.random() * 60) % 360;
					// Refresh chars
					for (let j = 0; j < stream.length; j++) {
						stream.chars[j] = STREAM_CHARS[Math.floor(Math.random() * STREAM_CHARS.length)];
					}
				}

				for (let j = 0; j < stream.length; j++) {
					const charY = stream.y - j * 12;
					if (charY < -10 || charY > height + 10) continue;

					// Lead character is brightest (cyan/green), rest fade
					const fade = 1 - j / stream.length;
					const charOpacity = stream.opacity * fade * 0.7;
					if (charOpacity < 0.01) continue;

					// Lead char in bright cyan, trail chars in stream hue
					if (j === 0) {
						ctx.fillStyle = `hsla(${(stream.hue + 180) % 360}, 100%, 70%, ${stream.opacity * 0.9})`;
					} else if (j === 1) {
						ctx.fillStyle = `hsla(${stream.hue}, 80%, 50%, ${charOpacity * 1.2})`;
					} else {
						ctx.fillStyle = `hsla(${stream.hue}, 60%, 40%, ${charOpacity})`;
					}
					ctx.fillText(stream.chars[j], stream.x, charY);
				}
			}

			// ═══════════ 2. MORPHED NODES + TRAILS + CONNECTIONS ═══════════
			for (let i = 0; i < nodes.length; i++) {
				const n = nodes[i];

				// Update position
				n.x += n.vx;
				n.y += n.vy;

				if (n.x < -20 || n.x > width + 20) n.vx *= -1;
				if (n.y < -20 || n.y > height + 20) n.vy *= -1;

				// Clamp
				n.x = Math.max(-20, Math.min(width + 20, n.x));
				n.y = Math.max(-20, Math.min(height + 20, n.y));

				// Update rotation
				n.rotation += n.rotationSpeed;

				// Update morph progress
				n.morphProgress += n.morphSpeed;
				if (n.morphProgress >= 1) {
					n.morphProgress = 0;
					n.shapeA = n.shapeB;
					n.shapeB = SHAPE_ORDER[Math.floor(Math.random() * SHAPE_ORDER.length)];
					// Ensure different from shapeA
					if (n.shapeB === n.shapeA) {
						n.shapeB = SHAPE_ORDER[(SHAPE_ORDER.indexOf(n.shapeA) + 1 + Math.floor(Math.random() * 2)) % SHAPE_ORDER.length];
					}
				}

				// Record trail (max 12 points)
				n.trail.push({ x: n.x, y: n.y });
				if (n.trail.length > 12) n.trail.shift();

				// Draw trail (fading tail behind each particle)
				if (n.trail.length > 1) {
					for (let t = 1; t < n.trail.length; t++) {
						const trailFade = t / n.trail.length;
						const trailAlpha = trailFade * 0.15;
						ctx.strokeStyle = `hsla(${(hueBase + n.hueOffset) % 360}, 80%, 55%, ${trailAlpha})`;
						ctx.lineWidth = n.radius * 0.5 * trailFade;
						ctx.beginPath();
						ctx.moveTo(n.trail[t - 1].x, n.trail[t - 1].y);
						ctx.lineTo(n.trail[t].x, n.trail[t].y);
						ctx.stroke();
					}
				}

				// Draw connections between nearby nodes (with hue cycling)
				for (let j = i + 1; j < nodes.length; j++) {
					const n2 = nodes[j];
					const dx = n.x - n2.x;
					const dy = n.y - n2.y;
					const dist = Math.sqrt(dx * dx + dy * dy);
					if (dist < 160) {
						const fade = 1 - dist / 160;
						const connHue = (hueBase + n.hueOffset * 0.5 + n2.hueOffset * 0.5) % 360;
						ctx.strokeStyle = `hsla(${connHue}, 80%, 60%, ${fade * 0.08})`;
						ctx.lineWidth = 0.6 + fade * 0.6;
						ctx.beginPath();
						ctx.moveTo(n.x, n.y);
						ctx.lineTo(n2.x, n2.y);
						ctx.stroke();
					}
				}

				// Draw the morphed node
				const hue = (hueBase + n.hueOffset) % 360;
				ctx.fillStyle = `hsla(${hue}, 90%, 60%, 0.35)`;
				ctx.strokeStyle = `hsla(${hue}, 90%, 70%, 0.5)`;
				ctx.lineWidth = 0.8;

				drawMorphedShape(
					ctx,
					n.x,
					n.y,
					n.radius,
					n.morphProgress,
					n.shapeA,
					n.shapeB,
					n.rotation,
				);

				// Glow aura for larger particles
				if (n.radius > 2.5) {
					const outerGlow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.radius * 4);
					outerGlow.addColorStop(0, `hsla(${hue}, 90%, 60%, 0.08)`);
					outerGlow.addColorStop(1, `hsla(${hue}, 90%, 60%, 0)`);
					ctx.fillStyle = outerGlow;
					ctx.beginPath();
					ctx.arc(n.x, n.y, n.radius * 4, 0, Math.PI * 2);
					ctx.fill();
				}
			}

			// ═══════════ 3. GLITCH BURSTS ═══════════
			glitchTimer++;
			if (glitchTimer > 60 + Math.random() * 120) {
				glitchTimer = 0;
				spawnGlitch();
			}

			for (let i = glitches.length - 1; i >= 0; i--) {
				const g = glitches[i];
				g.life++;
				if (g.life >= g.maxLife) {
					glitches.splice(i, 1);
					continue;
				}
				const lifeRatio = g.life / g.maxLife;
				const alpha = 1 - lifeRatio;

				for (const seg of g.segments) {
					// Glitch rect
					ctx.fillStyle = `hsla(${(hueBase + 180) % 360}, 100%, 60%, ${seg.alpha * alpha * 0.15})`;
					ctx.fillRect(g.x + seg.dx, g.y + seg.dy, seg.w, seg.h);

					// Secondary displaced copy
					ctx.fillStyle = `hsla(${(hueBase + 240) % 360}, 100%, 50%, ${seg.alpha * alpha * 0.08})`;
					ctx.fillRect(g.x + seg.dx + 4, g.y + seg.dy, seg.w, seg.h);
				}
			}

			animationFrameId = requestAnimationFrame(animate);
		};

		animate();

		return () => {
			window.removeEventListener("resize", handleResize);
			cancelAnimationFrame(animationFrameId);
		};
	}, []);

	return (
		<canvas
			ref={canvasRef}
			className="absolute inset-0 w-full h-full pointer-events-none z-[1]"
			style={{ mixBlendMode: "screen" }}
		/>
	);
}

/**
 * BrandSafetyHUD renders an isometric layout previewing 3D CAD loops,
 * blinking sensors, expanding scanner rings, and scrolling diagnostics.
 */
function BrandSafetyHUD() {
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const [logs, setLogs] = useState<string[]>([
		"[09:47:31] SYSTEM ACCESS INITIATED...",
		"[09:47:32] COUPLING WITH BAZSPARK REVIT BRIDGE...",
		"[09:47:33] ACTIVE: 48 NODE LOOP SENSORS DETECTED",
	]);

	useEffect(() => {
		const tickerPresets = [
			"NFPA 72 SEC 17.6 COMPLIANCE CHECK: PASSED",
			"SOLAS CRITERIA II-2/13 EVACUATION: COMPLIANT",
			"AI TOPOLOGY ROUTER: CALCULATING OPTIMAL LOOP A...",
			"loop resistance: 18.4 OHMS (SECURE BOUNDS)",
			"FACP LINK STATE: READY (1000 MBPS SSL)",
			"3D COLLISION CHECK: ZERO TRAYS OVERLAPPED",
			"audibility levels: > 75dBA AT 10FT (COMPLIANT)",
			"predictive temperature sensor index: NORMAL",
			"BIM METADATA: SYNCHRONIZED WITH HOST DB",
			"SYSTEM INTEGRITY STABILITY: 99.999% OPERATION",
		];

		let presetIdx = 0;
		const timer = setInterval(() => {
			setLogs((prev) => {
				const nextLog = `[${new Date().toLocaleTimeString()}] ${tickerPresets[presetIdx]}`;
				presetIdx = (presetIdx + 1) % tickerPresets.length;
				return [...prev.slice(-3), nextLog];
			});
		}, 1800);

		return () => clearInterval(timer);
	}, []);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;

		let animationFrameId: number;
		let width = (canvas.width = canvas.parentElement?.clientWidth || 400);
		let height = 180;
		canvas.height = height;

		const handleResize = () => {
			if (!canvas) return;
			width = canvas.width = canvas.parentElement?.clientWidth || 400;
			canvas.height = height;
		};
		window.addEventListener("resize", handleResize);

		const facp = { x: width / 2, y: height / 2, r: 5.5, color: "#f43f5e" };

		interface HudNode {
			x: number;
			y: number;
			r: number;
			status: "normal" | "blink";
			label: string;
			pulse: number;
		}

		const sensors: HudNode[] = [
			{ x: width * 0.18, y: height * 0.35, r: 2.5, status: "normal", label: "SD-01", pulse: 0 },
			{ x: width * 0.33, y: height * 0.22, r: 2.5, status: "blink", label: "HD-02", pulse: 0 },
			{ x: width * 0.16, y: height * 0.72, r: 2.5, status: "normal", label: "SD-03", pulse: 0 },
			{ x: width * 0.44, y: height * 0.78, r: 2.5, status: "blink", label: "MCP-04", pulse: 0 },
			{ x: width * 0.82, y: height * 0.32, r: 2.5, status: "normal", label: "SD-05", pulse: 0 },
			{ x: width * 0.64, y: height * 0.18, r: 2.5, status: "blink", label: "HD-06", pulse: 0 },
			{ x: width * 0.84, y: height * 0.74, r: 2.5, status: "normal", label: "SD-07", pulse: 0 },
			{ x: width * 0.68, y: height * 0.68, r: 2.5, status: "normal", label: "SD-08", pulse: 0 },
		];

		let radarAngle = 0;
		let pathProgress = 0;

		const animate = () => {
			ctx.clearRect(0, 0, width, height);

			// 1. Draw isometric grid lines
			ctx.strokeStyle = "rgba(148, 163, 184, 0.04)";
			ctx.lineWidth = 0.8;
			const gridSpacing = 22;

			for (let i = -width; i < width + height; i += gridSpacing) {
				ctx.beginPath();
				ctx.moveTo(i, 0);
				ctx.lineTo(i - height, height);
				ctx.stroke();

				ctx.beginPath();
				ctx.moveTo(i, 0);
				ctx.lineTo(i + height, height);
				ctx.stroke();
			}

			// 2. Draw radar wave sweep from center FACP
			radarAngle += 0.012;
			const radarMaxRadius = Math.max(width, height) * 0.6;
			const radarRadius = (radarAngle * 55) % radarMaxRadius;

			ctx.strokeStyle = `rgba(244, 63, 94, ${Math.max(0, 1 - radarRadius / radarMaxRadius) * 0.12})`;
			ctx.lineWidth = 1.2;
			ctx.beginPath();
			ctx.arc(facp.x, facp.y, radarRadius, 0, Math.PI * 2);
			ctx.stroke();

			// 3. Draw automated routing paths (cabling loop)
			pathProgress += 0.004;
			if (pathProgress > 1) pathProgress = 0;

			const loopPath = [facp, sensors[0], sensors[2], sensors[3], sensors[7], sensors[6], sensors[4], sensors[5], sensors[1], facp];
			
			ctx.beginPath();
			ctx.strokeStyle = "rgba(6, 182, 212, 0.28)"; // Glowing Cyan routing loop
			ctx.lineWidth = 1.5;
			ctx.moveTo(loopPath[0].x, loopPath[0].y);

			const currentSegmentCount = Math.floor(pathProgress * loopPath.length);
			const segmentRemainder = (pathProgress * loopPath.length) % 1;

			for (let i = 1; i <= currentSegmentCount; i++) {
				const idx = i % loopPath.length;
				ctx.lineTo(loopPath[idx].x, loopPath[idx].y);
			}

			if (currentSegmentCount < loopPath.length) {
				const lastNode = loopPath[currentSegmentCount % loopPath.length];
				const nextNode = loopPath[(currentSegmentCount + 1) % loopPath.length];
				const dx = nextNode.x - lastNode.x;
				const dy = nextNode.y - lastNode.y;
				ctx.lineTo(lastNode.x + dx * segmentRemainder, lastNode.y + dy * segmentRemainder);
			}
			ctx.stroke();

			// Draw backup redundant path in violet
			ctx.beginPath();
			ctx.strokeStyle = "rgba(168, 85, 247, 0.08)";
			ctx.lineWidth = 1;
			ctx.moveTo(facp.x, facp.y);
			sensors.forEach((s) => ctx.lineTo(s.x, s.y));
			ctx.closePath();
			ctx.stroke();

			// 4. Draw safety nodes
			sensors.forEach((s) => {
				s.pulse += 0.04;
				
				if (s.status === "blink" && Math.sin(s.pulse) > 0.4) {
					ctx.fillStyle = "rgba(244, 63, 94, 0.35)";
					ctx.beginPath();
					ctx.arc(s.x, s.y, s.r * 2.3, 0, Math.PI * 2);
					ctx.fill();

					ctx.fillStyle = "rgba(244, 63, 94, 0.95)";
				} else {
					ctx.fillStyle = "rgba(6, 182, 212, 0.75)";
				}

				ctx.beginPath();
				ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
				ctx.fill();

				ctx.fillStyle = "rgba(148, 163, 184, 0.55)";
				ctx.font = "8px monospace";
				ctx.fillText(s.label, s.x + 5, s.y + 3);
			});

			// 5. Draw FACP main node
			ctx.shadowColor = "#f43f5e";
			ctx.shadowBlur = 8;
			ctx.fillStyle = facp.color;
			ctx.beginPath();
			ctx.arc(facp.x, facp.y, facp.r, 0, Math.PI * 2);
			ctx.fill();

			ctx.shadowBlur = 0;
			ctx.fillStyle = "#ffffff";
			ctx.font = "bold 8.5px monospace";
			ctx.fillText("FACP-MAIN", facp.x - 24, facp.y - 9);

			animationFrameId = requestAnimationFrame(animate);
		};

		animate();

		return () => {
			window.removeEventListener("resize", handleResize);
			cancelAnimationFrame(animationFrameId);
		};
	}, []);

	return (
		<div className="w-full rounded-xl border border-slate-800/80 bg-slate-950/70 p-3.5 space-y-3.5 shadow-2xl relative overflow-hidden group hover:border-cyan-500/20 transition-all duration-300">
			<div className="absolute top-0 right-0 w-24 h-24 bg-cyan-500/5 rounded-full blur-2xl pointer-events-none group-hover:bg-cyan-500/10 transition-all" />
			
			{/* HUD Header */}
			<div className="flex justify-between items-center text-[9px] border-b border-slate-900 pb-2">
				<span className="font-mono text-cyan-400 font-bold tracking-widest flex items-center gap-1.5 animate-pulse">
					<span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
					CAD ROUTING COMPLIANCE SCANNER
				</span>
				<span className="font-mono text-slate-500">
					LOC_REF: RX-720
				</span>
			</div>

			{/* Canvas Blueprint */}
			<div className="w-full h-[180px] rounded bg-slate-950/90 border border-slate-900/60 relative overflow-hidden flex items-center justify-center">
				<canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
				<div className="absolute inset-0 bg-gradient-to-b from-transparent via-cyan-500/2 to-transparent h-1/4 w-full top-0 left-0 pointer-events-none" style={{
					animation: "scanline 6s linear infinite"
				}} />
				
				<style>{`
					@keyframes scanline {
						0% { top: -25%; }
						100% { top: 100%; }
					}
				`}</style>
			</div>

			{/* Terminal Output */}
			<div className="w-full rounded bg-[#030712] border border-slate-900 p-2.5 min-h-[70px] font-mono text-[9px] text-emerald-500/90 leading-normal flex flex-col justify-end overflow-hidden shadow-inner relative">
				<div className="absolute top-0.5 right-1 text-[7.5px] text-slate-600 tracking-widest font-bold">
					DIAGNOSTIC PORT
				</div>
				<div className="space-y-0.5">
					{logs.map((log, index) => (
						<div key={index} className="flex gap-1 items-start">
							<span className="text-slate-600 select-none shrink-0">&gt;</span>
							<span className="truncate">{log}</span>
						</div>
					))}
					<div className="flex items-center gap-0.5">
						<span className="text-slate-600 select-none shrink-0">&gt;</span>
						<span className="w-1 h-3 bg-emerald-500 animate-pulse" />
					</div>
				</div>
			</div>
		</div>
	);
}

export function LoginPage() {
	const [searchParams] = useSearchParams();
	const { isAuthenticated, loading: ctxLoading, login } = useAuth();

	const [apiKey, setApiKey] = useState("");
	const [showKey, setShowKey] = useState(false);
	const [remember, setRemember] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [isSuccess, setIsSuccess] = useState(false);
	const [redirectReady, setRedirectReady] = useState(false);

	// Delay redirect on form submission to display success sequence
	if (!ctxLoading && isAuthenticated && (redirectReady || !isSuccess)) {
		const from = searchParams.get("from") || "/dashboard";
		return <Navigate to={from} replace />;
	}

	const handleSubmit = async (e: FormEvent) => {
		e.preventDefault();
		setError(null);

		if (!apiKey.trim()) {
			setError("Please enter your authorization key.");
			return;
		}

		setSubmitting(true);
		try {
			if (remember) {
				try {
					sessionStorage.setItem(
						"fireai_settings",
						JSON.stringify({ apiKey: apiKey.trim() }),
					);
				} catch {
					// sessionStorage might be unavailable
				}
			}
			await login(apiKey.trim());
			setIsSuccess(true);
			setSubmitting(false);

			// Keep success screen visible for 1.5s before redirect
			setTimeout(() => {
				setRedirectReady(true);
			}, 1500);
		} catch (err) {
			const msg = err instanceof Error ? err.message : "Login failed";
			if (msg.includes("429") || msg.includes("Too many")) {
				setError("Too many failed attempts. Please wait a few minutes.");
			} else if (msg.includes("401") || msg.includes("Invalid")) {
				setError("Invalid Authorization key. Please verify and try again.");
			} else if (msg.includes("Failed to fetch") || msg.includes("Network")) {
				setError("Unable to reach the server. Check your connection.");
			} else {
				setError(msg);
			}
			setSubmitting(false);
		}
	};

	// Determine key security strength dynamically
	const getKeyStrength = (key: string) => {
		if (!key) return { score: 0, label: "", color: "" };
		const trimmed = key.trim();
		if (trimmed.length < 8) {
			return { score: 1, label: "Weak Key", color: "bg-rose-500" };
		}
		const hasPattern = trimmed.startsWith("BS-");
		const hasMinLength = trimmed.length >= 15;
		if (hasPattern && hasMinLength) {
			return { score: 3, label: "Secure Key Format", color: "bg-emerald-500" };
		}
		return { score: 2, label: "Moderate Key Strength", color: "bg-amber-500" };
	};

	const strength = getKeyStrength(apiKey);

	// Animation config for staggered entrance
	const leftPanelContainer = {
		hidden: { opacity: 0 },
		show: {
			opacity: 1,
			transition: {
				staggerChildren: 0.12,
				delayChildren: 0.1,
			},
		},
	};

	const leftPanelItem = {
		hidden: { opacity: 0, y: 20 },
		show: {
			opacity: 1,
			y: 0,
			transition: { type: "spring" as const, stiffness: 120, damping: 20 },
		},
	};

	return (
		<div className="min-h-screen w-full flex flex-col md:flex-row bg-[#05070f] text-[#f8fafc] font-sans selection:bg-rose-500/30 overflow-hidden relative" role="main" aria-label="BAZSPARK Login">
			
			{/* Custom CSS for the 3D grid and premium micro-interactions */}
			<style dangerouslySetInnerHTML={{ __html: `
				.grid-3d-bg {
					position: absolute;
					inset: 0;
					z-index: 0;
					overflow: hidden;
					background-color: #05070f;
					perspective: 280px;
				}
				.grid-3d-grid {
					position: absolute;
					top: -60%;
					left: -50%;
					right: -50%;
					bottom: -50%;
					width: 200%;
					height: 220%;
					background-image: 
						linear-gradient(rgba(239, 68, 68, 0.032) 1px, transparent 1px),
						linear-gradient(90deg, rgba(239, 68, 68, 0.032) 1px, transparent 1px);
					background-size: 50px 50px;
					transform: rotateX(60deg) translateY(0);
					transform-origin: center center;
					animation: gridScroll 18s linear infinite;
				}
				@keyframes gridScroll {
					0% {
						transform: rotateX(60deg) translateY(0);
					}
					100% {
						transform: rotateX(60deg) translateY(50px);
					}
				}
				.grid-3d-overlay {
					position: absolute;
					inset: 0;
					background: radial-gradient(circle at 50% 40%, transparent 10%, #05070f 85%);
					pointer-events: none;
				}
				.feature-icon-box {
					transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
				}
				.feature-row:hover .feature-icon-box {
					transform: scale(1.08) rotate(3deg);
				}
			` }} />

			{/* 3D perspective grid background */}
			<div className="grid-3d-bg pointer-events-none">
				<div className="grid-3d-grid" />
				<div className="grid-3d-overlay" />
				{/* Glowing orbs for depth */}
				<div className="absolute top-[10%] left-[10%] w-[50%] h-[50%] rounded-full bg-rose-500/[0.03] blur-[130px]" />
				<div className="absolute bottom-[10%] right-[10%] w-[50%] h-[50%] rounded-full bg-cyan-500/[0.02] blur-[130px]" />
			</div>

			{/* Brand Network particle system overlay */}
			<BrandNetworkBackground />

			{/* ═══════════════════════════════════════════════════════════════
				LEFT PANEL: Brand Identity, Logo, Metrics, and Safety HUD
			   ═════════════════════════════════════════════════════════════════ */}
			<motion.div
				variants={leftPanelContainer}
				initial="hidden"
				animate="show"
				className="w-full md:w-1/2 relative flex flex-col justify-between p-10 lg:p-16 xl:p-20 z-10 border-b md:border-b-0 md:border-r border-slate-900/60 bg-gradient-to-b from-[#05070f]/20 to-[#05070f]/85 backdrop-blur-[2px] overflow-y-auto"
			>
				
				{/* Top Branding Section */}
				<motion.div variants={leftPanelItem} className="flex items-center gap-4 mb-4">
					<BazSparkLogo size={42} animated className="flex-shrink-0" />
					<BazSparkWordmark size="md" />
				</motion.div>

				{/* Headline and Features List */}
				<div className="my-auto max-w-lg space-y-8 py-8">
					<motion.div variants={leftPanelItem} className="space-y-4">
						<span className="text-rose-500 font-mono text-xs font-bold tracking-widest uppercase flex items-center gap-2">
							<span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
							THE FUTURE OF LIFE-SAFETY ENGINEERING
						</span>
						<h1 className="text-3xl lg:text-4xl xl:text-5xl font-black tracking-tight text-white leading-tight lg:leading-[1.12]">
							Autonomous 3D Routing <br />& Compliance Solver
						</h1>
						<p className="text-slate-400 text-sm lg:text-base leading-relaxed max-w-md opacity-90">
							BAZSPARK integrates safety codes with automated path-planning, allowing engineers to design safety-critical fire alarm loops in minutes.
						</p>
					</motion.div>

					{/* Glowing Metrics Grid with Enhanced Spacing & Typography */}
					<motion.div variants={leftPanelItem} className="grid grid-cols-3 gap-4 lg:gap-5 pt-2">
						<div className="rounded-xl border border-slate-900 bg-slate-950/60 p-3.5 lg:p-4 text-center space-y-1 hover:border-cyan-500/20 hover:shadow-[0_0_15px_rgba(6,182,212,0.08)] transition-all duration-300">
							<div className="text-2xl lg:text-3xl font-black tracking-tight font-mono">
								<span className="bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">80%</span>
							</div>
							<p className="text-[9px] lg:text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">
								Time Saved
							</p>
						</div>

						<div className="rounded-xl border border-slate-900 bg-slate-950/60 p-3.5 lg:p-4 text-center space-y-1 hover:border-rose-500/20 hover:shadow-[0_0_15px_rgba(244,63,94,0.08)] transition-all duration-300">
							<div className="text-2xl lg:text-3xl font-black tracking-tight font-mono">
								<span className="bg-gradient-to-r from-rose-400 to-orange-400 bg-clip-text text-transparent">100%</span>
							</div>
							<p className="text-[9px] lg:text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">
								Compliant
							</p>
						</div>

						<div className="rounded-xl border border-slate-900 bg-slate-950/60 p-3.5 lg:p-4 text-center space-y-1 hover:border-purple-500/20 hover:shadow-[0_0_15px_rgba(168,85,247,0.08)] transition-all duration-300">
							<div className="text-2xl lg:text-3xl font-black tracking-tight font-mono">
								<span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">ZERO</span>
							</div>
							<p className="text-[9px] lg:text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">
								Collisions
							</p>
						</div>
					</motion.div>

					{/* Safety HUD Scanner preview with breathing margin */}
					<motion.div variants={leftPanelItem} className="pt-2 pb-1">
						<BrandSafetyHUD />
					</motion.div>
				</div>

				{/* Bottom Quote & Log Section with Enhanced Margins & Padding */}
				<motion.div variants={leftPanelItem} className="w-full pt-6">
					<div className="h-px bg-slate-800/80 mb-6 w-full" />
					<div className="flex items-center gap-4">
						{/* Micro dashboard layout preview square */}
						<div className="w-9 h-9 rounded border border-slate-850 bg-slate-950/95 flex-shrink-0 relative overflow-hidden flex items-center justify-center">
							<div className="absolute inset-0 opacity-[0.12] bg-[linear-gradient(rgba(239,68,68,0.5)_1px,transparent_1px),linear-gradient(90deg,rgba(239,68,68,0.5)_1px,transparent_1px)] bg-[size:3px_3px]" />
							<div className="w-3.5 h-3.5 rounded-full border-2 border-rose-500/30 border-t-rose-500 animate-spin" />
						</div>
						<div className="space-y-0.5">
							<p className="text-slate-400 text-xs lg:text-[13px] italic leading-relaxed">
								&ldquo;Precision-critical fire protection algorithms for high-stakes structures.&rdquo;
							</p>
							<p className="text-[9px] font-mono text-slate-500 tracking-widest uppercase">
								SYSTEM LOG :: SECURE INITIATION
							</p>
						</div>
					</div>
				</motion.div>

			</motion.div>

			{/* ═══════════════════════════════════════════════════════════════
				RIGHT PANEL: System Access Form Panel (50% Width)
			   ═════════════════════════════════════════════════════════════════ */}
			<div className="w-full md:w-1/2 flex items-center justify-center p-10 lg:p-16 z-10 relative">
				
				<motion.div
					initial={{ opacity: 0, x: 30 }}
					animate={{ opacity: 1, x: 0 }}
					transition={{ type: "spring" as const, stiffness: 100, damping: 20, delay: 0.15 }}
					className="w-full max-w-[440px] flex flex-col py-8"
				>
					{/* Header with Breathing Room */}
					<div className="mb-10 space-y-3">
						<h2 className="text-3xl lg:text-4xl font-black text-white tracking-tight">
							System Access
						</h2>
						<p className="text-slate-400 text-sm lg:text-base leading-relaxed">
							Enter your credentials key below to initialize a secure session.
						</p>
					</div>

					{/* Form / Success Transition Container */}
					<div className="min-h-[320px] relative">
						<AnimatePresence mode="wait">
							{!isSuccess ? (
								<motion.div
									key="login-form-container"
									initial={{ opacity: 1 }}
									exit={{ opacity: 0, y: -15, transition: { duration: 0.2 } }}
									className="space-y-7"
								>
									<form onSubmit={handleSubmit} className="space-y-5">
										{error && (
											<div className="flex gap-3 bg-red-500/10 border border-red-500/20 text-red-400 p-3.5 rounded-lg text-xs leading-normal select-none" role="alert">
												<AlertCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5 animate-pulse" />
												<div className="space-y-1">
													<div className="font-extrabold uppercase tracking-widest text-[9px]">
														Sign-in failed
													</div>
													<div className="opacity-90 leading-relaxed font-sans text-xs">
														{error}
													</div>
												</div>
											</div>
										)}

										{/* API Key input field */}
										<div className="space-y-4">
											<div className="flex justify-between items-center h-4">
												<span className="text-[10px] lg:text-[11px] font-extrabold tracking-widest text-slate-500 uppercase">
													SECURE ACCESS PORTAL
												</span>
												<a
													href="mailto:ahmdelbaz28@gmail.com"
													className="text-[11px] lg:text-[12px] font-extrabold uppercase tracking-widest text-cyan-400 hover:text-cyan-300 transition-colors hover:underline"
												>
													SUPPORT
												</a>
											</div>

											{/* Floating Label Wrapper */}
											<div className="relative mt-2">
												<KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-slate-500 z-10" />
												<Input
													id="api-key"
													type={showKey ? "text" : "password"}
													autoComplete="off"
													autoFocus
													placeholder=" "
													value={apiKey}
													onChange={(e) => setApiKey(e.target.value)}
													disabled={submitting}
													className="peer pl-11 pr-11 font-mono text-sm tracking-widest bg-slate-950/80 border-slate-800 text-white rounded-lg h-12 transition-all duration-300 focus:border-rose-500/80 focus:ring-1 focus:ring-rose-500/20 focus:shadow-[0_0_15px_rgba(239,68,68,0.15)]"
												/>
												<Label
													htmlFor="api-key"
													className="absolute left-11 top-1/2 -translate-y-1/2 text-xs text-slate-500 transition-all duration-300 pointer-events-none origin-[0]
														peer-focus:top-2 peer-focus:scale-85 peer-focus:-translate-y-4 peer-focus:text-rose-500 peer-focus:bg-[#05070f] peer-focus:px-1
														peer-[:not(:placeholder-shown)]:top-2 peer-[:not(:placeholder-shown)]:scale-85 peer-[:not(:placeholder-shown)]:-translate-y-4 peer-[:not(:placeholder-shown)]:bg-[#05070f] peer-[:not(:placeholder-shown)]:px-1"
												>
													AUTHORIZATION KEY
												</Label>
												<button
													type="button"
													onClick={() => setShowKey(!showKey)}
													className="absolute right-3.5 top-1/2 -translate-y-1/2 p-1 text-slate-500 transition-colors hover:text-rose-400 z-10"
													aria-label={showKey ? "Hide API key" : "Show API key"}
													tabIndex={-1}
												>
													{showKey ? (
														<EyeOff className="h-[18px] w-[18px]" />
													) : (
														<Eye className="h-[18px] w-[18px]" />
													)}
												</button>
											</div>

											{/* Key Strength Indicator */}
											{apiKey && (
												<div className="space-y-1.5 pt-1">
													<div className="flex justify-between items-center text-[10px]">
														<span className="text-slate-500">Security Strength</span>
														<span className={
															strength.score === 1 ? "text-rose-400 font-bold" :
															strength.score === 2 ? "text-amber-400 font-bold" :
															"text-emerald-400 font-bold"
														}>
															{strength.label}
														</span>
													</div>
													<div className="grid grid-cols-3 gap-1">
														<div className={`h-1 rounded-full transition-all duration-300 ${strength.score >= 1 ? strength.color : "bg-slate-900"}`} />
														<div className={`h-1 rounded-full transition-all duration-300 ${strength.score >= 2 ? strength.color : "bg-slate-900"}`} />
														<div className={`h-1 rounded-full transition-all duration-300 ${strength.score >= 3 ? strength.color : "bg-slate-900"}`} />
													</div>
												</div>
											)}

											<p className="text-[10px] text-slate-500 tracking-normal mt-1 leading-normal">
												Required for secure terminal access and Revit bridge authorization.
											</p>
										</div>

										{/* Remember me */}
										<div className="flex items-center gap-2.5 pt-1">
											<Checkbox
												id="remember"
												checked={remember}
												onCheckedChange={(v) => setRemember(v === true)}
												disabled={submitting}
												className="border-slate-800 h-4 w-4 data-[state=checked]:bg-rose-600 data-[state=checked]:border-rose-600"
											/>
											<Label htmlFor="remember" className="text-xs lg:text-sm cursor-pointer select-none text-slate-450 hover:text-slate-300 transition-colors leading-none">
												Maintain persistent secure connection
											</Label>
										</div>

										{/* Submit button with enhanced size & typography */}
										<Button
											type="submit"
											className="w-full h-12 lg:h-13 text-xs lg:text-sm font-extrabold tracking-widest rounded-lg transition-all duration-300 bg-rose-600 hover:bg-rose-500 text-white shadow-lg hover:shadow-rose-600/25 disabled:opacity-50 disabled:pointer-events-none mt-3"
											disabled={submitting || !apiKey.trim()}
										>
											{submitting ? (
												<>
													<Loader2 className="h-4 w-4 animate-spin mr-2" />
													INITIALIZING SESSION...
												</>
											) : (
												<>
													<ShieldCheck className="h-4 w-4 mr-2" />
													INITIALIZE SESSION
												</>
											)}
										</Button>
									</form>
								</motion.div>
							) : (
								<motion.div
									key="success-overlay"
									initial={{ opacity: 0, scale: 0.95, y: 15 }}
									animate={{ opacity: 1, scale: 1, y: 0 }}
									transition={{ type: "spring" as const, stiffness: 260, damping: 20 }}
									className="text-center py-10 space-y-6 flex flex-col items-center justify-center bg-slate-950/40 border border-emerald-500/20 rounded-xl p-6 backdrop-blur-sm"
								>
									<div className="relative flex items-center justify-center">
										{/* Pulsing glow background */}
										<div className="absolute inset-0 bg-emerald-500/20 rounded-full blur-xl animate-pulse w-20 h-20 -translate-y-0.5" />
										<div className="h-16 w-16 rounded-full bg-emerald-950/80 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.25)] relative z-10">
											<motion.svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												strokeWidth={3}
												stroke="currentColor"
												className="w-8 h-8"
												initial={{ pathLength: 0 }}
												animate={{ pathLength: 1 }}
												transition={{ duration: 0.5, delay: 0.15 }}
											>
												<motion.path
													strokeLinecap="round"
													strokeLinejoin="round"
													d="M4.5 12.75l6 6 9-13.5"
												/>
											</motion.svg>
										</div>
									</div>
									<div className="space-y-1.5">
										<h3 className="text-lg font-bold text-white tracking-wide">
											Access Granted
										</h3>
										<p className="text-xs text-slate-400">
											Secure engineering session initialized successfully.
										</p>
									</div>
									<div className="w-full max-w-[200px] h-1 bg-slate-900 rounded-full overflow-hidden relative">
										<motion.div
											className="h-full bg-emerald-500 rounded-full"
											initial={{ width: "0%" }}
											animate={{ width: "100%" }}
											transition={{ duration: 1.2, ease: "easeInOut" }}
										/>
									</div>
									<span className="text-[9px] font-mono tracking-widest text-slate-500 uppercase animate-pulse">
										REDIRECTING TO DASHBOARD...
									</span>
								</motion.div>
							)}
						</AnimatePresence>
					</div>
				</motion.div>

			</div>
		</div>
	);
}
