/**
 * FDSSimulationPage.tsx — FDS (Fire Dynamics Simulator) Simulation UI.
 *
 * V270: New page covering v2 FDS endpoints:
 * - Submit FDS job (POST /fds/submit)
 * - Track job status (GET /fds/status/{job_id})
 * - List recent jobs (GET /fds/jobs)
 * - Create smoke simulation state (POST /smoke-simulation/state)
 */
import { useState } from "react";
import {
  Activity,
  CheckCircle2,
  Clock,
  FileText,
  Flame,
  Loader2,
  Play,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
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
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { v2Api, v2ExtendedApi } from "@/services/fullApi";
import { useToast } from "@/hooks/use-toast";

interface FdsJob {
  job_id?: string;
  status: string;
  project_id?: string;
  fds_run_id?: string;
  created_at?: string;
  completed_at?: string;
  result?: Record<string, unknown>;
  error?: string;
}

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "secondary",
  queued: "secondary",
  running: "default",
  completed: "default",
  success: "default",
  failed: "destructive",
  error: "destructive",
  timeout: "destructive",
  cancelled: "outline",
};

const PLACEHOLDER_FDS_INPUT = `&HEAD CHID='fds_simulation', TITLE='BAZSPARK FDS Simulation' /
&GRID ID='Domain', IJK=32,32,16, XB=0.0,16.0,0.0,16.0,0.0,8.0 /
&TIME TWFIN=60.0 /
&INIT XB=0.0,16.0,0.0,16.0,0.0,8.0, TEMPERATURE=20.0 /
&SURF ID='BURNER', HRRPUA=500.0, COLOR='RED' /
&OBST XB=7.0,9.0,7.0,9.0,0.0,0.2, SURF_ID='BURNER' /
&SLCF PBY=8.0, QUANTITY='TEMPERATURE' /
&SLCF PBZ=2.0, QUANTITY='VELOCITY' /
&TAIL /`;

export function FDSSimulationPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [jobs, setJobs] = useState<FdsJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<FdsJob | null>(null);
  const [smokeState, setSmokeState] = useState<Record<string, unknown> | null>(null);

  // Submit form
  const [fdsInput, setFdsInput] = useState(PLACEHOLDER_FDS_INPUT);
  const [projectId, setProjectId] = useState("");

  // Status lookup
  const [statusJobId, setStatusJobId] = useState("");

  // Smoke state form
  const [smokeRoomId, setSmokeRoomId] = useState("room-001");
  const [smokeStateJson, setSmokeStateJson] = useState(
    JSON.stringify(
      [
        { x: 4, y: 4, z: 2, density_kg_m3: 0.05 },
        { x: 8, y: 8, z: 2, density_kg_m3: 0.12 },
      ],
      null,
      2,
    ),
  );
  const [smokeFdsRunId, setSmokeFdsRunId] = useState("");
  const [simUpdateState, setSimUpdateState] = useState("");
  const [simUpdateResult, setSimUpdateResult] = useState<Record<string, unknown> | null>(null);

  const handleSubmitJob = async () => {
    if (!fdsInput || fdsInput.length < 10) {
      toast({ title: "FDS input must be at least 10 characters", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = (await v2Api.submitFdsJob({
        fds_input: fdsInput,
        project_id: projectId || undefined,
      })) as FdsJob;
      setSelectedJob(res);
      toast({
        title: "FDS job submitted",
        description: `Job ID: ${res.job_id || "N/A"}`,
      });
    } catch (err) {
      toast({
        title: "Submission failed",
        description: err instanceof Error ? err.message : "FDS service may not be configured",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCheckStatus = async () => {
    if (!statusJobId) {
      toast({ title: "Enter a job ID first", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = (await v2Api.getFdsJobStatus(statusJobId)) as FdsJob;
      setSelectedJob(res);
      toast({
        title: `Status: ${res.status}`,
        description: `Job: ${statusJobId}`,
      });
    } catch (err) {
      toast({
        title: "Status check failed",
        description: err instanceof Error ? err.message : "Job not found",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleListJobs = async () => {
    setLoading(true);
    try {
      const res = (await v2Api.listFdsJobs(20)) as { jobs?: FdsJob[] };
      setJobs(res.jobs || []);
      toast({
        title: "Jobs loaded",
        description: `${(res.jobs || []).length} job(s) found`,
      });
    } catch (err) {
      toast({
        title: "Failed to list jobs",
        description: err instanceof Error ? err.message : "FDS service may not be configured",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSmokeState = async () => {
    let densityPoints: Array<{ x: number; y: number; z: number; density_kg_m3: number }>;
    try {
      densityPoints = JSON.parse(smokeStateJson);
      if (!Array.isArray(densityPoints)) throw new Error("Not an array");
    } catch {
      toast({ title: "Invalid smoke density points JSON", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = await v2Api.setSmokeSimulationState({
        room_id: smokeRoomId,
        smoke_density_points: densityPoints,
        fds_run_id: smokeFdsRunId || undefined,
      });
      setSmokeState(res as Record<string, unknown>);
      toast({
        title: "Smoke state created",
        description: `Room: ${smokeRoomId}`,
      });
    } catch (err) {
      toast({
        title: "Failed to create smoke state",
        description: err instanceof Error ? err.message : "Failed",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Flame aria-hidden="true" className="h-5 w-5 text-primary" />
            FDS Simulation
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Submit, monitor, and review Fire Dynamics Simulator (FDS) smoke simulation jobs
          </p>
        </div>

        {/* Actions Bar */}
        <div className="flex items-center gap-3">
          <Button onClick={handleListJobs} disabled={loading} variant="outline">
            {loading ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw aria-hidden="true" className="h-4 w-4" />
            )}
            Refresh Jobs
          </Button>
          {jobs.length > 0 && (
            <Badge variant="secondary" className="text-xs">
              {jobs.length} recent jobs
            </Badge>
          )}
        </div>

        {/* Job Status Lookup */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search aria-hidden="true" className="h-4 w-4 text-primary" />
              Job Status Lookup
            </CardTitle>
            <CardDescription>
              Check the status and results of a submitted FDS simulation job
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input
                autoComplete="off"
                value={statusJobId}
                onChange={(e) => setStatusJobId(e.target.value)}
                placeholder="Enter job ID..."
                className="max-w-sm"
              />
              <Button onClick={handleCheckStatus} disabled={loading || !statusJobId}>
                {loading ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Search aria-hidden="true" className="h-4 w-4" />
                )}
                Check Status
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Submit Job */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Play aria-hidden="true" className="h-4 w-4 text-primary" />
              Submit FDS Simulation
            </CardTitle>
            <CardDescription>
              Paste FDS input file content to submit a cloud simulation job
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">FDS Input (.fds file content)</Label>
                <Textarea
                  value={fdsInput}
                  onChange={(e) => setFdsInput(e.target.value)}
                  placeholder="Paste FDS input file content here..."
                  className="font-mono text-xs min-h-[160px] bg-card border-border text-foreground"
                  rows={8}
                />
                <p className="text-xs text-muted-foreground">
                  Minimum 10 characters. Supports full FDS input file format.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">
                  Project ID <span className="text-muted-foreground/60">(optional)</span>
                </Label>
                <Input
                  autoComplete="off"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  placeholder="default-project"
                  className="max-w-xs"
                />
              </div>
              <Button
                onClick={handleSubmitJob}
                disabled={loading || fdsInput.length < 10}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                {loading ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Play aria-hidden="true" className="h-4 w-4 mr-2" />
                )}
                Submit Simulation
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Selected Job Details */}
        {selectedJob && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileText aria-hidden="true" className="h-4 w-4 text-primary" />
                Job Details
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <span className="text-xs text-muted-foreground block">Job ID</span>
                  <span className="text-sm font-mono text-foreground">
                    {selectedJob.job_id || selectedJob.fds_run_id || "N/A"}
                  </span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">Status</span>
                  <Badge
                    variant={STATUS_VARIANTS[selectedJob.status] || "secondary"}
                    className="mt-1"
                  >
                    {selectedJob.status === "running" && (
                      <Loader2 aria-hidden="true" className="h-3 w-3 mr-1 animate-spin" />
                    )}
                    {selectedJob.status === "completed" && (
                      <CheckCircle2 aria-hidden="true" className="h-3 w-3 mr-1" />
                    )}
                    {selectedJob.status === "failed" && (
                      <XCircle aria-hidden="true" className="h-3 w-3 mr-1" />
                    )}
                    {(selectedJob.status === "pending" || selectedJob.status === "queued") && (
                      <Clock aria-hidden="true" className="h-3 w-3 mr-1" />
                    )}
                    {selectedJob.status}
                  </Badge>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">Project</span>
                  <span className="text-sm text-foreground">
                    {selectedJob.project_id || "—"}
                  </span>
                </div>
              </div>

              {selectedJob.created_at && (
                <div className="text-xs text-muted-foreground mb-3">
                  Created: {selectedJob.created_at}
                  {selectedJob.completed_at && ` · Completed: ${selectedJob.completed_at}`}
                </div>
              )}

              {selectedJob.error && (
                <div className="p-3 rounded-lg bg-danger/10 border border-danger/30 mb-3">
                  <span className="text-xs font-medium text-danger">Error:</span>
                  <p className="text-xs text-danger/80 mt-1 font-mono">{selectedJob.error}</p>
                </div>
              )}

              {selectedJob.result && Object.keys(selectedJob.result).length > 0 && (
                <div className="p-3 rounded-lg bg-muted/50 border border-border">
                  <span className="text-xs font-medium text-foreground block mb-2">
                    Simulation Results
                  </span>
                  <pre className="text-xs font-mono whitespace-pre-wrap text-foreground max-h-64 overflow-auto">
                    {JSON.stringify(selectedJob.result, null, 2)}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <Separator className="bg-border" />

        {/* Smoke Simulation State */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity aria-hidden="true" className="h-4 w-4 text-primary" />
              Smoke Simulation State
            </CardTitle>
            <CardDescription>
              Create or update a validated smoke simulation state for a room
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Room ID</Label>
                <Input
                  autoComplete="off"
                  value={smokeRoomId}
                  onChange={(e) => setSmokeRoomId(e.target.value)}
                  placeholder="room-001"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">
                  FDS Run ID <span className="text-muted-foreground/60">(optional)</span>
                </Label>
                <Input
                  autoComplete="off"
                  value={smokeFdsRunId}
                  onChange={(e) => setSmokeFdsRunId(e.target.value)}
                  placeholder="fds-2026-001"
                />
                <p className="text-xs text-muted-foreground">
                  Format: <span className="font-mono">fds-YYYY-NNN</span>
                </p>
              </div>
            </div>
            <div className="mt-4 space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Smoke Density Points <span className="font-mono">(JSON array)</span>
              </Label>
              <Textarea
                value={smokeStateJson}
                onChange={(e) => setSmokeStateJson(e.target.value)}
                className="font-mono text-xs min-h-[100px] bg-card border-border text-foreground"
                rows={4}
              />
            </div>
            <Button
              onClick={handleCreateSmokeState}
              disabled={loading}
              className="mt-4 bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              {loading ? (
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : (
                <Activity aria-hidden="true" className="h-4 w-4" />
              )}
              Create Smoke State
            </Button>

            <Separator className="bg-border my-4" />

            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Update Simulation State (v2 Extended)
              </Label>
              <p className="text-xs text-muted-foreground/60">
                Update the smoke simulation state via v2 Extended API
              </p>
              <div className="flex gap-2 mt-2">
                <Input
                  autoComplete="off"
                  value={simUpdateState}
                  onChange={(e) => setSimUpdateState(e.target.value)}
                  placeholder='{"status": "running", "progress": 0.5}'
                  className="flex-1"
                />
                <Button
                  onClick={async () => {
                    let parsedState: Record<string, unknown>;
                    try {
                      parsedState = JSON.parse(simUpdateState || "{}");
                    } catch {
                      toast({ title: "Invalid JSON state", variant: "destructive" });
                      return;
                    }
                    setLoading(true);
                    try {
                      const res = await v2ExtendedApi.updateSmokeSimulation({ state: parsedState });
                      setSimUpdateResult(res as Record<string, unknown>);
                      toast({ title: "Simulation state updated" });
                    } catch (err) {
                      toast({
                        title: "Update failed",
                        description: err instanceof Error ? err.message : "Failed",
                        variant: "destructive",
                      });
                    } finally {
                      setLoading(false);
                    }
                  }}
                  disabled={loading}
                  className="bg-primary hover:bg-primary/90 text-primary-foreground"
                >
                  {loading ? (
                    <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                  ) : (
                    <Activity aria-hidden="true" className="h-4 w-4" />
                  )}
                  Update Simulation State
                </Button>
              </div>
              {simUpdateResult && (
                <div className="mt-3 p-3 rounded-lg bg-muted/50 border border-border">
                  <pre className="text-xs font-mono whitespace-pre-wrap text-foreground max-h-48 overflow-auto">
                    {JSON.stringify(simUpdateResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {smokeState && (
              <div className="mt-4 p-3 rounded-lg bg-muted/50 border border-border">
                <pre className="text-xs font-mono whitespace-pre-wrap text-foreground max-h-48 overflow-auto">
                  {JSON.stringify(smokeState, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Jobs List */}
        {jobs.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock aria-hidden="true" className="h-4 w-4 text-primary" />
                Recent Jobs ({jobs.length})
              </CardTitle>
              <CardDescription>Recently submitted FDS simulation jobs</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {jobs.map((job, i) => (
                  <div
                    key={job.job_id || i}
                    className="flex items-center justify-between p-3 rounded-lg border border-border bg-card/50 cursor-pointer hover:bg-card/80 transition-colors"
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setStatusJobId(job.job_id || ""); setSelectedJob(job); } }}
                    onClick={() => {
                      setStatusJobId(job.job_id || "");
                      setSelectedJob(job);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        setStatusJobId(job.job_id || "");
                        setSelectedJob(job);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono text-foreground truncate">
                          {job.job_id || "N/A"}
                        </span>
                        <Badge
                          variant={STATUS_VARIANTS[job.status] || "secondary"}
                          className="text-xs shrink-0"
                        >
                          {job.status}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {job.project_id && <>Project: {job.project_id} · </>}
                        {job.created_at && <>{job.created_at}</>}
                      </div>
                    </div>
                    {(job.status === "completed" || job.status === "success") && (
                      <CheckCircle2
                        aria-hidden="true"
                        className="h-4 w-4 text-success shrink-0 ml-2"
                      />
                    )}
                    {job.status === "failed" && (
                      <XCircle
                        aria-hidden="true"
                        className="h-4 w-4 text-danger shrink-0 ml-2"
                      />
                    )}
                    {(job.status === "pending" || job.status === "queued") && (
                      <Clock
                        aria-hidden="true"
                        className="h-4 w-4 text-muted-foreground shrink-0 ml-2"
                      />
                    )}
                    {job.status === "running" && (
                      <Loader2
                        aria-hidden="true"
                        className="h-4 w-4 animate-spin text-primary shrink-0 ml-2"
                      />
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Empty State */}
        {jobs.length === 0 && !selectedJob && (
          <Card>
            <CardContent className="py-12">
              <div className="flex flex-col items-center text-center">
                <Flame
                  aria-hidden="true"
                  className="h-12 w-12 text-muted-foreground/40 mb-4"
                />
                <p className="text-muted-foreground font-medium">No FDS simulations yet</p>
                <p className="text-sm text-muted-foreground/60 mt-1">
                  Submit an FDS input file above to start a cloud simulation
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
