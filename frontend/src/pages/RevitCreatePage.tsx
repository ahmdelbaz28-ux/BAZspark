
/**
 * RevitCreatePage.tsx — Create Revit elements (wall, floor, column, beam, door, window)
 */

import {
	AppWindow,
	Box,
	Columns3,
	DoorOpen,
	Loader2,
	Ruler,
	Square,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { revitApi } from "@/services/fullApi";

const parsePoint = (s: string): number[] =>
	s.split(",").map((v) => Number.parseFloat(v.trim()));
const parsePoints = (s: string): number[][] =>
	s.split(";").map((p) => parsePoint(p.trim()));

export function RevitCreatePage() {
	const [creating, setCreating] = useState(false);
	const [activeTab, setActiveTab] = useState("wall");

	// Wall
	const [wallStart, setWallStart] = useState("0,0,0");
	const [wallEnd, setWallEnd] = useState("5000,0,0");
	const [wallHeight, setWallHeight] = useState("3000");
	const [wallLevel, setWallLevel] = useState("Level 1");
	const [wallType, setWallType] = useState("Basic Wall");

	// Floor
	const [floorBoundary, setFloorBoundary] = useState(
		"0,0,0; 5000,0,0; 5000,5000,0; 0,5000,0",
	);
	const [floorLevel, setFloorLevel] = useState("Level 1");
	const [floorType, setFloorType] = useState("Floor");

	// Column
	const [colLocation, setColLocation] = useState("2500,2500,0");
	const [colHeight, setColHeight] = useState("3000");
	const [colLevel, setColLevel] = useState("Level 1");
	const [colType, setColType] = useState("M_Columns");

	// Beam
	const [beamStart, setBeamStart] = useState("0,0,3000");
	const [beamEnd, setBeamEnd] = useState("5000,0,3000");
	const [beamLevel, setBeamLevel] = useState("Level 1");
	const [beamType, setBeamType] = useState("W-Wide Flange");

	// Door
	const [doorWall, setDoorWall] = useState("");
	const [doorLocation, setDoorLocation] = useState("1000,0,0");
	const [doorType, setDoorType] = useState("M_Single-Flush");
	const [doorLevel, setDoorLevel] = useState("Level 1");

	// Window
	const [winWall, setWinWall] = useState("");
	const [winLocation, setWinLocation] = useState("2000,0,0");
	const [winType, setWinType] = useState("M_Single-Flush");
	const [winLevel, setWinLevel] = useState("Level 1");

	const handleCreate = async (type: string) => {
		setCreating(true);
		try {
			let result;
			switch (type) {
				case "wall":
					result = await revitApi.createWall({
						start_point: parsePoint(wallStart),
						end_point: parsePoint(wallEnd),
						height: Number.parseFloat(wallHeight),
						level: wallLevel,
						wall_type: wallType,
					});
					break;
				case "floor":
					result = await revitApi.createFloor({
						boundary_points: parsePoints(floorBoundary),
						level: floorLevel,
						floor_type: floorType,
					});
					break;
				case "column":
					result = await revitApi.createColumn({
						location_point: parsePoint(colLocation),
						height: Number.parseFloat(colHeight),
						level: colLevel,
						column_type: colType,
					});
					break;
				case "beam":
					result = await revitApi.createBeam({
						start_point: parsePoint(beamStart),
						end_point: parsePoint(beamEnd),
						level: beamLevel,
						beam_type: beamType,
					});
					break;
				case "door":
					if (!doorWall) {
						toast.error("Enter host wall ID");
						return;
					}
					result = await revitApi.createDoor({
						host_wall_id: doorWall,
						location_point: parsePoint(doorLocation),
						family_type: doorType,
						level: doorLevel,
					});
					break;
				case "window":
					if (!winWall) {
						toast.error("Enter host wall ID");
						return;
					}
					result = await revitApi.createWindow({
						host_wall_id: winWall,
						location_point: parsePoint(winLocation),
						family_type: winType,
						level: winLevel,
					});
					break;
			}
			toast.success(`${type} created: ${result}`);
		} catch (err) {
			toast.error(
				`Create failed: ${err instanceof Error ? err.message : "Unknown error"}`,
			);
		} finally {
			setCreating(false);
		}
	};

	const inputClass = "bg-card border-border text-foreground";

	return (
		<div className="flex-1 overflow-auto p-6 max-w-4xl mx-auto space-y-6">
			<div>
				<h1 className="text-2xl font-bold text-foreground">
					Create Revit Elements
				</h1>
				<p className="text-sm text-muted-foreground mt-1">
					Create walls, floors, columns, beams, doors, and windows
				</p>
			</div>

			<Tabs value={activeTab} onValueChange={setActiveTab}>
				<TabsList className="bg-card border border-border flex-wrap stagger-card">
					<TabsTrigger
						value="wall"
						className="data-[state=active]:bg-primary data-[state=active]:text-white"
					>
						<Ruler aria-hidden="true" className="h-4 w-4 mr-1" /> Wall
					</TabsTrigger>
					<TabsTrigger
						value="floor"
						className="data-[state=active]:bg-primary data-[state=active]:text-white"
					>
						<Square aria-hidden="true" className="h-4 w-4 mr-1" /> Floor
					</TabsTrigger>
					<TabsTrigger
						value="column"
						className="data-[state=active]:bg-primary data-[state=active]:text-white"
					>
						<Columns3 aria-hidden="true" className="h-4 w-4 mr-1" /> Column
					</TabsTrigger>
					<TabsTrigger
						value="beam"
						className="data-[state=active]:bg-primary data-[state=active]:text-white"
					>
						<Box aria-hidden="true" className="h-4 w-4 mr-1" /> Beam
					</TabsTrigger>
					<TabsTrigger
						value="door"
						className="data-[state=active]:bg-primary data-[state=active]:text-white"
					>
						<DoorOpen aria-hidden="true" className="h-4 w-4 mr-1" /> Door
					</TabsTrigger>
					<TabsTrigger
						value="window"
						className="data-[state=active]:bg-primary data-[state=active]:text-white"
					>
						<AppWindow aria-hidden="true" className="h-4 w-4 mr-1" /> Window
					</TabsTrigger>
				</TabsList>

				<TabsContent value="wall">
					<Card className="border-border bg-card stagger-card">
						<CardHeader>
							<CardTitle className="text-foreground">Create Wall</CardTitle>
							<CardDescription className="text-muted-foreground">
								Draw a wall between two points
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div className="grid grid-cols-2 gap-3">
								<div>
									<Label className="text-foreground/90">Start (x,y,z mm)</Label>
									<Input
										value={wallStart}
										onChange={(e) => setWallStart(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">End (x,y,z mm)</Label>
									<Input
										value={wallEnd}
										onChange={(e) => setWallEnd(e.target.value)}
										className={inputClass}
									/>
								</div>
							</div>
							<div className="grid grid-cols-2 gap-3">
								<div>
									<Label className="text-foreground/90">Height (mm)</Label>
									<Input
										value={wallHeight}
										onChange={(e) => setWallHeight(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">Level</Label>
									<Input
										value={wallLevel}
										onChange={(e) => setWallLevel(e.target.value)}
										className={inputClass}
									/>
								</div>
							</div>
							<div>
								<Label className="text-foreground/90">Wall Type</Label>
								<Input
									value={wallType}
									onChange={(e) => setWallType(e.target.value)}
									className={inputClass}
								/>
							</div>
							<Button
								onClick={() => handleCreate("wall")}
								disabled={creating}
								className="bg-primary hover:bg-cyan-400 text-slate-950 font-semibold"
							>
								{creating ? (
									<Loader2 aria-hidden="true" className="h-4 w-4 mr-2 animate-spin" />
								) : null}{" "}
								Create Wall
							</Button>
						</CardContent>
					</Card>
				</TabsContent>

				<TabsContent value="floor">
					<Card className="border-border bg-card stagger-card">
						<CardHeader>
							<CardTitle className="text-foreground">Create Floor</CardTitle>
							<CardDescription className="text-muted-foreground">
								Create floor from boundary points
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div>
								<Label className="text-foreground/90">
									Boundary Points (x,y,z separated by ;)
								</Label>
								<Input
									value={floorBoundary}
									onChange={(e) => setFloorBoundary(e.target.value)}
									className={inputClass}
								/>
							</div>
							<div className="grid grid-cols-2 gap-3">
								<div>
									<Label className="text-foreground/90">Level</Label>
									<Input
										value={floorLevel}
										onChange={(e) => setFloorLevel(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">Floor Type</Label>
									<Input
										value={floorType}
										onChange={(e) => setFloorType(e.target.value)}
										className={inputClass}
									/>
								</div>
							</div>
							<Button
								onClick={() => handleCreate("floor")}
								disabled={creating}
								className="bg-primary hover:bg-cyan-400 text-slate-950 font-semibold"
							>
								{creating ? (
									<Loader2 aria-hidden="true" className="h-4 w-4 mr-2 animate-spin" />
								) : null}{" "}
								Create Floor
							</Button>
						</CardContent>
					</Card>
				</TabsContent>

				<TabsContent value="column">
					<Card className="border-border bg-card stagger-card">
						<CardHeader>
							<CardTitle className="text-foreground">Create Column</CardTitle>
							<CardDescription className="text-muted-foreground">
								Place a structural column
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div>
								<Label className="text-foreground/90">Location (x,y,z mm)</Label>
								<Input
									value={colLocation}
									onChange={(e) => setColLocation(e.target.value)}
									className={inputClass}
								/>
							</div>
							<div className="grid grid-cols-3 gap-3">
								<div>
									<Label className="text-foreground/90">Height (mm)</Label>
									<Input
										value={colHeight}
										onChange={(e) => setColHeight(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">Level</Label>
									<Input
										value={colLevel}
										onChange={(e) => setColLevel(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">Column Type</Label>
									<Input
										value={colType}
										onChange={(e) => setColType(e.target.value)}
										className={inputClass}
									/>
								</div>
							</div>
							<Button
								onClick={() => handleCreate("column")}
								disabled={creating}
								className="bg-primary hover:bg-cyan-400 text-slate-950 font-semibold"
							>
								{creating ? (
									<Loader2 aria-hidden="true" className="h-4 w-4 mr-2 animate-spin" />
								) : null}{" "}
								Create Column
							</Button>
						</CardContent>
					</Card>
				</TabsContent>

				<TabsContent value="beam">
					<Card className="border-border bg-card stagger-card">
						<CardHeader>
							<CardTitle className="text-foreground">Create Beam</CardTitle>
							<CardDescription className="text-muted-foreground">
								Place a structural beam
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div className="grid grid-cols-2 gap-3">
								<div>
									<Label className="text-foreground/90">Start (x,y,z mm)</Label>
									<Input
										value={beamStart}
										onChange={(e) => setBeamStart(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">End (x,y,z mm)</Label>
									<Input
										value={beamEnd}
										onChange={(e) => setBeamEnd(e.target.value)}
										className={inputClass}
									/>
								</div>
							</div>
							<div className="grid grid-cols-2 gap-3">
								<div>
									<Label className="text-foreground/90">Level</Label>
									<Input
										value={beamLevel}
										onChange={(e) => setBeamLevel(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">Beam Type</Label>
									<Input
										value={beamType}
										onChange={(e) => setBeamType(e.target.value)}
										className={inputClass}
									/>
								</div>
							</div>
							<Button
								onClick={() => handleCreate("beam")}
								disabled={creating}
								className="bg-primary hover:bg-cyan-400 text-slate-950 font-semibold"
							>
								{creating ? (
									<Loader2 aria-hidden="true" className="h-4 w-4 mr-2 animate-spin" />
								) : null}{" "}
								Create Beam
							</Button>
						</CardContent>
					</Card>
				</TabsContent>

				<TabsContent value="door">
					<Card className="border-border bg-card stagger-card">
						<CardHeader>
							<CardTitle className="text-foreground">Create Door</CardTitle>
							<CardDescription className="text-muted-foreground">
								Place a door in a wall
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div>
								<Label className="text-foreground/90">Host Wall ID</Label>
								<Input
									placeholder="Wall element ID"
									value={doorWall}
									onChange={(e) => setDoorWall(e.target.value)}
									className={inputClass}
								/>
							</div>
							<div>
								<Label className="text-foreground/90">Location (x,y,z mm)</Label>
								<Input
									value={doorLocation}
									onChange={(e) => setDoorLocation(e.target.value)}
									className={inputClass}
								/>
							</div>
							<div className="grid grid-cols-2 gap-3">
								<div>
									<Label className="text-foreground/90">Family Type</Label>
									<Input
										value={doorType}
										onChange={(e) => setDoorType(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">Level</Label>
									<Input
										value={doorLevel}
										onChange={(e) => setDoorLevel(e.target.value)}
										className={inputClass}
									/>
								</div>
							</div>
							<Button
								onClick={() => handleCreate("door")}
								disabled={creating}
								className="bg-primary hover:bg-cyan-400 text-slate-950 font-semibold"
							>
								{creating ? (
									<Loader2 aria-hidden="true" className="h-4 w-4 mr-2 animate-spin" />
								) : null}{" "}
								Create Door
							</Button>
						</CardContent>
					</Card>
				</TabsContent>

				<TabsContent value="window">
					<Card className="border-border bg-card stagger-card">
						<CardHeader>
							<CardTitle className="text-foreground">Create Window</CardTitle>
							<CardDescription className="text-muted-foreground">
								Place a window in a wall
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div>
								<Label className="text-foreground/90">Host Wall ID</Label>
								<Input
									placeholder="Wall element ID"
									value={winWall}
									onChange={(e) => setWinWall(e.target.value)}
									className={inputClass}
								/>
							</div>
							<div>
								<Label className="text-foreground/90">Location (x,y,z mm)</Label>
								<Input
									value={winLocation}
									onChange={(e) => setWinLocation(e.target.value)}
									className={inputClass}
								/>
							</div>
							<div className="grid grid-cols-2 gap-3">
								<div>
									<Label className="text-foreground/90">Family Type</Label>
									<Input
										value={winType}
										onChange={(e) => setWinType(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div>
									<Label className="text-foreground/90">Level</Label>
									<Input
										value={winLevel}
										onChange={(e) => setWinLevel(e.target.value)}
										className={inputClass}
									/>
								</div>
							</div>
							<Button
								onClick={() => handleCreate("window")}
								disabled={creating}
								className="bg-primary hover:bg-cyan-400 text-slate-950 font-semibold"
							>
								{creating ? (
									<Loader2 aria-hidden="true" className="h-4 w-4 mr-2 animate-spin" />
								) : null}{" "}
								Create Window
							</Button>
						</CardContent>
					</Card>
				</TabsContent>
			</Tabs>
		</div>
	);
}
