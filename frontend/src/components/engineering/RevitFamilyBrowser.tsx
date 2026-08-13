import { Box, Loader2, Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

interface RevitSymbol {
	id: string;
	name: string;
	family: string;
}

export function RevitFamilyBrowser() {
	const [open, setOpen] = useState(false);
	const [category, setCategory] = useState("doors");
	const [symbols, setSymbols] = useState<RevitSymbol[]>([]);
	const [loading, setLoading] = useState(false);
	const [search, setSearch] = useState("");

	const loadSymbols = async () => {
		if (!category) return;
		setLoading(true);
		try {
			const apiUrl = import.meta.env.VITE_API_URL || "/api/v1";
			const res = await fetch(`${apiUrl}/families/${category}/symbols`, {
				credentials: "same-origin",
			});
			if (!res.ok) throw new Error("Failed to load symbols");
			const data = await res.json();
			setSymbols(data.symbols || data || []);
		} catch (error) {
			toast.error(`Error loading family symbols: ${(error as Error).message}`);
		} finally {
			setLoading(false);
		}
	};

	const filteredSymbols = symbols.filter(
		(s) =>
			s.name.toLowerCase().includes(search.toLowerCase()) ||
			s.family.toLowerCase().includes(search.toLowerCase()),
	);

	return (
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogTrigger asChild>
				<Button variant="outline" className="w-full">
					<Box className="h-4 w-4 mr-2" />
					Browse Families
				</Button>
			</DialogTrigger>
			<DialogContent className="sm:max-w-[500px]">
				<DialogHeader>
					<DialogTitle>Revit Family Browser</DialogTitle>
				</DialogHeader>

				<div className="space-y-4 pt-4">
					<div className="flex gap-2">
						<Select value={category} onValueChange={setCategory}>
							<SelectTrigger className="w-[180px]">
								<SelectValue placeholder="Category" />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="doors">Doors</SelectItem>
								<SelectItem value="windows">Windows</SelectItem>
								<SelectItem value="walls">Walls</SelectItem>
								<SelectItem value="floors">Floors</SelectItem>
								<SelectItem value="columns">Columns</SelectItem>
								<SelectItem value="beams">Beams</SelectItem>
							</SelectContent>
						</Select>

						<Button onClick={loadSymbols} disabled={loading}>
							{loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
							Load
						</Button>
					</div>

					<div className="relative">
						<Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
						<Input
							placeholder="Search families..."
							className="pl-8"
							value={search}
							onChange={(e) => setSearch(e.target.value)}
						/>
					</div>

					<ScrollArea className="h-[300px] border rounded-md p-4">
						{loading ? (
							<div className="flex items-center justify-center h-full text-muted-foreground">
								<Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading...
							</div>
						) : filteredSymbols.length > 0 ? (
							<div className="space-y-2">
								{filteredSymbols.map((sym, i) => (
									<div
										key={i}
										className="flex flex-col p-2 bg-secondary/50 rounded hover:bg-secondary"
									>
										<span className="font-medium text-sm">{sym.name}</span>
										<span className="text-xs text-muted-foreground">
											{sym.family}
										</span>
									</div>
								))}
							</div>
						) : (
							<div className="text-center text-muted-foreground py-8">
								{symbols.length === 0
									? "Click Load to fetch families"
									: "No symbols found matching search"}
							</div>
						)}
					</ScrollArea>
				</div>
			</DialogContent>
		</Dialog>
	);
}
