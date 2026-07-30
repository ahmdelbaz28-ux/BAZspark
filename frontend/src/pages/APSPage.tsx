/**
 * APSPage.tsx — Autodesk Platform Services (APS) Job Submission.
 *
 * Submit drawings/BIM files to Autodesk Cloud for design automation
 * and poll WorkItem job progress.
 *
 * Backend: POST /api/v2/aps/process, GET /api/v2/aps/status/{id}
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Box,
  Send,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";

const APS_API = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace("/api/v1", "/api/v2")}/aps`
  : "/api/v2/aps";

interface ApsJob {
  work_item_id: string;
  input_urn: string;
  output_urn: string;
  simulation_mode: boolean;
}

interface ApsStatus {
  success: boolean;
  status: string;
  report_url?: string;
  error?: string;
}

export const APSPage: React.FC = () => {
  const [bucketKey, setBucketKey] = useState("bazspark_bucket");
  const [objectKey, setObjectKey] = useState("");
  const [activityId, setActivityId] = useState("");
  const [paramsStr, setParamsStr] = useState("{}");
  const [jobId, setJobId] = useState<string | null>(null);

  const submitMutation = useMutation({
    mutationFn: async () => {
      const params = JSON.parse(paramsStr);
      const res = await fetch(`${APS_API}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ bucket_key: bucketKey, object_key: objectKey, activity_id: activityId, params }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<ApsJob>;
    },
  });

  const statusMutation = useMutation({
    mutationFn: async () => {
      if (!jobId) throw new Error("No job selected");
      const res = await fetch(`${APS_API}/status/${jobId}`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error("Failed to fetch status");
      return res.json() as Promise<ApsStatus>;
    },
  });

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Box className="h-6 w-6 text-cyan-400" />
            Autodesk Platform Services
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Submit drawings and BIM files to Autodesk Cloud for design
            automation processing
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ── Submit Form ── */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">
              Submit WorkItem
            </h3>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Bucket Key
                </label>
                <input
                  type="text"
                  value={bucketKey}
                  onChange={(e) => setBucketKey(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
                  placeholder="bazspark_bucket"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Object Key *
                </label>
                <input
                  type="text"
                  value={objectKey}
                  onChange={(e) => setObjectKey(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
                  placeholder="filename.dwg"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Activity ID *
                </label>
                <input
                  type="text"
                  value={activityId}
                  onChange={(e) => setActivityId(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
                  placeholder="your.activity.id"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Parameters (JSON)
                </label>
                <textarea
                  value={paramsStr}
                  onChange={(e) => setParamsStr(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <button
                type="button"
                onClick={() => submitMutation.mutate()}
                disabled={!objectKey || !activityId || submitMutation.isPending}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {submitMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Submit WorkItem
                  </>
                )}
              </button>

              {submitMutation.isError && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                  <p className="text-red-400 text-xs">
                    {submitMutation.error instanceof Error
                      ? submitMutation.error.message
                      : "Submission failed"}
                  </p>
                </div>
              )}

              {submitMutation.isSuccess && (
                <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-emerald-400 text-xs font-medium mb-1">
                    <CheckCircle2 className="h-4 w-4" />
                    WorkItem submitted successfully
                  </div>
                  <p className="text-emerald-300/70 text-[11px] font-mono break-all">
                    ID: {submitMutation.data.work_item_id}
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      setJobId(submitMutation.data.work_item_id)
                    }
                    className="mt-2 text-xs text-cyan-400 hover:text-cyan-300 underline"
                  >
                    Check status →
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* ── Status Panel ── */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">
              Job Status
            </h3>

            {!jobId ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-500">
                <Box className="h-10 w-10 mb-3 opacity-30" />
                <p className="text-sm">No job selected</p>
                <p className="text-xs mt-1">
                  Submit a WorkItem to see its status here
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="bg-slate-700/30 rounded-lg p-3">
                  <p className="text-[11px] text-slate-500 mb-1">Job ID</p>
                  <p className="text-xs text-slate-300 font-mono break-all">
                    {jobId}
                  </p>
                </div>

                {statusMutation.isPending && (
                  <div className="flex items-center gap-2 text-slate-400 text-sm py-4">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Fetching status...
                  </div>
                )}

                {statusMutation.isError && (
                  <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    <p className="text-red-400 text-xs">
                      {statusMutation.error instanceof Error
                        ? statusMutation.error.message
                        : "Status check failed"}
                    </p>
                  </div>
                )}

                {statusMutation.data && (
                  <div className="space-y-2">
                    <div
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                        statusMutation.data.status === "completed"
                          ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
                          : statusMutation.data.status === "failed"
                            ? "text-red-400 bg-red-500/10 border-red-500/30"
                            : "text-amber-400 bg-amber-500/10 border-amber-500/30"
                      }`}
                    >
                      {statusMutation.data.status === "completed" ? (
                        <CheckCircle2 className="h-3 w-3" />
                      ) : (
                        <AlertTriangle className="h-3 w-3" />
                      )}
                      {statusMutation.data.status}
                    </div>

                    {statusMutation.data.report_url && (
                      <a
                        href={statusMutation.data.report_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
                      >
                        <ExternalLink className="h-3 w-3" />
                        View Report
                      </a>
                    )}

                    {statusMutation.data.error && (
                      <p className="text-xs text-red-400">
                        {statusMutation.data.error}
                      </p>
                    )}
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => statusMutation.mutate()}
                  disabled={statusMutation.isPending}
                  className="w-full px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors disabled:opacity-50"
                >
                  {statusMutation.isPending ? "Checking..." : "Refresh Status"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Info */}
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-lg p-4">
          <p className="text-xs text-slate-500">
            APS (Autodesk Platform Services) enables cloud-based design
            automation. Upload your files to an Autodesk OSS bucket, then
            submit a WorkItem to process them with a Design Automation
            activity. Requires valid APS credentials configured on the server.
          </p>
        </div>
      </div>
    </div>
  );
};

export default APSPage;
