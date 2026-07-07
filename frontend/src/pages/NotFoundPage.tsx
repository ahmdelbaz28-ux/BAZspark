/**
 * NotFoundPage.tsx — 404 page for unknown routes.
 *
 * V193 (R13): Previously React Router had no catch-all route, so unknown
 * paths silently rendered the SPA shell with HTTP 200 — confusing users
 * and crawlers. This page renders a clear 404 with a link back to the
 * dashboard.
 */
import { Button } from "@/components/ui/button";
import { Home, Compass } from "lucide-react";
import { useNavigate } from "react-router-dom";

export function NotFoundPage() {
	const navigate = useNavigate();
	return (
		<div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
			<div className="text-center max-w-md">
				<div className="inline-flex items-center justify-center h-20 w-20 rounded-full bg-slate-800 mb-6">
					<Compass className="h-10 w-10 text-orange-500" />
				</div>
				<h1 className="text-6xl font-bold text-slate-100 mb-2">404</h1>
				<h2 className="text-xl font-semibold text-slate-300 mb-3">
					Page not found
				</h2>
				<p className="text-sm text-slate-400 mb-6">
					The page you're looking for doesn't exist or has been moved.
					If you reached this page from a bookmark, the link may be
					outdated.
				</p>
				<div className="flex gap-3 justify-center">
					<Button
						onClick={() => navigate("/dashboard")}
						className="bg-orange-500 hover:bg-orange-600 text-white"
					>
						<Home className="h-4 w-4 mr-2" />
						Back to Dashboard
					</Button>
					<Button
						variant="outline"
						onClick={() => navigate(-1)}
						className="border-slate-700 text-slate-300 hover:bg-slate-800"
					>
						Go Back
					</Button>
				</div>
			</div>
		</div>
	);
}
