"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { Pencil, RefreshCw, Trash2, Server, Layers, CheckCircle2, Clock, PlayCircle, PauseCircle, XCircle, Activity } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/PageHeader";
import { DependencyPanel } from "@/components/dashboard/DependencyPanel";
import { TaskDetailPanel } from "@/components/dashboard/TaskDetailPanel";
import { SegmentedProgressBar } from "@/components/ui/segmented-progress";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  abortJob,
  formatApiError,
  getJob,
  getJobLayers,
  requeueFailedJobTasks,
  updateJob,
  readAuthSession,
  type JobDetail,
  type LayerList,
} from "@/services/api";

function formatRuntimeDuration(createdAt: string | null | undefined, stoppedAt: string | null | undefined): string {
  if (!createdAt) return "—";
  const start = new Date(createdAt).getTime();
  const end = stoppedAt ? new Date(stoppedAt).getTime() : new Date().getTime();
  const diffMins = Math.floor((end - start) / 60000);
  if (diffMins < 1) return "< 1m";
  const hours = Math.floor(diffMins / 60);
  const mins = diffMins % 60;
  return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
}


function StateBadge({ state, className }: { state: string; className?: string }) {
  const baseClasses = "text-[10px] font-black uppercase tracking-wider";
  switch (state) {
    case "FINISHED":
    case "SUCCEEDED":
      return <span className={cn(baseClasses, "text-success", className)}>{state}</span>;
    case "FAILED":
      return <span className={cn(baseClasses, "text-destructive", className)}>{state}</span>;
    case "RUNNING":
      return <span className={cn(baseClasses, "text-info animate-pulse", className)}>{state}</span>;
    case "PAUSED":
      return <span className={cn(baseClasses, "text-muted-foreground", className)}>{state}</span>;
    case "PENDING":
    case "READY":
      return <span className={cn(baseClasses, "text-warning", className)}>{state}</span>;
    default:
      return <span className={cn(baseClasses, "text-muted-foreground", className)}>{state}</span>;
  }
}

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [layers, setLayers] = useState<LayerList[]>([]);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isEditOpen, setIsEditOpen] = useState<boolean>(false);
  const [isAbortConfirmOpen, setIsAbortConfirmOpen] = useState<boolean>(false);
  const [isAborting, setIsAborting] = useState<boolean>(false);
  const [isRequeuingFailed, setIsRequeuingFailed] = useState<boolean>(false);
  const [draft, setDraft] = useState({ visible_name: "", priority: 50, max_tasks_per_worker: 0 });

  const session = useMemo(() => readAuthSession(), []);
  const isStaff = session?.user?.isStaff || session?.user?.isSuperuser || false;

  const completedTasks = useMemo(() => (job ? job.succeeded_tasks + job.skipped_tasks : 0), [job]);

  const loadJob = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const [jobData, layerData] = await Promise.all([getJob(jobId), getJobLayers(jobId)]);
      setJob(jobData);
      setLayers(layerData);
      if (layerData.length > 0) {
        setSelectedLayerId(prev => prev || layerData[0].id);
      }
      setDraft({
        visible_name: jobData.visible_name,
        priority: jobData.priority,
        max_tasks_per_worker: jobData.max_tasks_per_worker,
      });
    } catch (error) {
      toast.error("Unable to load job", { description: formatApiError(error) });
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadJob();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadJob]);

  const handleDraftChange =
    (key: keyof typeof draft) =>
    (event: ChangeEvent<HTMLInputElement>): void => {
      const value = event.target.value;
      setDraft((current) => ({
        ...current,
        [key]: key === "visible_name" ? value : Number(value),
      }));
    };

  const handleSave = async (): Promise<void> => {
    try {
      await updateJob(jobId, draft);
      toast.success("Job metadata updated");
      setIsEditOpen(false);
      await loadJob();
    } catch (error) {
      toast.error("Update failed", { description: formatApiError(error) });
    }
  };

  const handleAbort = async (): Promise<void> => {
    setIsAborting(true);
    try {
      await abortJob(jobId);
      toast.success("Job aborted");
      setIsAbortConfirmOpen(false);
      await loadJob();
    } catch (error) {
      toast.error("Abort failed", { description: formatApiError(error) });
    } finally {
      setIsAborting(false);
    }
  };

  const handleRequeueFailed = async (): Promise<void> => {
    setIsRequeuingFailed(true);
    try {
      const res = await requeueFailedJobTasks(jobId);
      toast.success("Failed tasks requeued", {
        description: `Requeued ${res.requeued_count} failed task(s) for execution.`,
      });
      await loadJob();
    } catch (error) {
      toast.error("Requeue failed", { description: formatApiError(error) });
    } finally {
      setIsRequeuingFailed(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader
        title={job?.visible_name || job?.name || "Job Detail"}
        description={job ? `${job.project} / ${job.department} / ${job.user}` : "Fetching details..."}
        backTo="/"
      >
        <Button variant="outline" onClick={() => void loadJob()} className="gap-2">
          <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          Refresh
        </Button>
        {job && job.failed_tasks > 0 && (
          <Button
            variant="outline"
            onClick={() => void handleRequeueFailed()}
            disabled={isRequeuingFailed}
            className="gap-2 border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 hover:text-amber-200"
          >
            <RefreshCw size={14} className={isRequeuingFailed ? "animate-spin" : ""} />
            Requeue Failed ({job.failed_tasks})
          </Button>
        )}
        <Button variant="outline" onClick={() => setIsEditOpen(true)} disabled={!job} className="gap-2">
          <Pencil size={14} />
          Edit
        </Button>
        <Button
          variant="outline"
          onClick={() => setIsAbortConfirmOpen(true)}
          disabled={!job}
          className="gap-2 border-destructive/30 text-destructive hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 size={14} />
          Abort
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">
          {isLoading || !job ? (
            <Card className="border-border">
              <CardContent className="flex h-56 items-center justify-center text-muted-foreground">
                Loading job detail...
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Job Header Overview */}
              <Card className="border-border overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none" />
                <CardContent className="p-0">
                  <div className="flex flex-col md:flex-row divide-y md:divide-y-0 md:divide-x divide-border/50">
                    
                    {/* Context Side */}
                    <div className="flex-1 p-5 flex flex-col gap-6">
                      <div className="flex items-center justify-between">
                         <h2 className="text-xl font-black tracking-tight">{job.visible_name || job.name}</h2>
                         <StateBadge state={job.state} />
                      </div>
                      
                      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">System Name</span>
                          <span className="font-mono text-xs truncate" title={job.name}>{job.name || "—"}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Log Directory</span>
                          <span className="font-mono text-xs truncate" title={job.log_directory}>{job.log_directory || "—"}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Priority</span>
                          <div>
                            <Badge variant="outline" className="px-1.5 py-0 text-[11px] font-medium border-warning/30 bg-warning/5 text-warning">
                              {job.priority}
                            </Badge>
                          </div>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Target Pools</span>
                          <div className="flex flex-wrap gap-1">
                            {job.included_pools?.length > 0 ? (
                              job.included_pools.map((pool) => (
                                <Badge key={pool} variant="secondary" className="px-1.5 py-0 text-[11px] font-medium">
                                  {pool}
                                </Badge>
                              ))
                            ) : (
                              <span className="text-xs text-muted-foreground">Any</span>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Max Tasks</span>
                          <span className="font-mono text-sm font-bold">{job.max_tasks_per_worker}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Submit Time</span>
                          <span className="font-mono text-xs">{new Date(job.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Runtime</span>
                          <span className="font-mono text-xs">{formatRuntimeDuration(job.created_at, job.stopped_at)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Progress Side */}
                    <div className="md:w-[380px] xl:w-[480px] p-5 flex flex-col justify-center bg-muted/5 shrink-0">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                          <Layers size={14} className="text-primary" /> Task Progress
                        </span>
                        <span className="font-mono text-lg font-black">{Math.round(((job.succeeded_tasks + job.skipped_tasks) / Math.max(1, job.total_tasks)) * 100)}%</span>
                      </div>
                      
                      <SegmentedProgressBar
                        className="h-2.5 rounded-full mb-5"
                        total={job.total_tasks}
                        succeeded={job.succeeded_tasks}
                        failed={job.failed_tasks}
                        running={job.running_tasks}
                        ready={job.ready_tasks}
                        waiting={job.waiting_tasks}
                        skipped={job.skipped_tasks}
                        showCounts={false}
                      />
                      
                      <div className="grid grid-cols-3 gap-2">
                         <div className="flex flex-col bg-surface-deep p-2 rounded border border-border/50">
                           <span className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Total</span>
                           <span className="font-mono text-sm font-bold">{job.total_tasks}</span>
                         </div>
                         <div className="flex flex-col bg-success/10 p-2 rounded border border-success/20">
                           <span className="text-[10px] text-success uppercase tracking-wider mb-0.5">Succeeded</span>
                           <span className="font-mono text-sm font-bold text-success">{job.succeeded_tasks}</span>
                         </div>
                         <div className="flex flex-col bg-info/10 p-2 rounded border border-info/20">
                           <span className="text-[10px] text-info uppercase tracking-wider mb-0.5">Running</span>
                           <span className="font-mono text-sm font-bold text-info">{job.running_tasks}</span>
                         </div>
                         <div className="flex flex-col bg-warning/10 p-2 rounded border border-warning/20">
                           <span className="text-[10px] text-warning uppercase tracking-wider mb-0.5">Ready</span>
                           <span className="font-mono text-sm font-bold text-warning">{job.ready_tasks}</span>
                         </div>
                         <div className="flex flex-col bg-destructive/10 p-2 rounded border border-destructive/20">
                           <span className="text-[10px] text-destructive uppercase tracking-wider mb-0.5">Failed</span>
                           <span className="font-mono text-sm font-bold text-destructive">{job.failed_tasks}</span>
                         </div>
                         <div className="flex flex-col bg-muted/50 p-2 rounded border border-border/50">
                           <span className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Waiting</span>
                           <span className="font-mono text-sm font-bold text-muted-foreground">{job.waiting_tasks}</span>
                         </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Dependencies Panel (Full Width Expandable) */}
              <DependencyPanel jobId={job.id} isStaff={isStaff} />

              {/* Unified Layers & Tasks View */}
              <Card className="border-border p-0 overflow-hidden mt-4 h-[700px] flex flex-col shadow-sm">
                <div className="flex-1 flex flex-col lg:flex-row divide-y lg:divide-y-0 lg:divide-x divide-border/50 min-h-0">
                  
                  {/* Left side: Layers Table */}
                  <div className="lg:w-[40%] xl:w-[35%] flex flex-col h-full bg-surface relative shrink-0">
                    <div className="p-3 border-b border-border/50 shrink-0 flex items-center gap-2 bg-muted/10">
                      <Layers size={16} className="text-primary" />
                      <span className="text-sm font-bold">Execution Layers</span>
                    </div>
                    <div className="flex-1 overflow-auto bg-surface-deep/20">
                      <Table>
                        <TableHeader className="bg-muted/30 sticky top-0 z-10 shadow-sm">
                          <TableRow className="hover:bg-transparent">
                            <TableHead className="pl-4 font-semibold w-[30%] text-[11px] uppercase tracking-wider h-8">Name</TableHead>
                            <TableHead className="font-semibold text-center w-[15%] text-[11px] uppercase tracking-wider h-8">Type</TableHead>
                            <TableHead className="font-semibold text-center w-[15%] text-[11px] uppercase tracking-wider h-8">State</TableHead>
                            <TableHead className="font-semibold text-right pr-4 w-[40%] text-[11px] uppercase tracking-wider h-8">Progress</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {layers.map((layer) => (
                            <TableRow 
                              key={layer.id} 
                              className={`cursor-pointer transition-colors group ${selectedLayerId === layer.id ? "bg-muted/60" : "hover:bg-muted/40"}`}
                              onClick={() => setSelectedLayerId(layer.id)}
                            >
                              <TableCell className="pl-4 py-2 text-[11px]">
                                <span className="font-bold text-primary group-hover:underline">
                                  {layer.name}
                                </span>
                              </TableCell>
                              <TableCell className="text-center py-2 text-[11px]">{layer.layer_type}</TableCell>
                              <TableCell className="text-center py-2">
                                <StateBadge state={layer.state} />
                              </TableCell>
                              <TableCell className="text-right pr-4 py-2">
                                <SegmentedProgressBar
                                  className="h-2 rounded-full"
                                  total={layer.total_tasks}
                                  succeeded={layer.succeeded_tasks}
                                  failed={layer.failed_tasks}
                                  running={layer.running_tasks}
                                  ready={layer.ready_tasks}
                                  waiting={layer.waiting_tasks}
                                  skipped={layer.skipped_tasks}
                                  showCounts={false}
                                />
                                <div className="text-[11px] text-muted-foreground mt-1 tabular-nums w-full text-right">
                                  {Math.round(((layer.succeeded_tasks + layer.skipped_tasks) / Math.max(1, layer.total_tasks)) * 100)}% ({layer.succeeded_tasks + layer.skipped_tasks}/{layer.total_tasks})
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </div>

                  {/* Right side: Tasks View */}
                  <div className="flex-1 flex flex-col h-full bg-surface relative min-w-0">
                    {selectedLayerId ? (
                      <TaskDetailPanel
                        selectedJobId={job.id}
                        selectedLayerId={selectedLayerId}
                        jobs={[{
                           id: job.id, 
                           displayId: job.visible_name || job.name, 
                           user: job.user, 
                           status: job.state, 
                           backendState: job.state,
                           total_tasks: job.total_tasks,
                           succeeded_tasks: job.succeeded_tasks,
                           failed_tasks: job.failed_tasks,
                           running_tasks: job.running_tasks,
                           ready_tasks: job.ready_tasks,
                           waiting_tasks: job.waiting_tasks,
                           skipped_tasks: job.skipped_tasks,
                           depend_tasks: job.depend_tasks,
                           created_at: job.created_at,
                           started_at: (job as any).started_at || job.created_at,
                           finished_at: job.stopped_at,
                           project: job.project,
                           department: job.department,
                           priority: job.priority,
                           included_pools: job.included_pools
                        } as any]}
                        nodes={[]}
                        pools={[]}
                        onSelectLayer={(jid, lid) => setSelectedLayerId(lid)}
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                        <Activity className="size-10 text-muted-foreground/30 mb-4" />
                        <p>Select a layer to view its tasks.</p>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            </>
          )}
        </div>

        <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
          <DialogContent className="border-border bg-surface">
            <DialogHeader>
              <DialogTitle>Edit Job Metadata</DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Update display name, scheduling priority, or worker concurrency limit.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="job-visible-name">Visible Name</Label>
                <Input
                  id="job-visible-name"
                  value={draft.visible_name}
                  onChange={handleDraftChange("visible_name")}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="job-priority">Priority</Label>
                  <Input
                    id="job-priority"
                    type="number"
                    value={draft.priority}
                    onChange={handleDraftChange("priority")}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="job-max-tasks">Max Tasks / Worker</Label>
                  <Input
                    id="job-max-tasks"
                    type="number"
                    value={draft.max_tasks_per_worker}
                    onChange={handleDraftChange("max_tasks_per_worker")}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setIsEditOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={() => void handleSave()}>Save changes</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Abort Confirmation Dialog */}
        <ConfirmDialog
          open={isAbortConfirmOpen}
          onOpenChange={setIsAbortConfirmOpen}
          variant="destructive"
          title="Abort Render Job"
          description={
            <>
              Are you sure you want to abort{" "}
              <strong className="text-foreground">{job?.visible_name || job?.name}</strong>?<br />
              This will cancel all running tasks and remove the job and all associated layers. This action cannot be undone.
            </>
          }
          confirmText="Abort Job"
          isLoading={isAborting}
          onConfirm={handleAbort}
        />
      </div>
    </div>
  );
}
