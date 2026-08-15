"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Layers,
  Link2,
  ListOrdered,
  Loader2,
  Pause,
  Play,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SegmentedProgressBar } from "@/components/ui/segmented-progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { deleteJob, formatApiError, pauseJob, resumeJob } from "@/services/api";
import type { BackendJobState, RenderJob } from "@/types/dashboard";

type QueueTabFilter = "ALL" | "RUNNING" | "PENDING" | "PAUSED" | "FAILED";

interface JobQueueProps {
  jobs: RenderJob[];
  searchQuery: string;
  onJobRemoved: () => Promise<void>;
}

function matchesJobSearch(job: RenderJob, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;

  return [job.id, job.displayId, job.user, job.backendState, job.project, job.department].some((value) =>
    value.toLowerCase().includes(normalizedQuery),
  );
}

function formatRuntime(createdAt: string | undefined): string {
  if (!createdAt) return "-";
  const start = new Date(createdAt);
  const now = new Date();
  const diffMs = now.getTime() - start.getTime();
  if (diffMs < 0) return "Just now";

  const diffSecs = Math.floor(diffMs / 1000);
  const hours = Math.floor(diffSecs / 3600);
  const minutes = Math.floor((diffSecs % 3600) / 60);

  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

const getJobStateBadge = (state: BackendJobState) => {
  switch (state) {
    case "RUNNING":
      return (
        <Badge variant="info" className="gap-1.5 font-medium pr-2">
          <Loader2 className="animate-spin" size={12} /> {state}
        </Badge>
      );
    case "FINISHED":
      return (
        <Badge variant="success" className="gap-1.5 font-medium pr-2 bg-success/15 text-success hover:bg-success/20">
          <CheckCircle2 size={12} /> {state}
        </Badge>
      );
    case "FAILED":
      return (
        <Badge
          variant="destructive"
          className="gap-1.5 font-medium pr-2 bg-destructive/15 text-destructive hover:bg-destructive/20"
        >
          <XCircle size={12} /> {state}
        </Badge>
      );
    case "PAUSED":
      return (
        <Badge variant="warning" className="gap-1.5 font-medium pr-2 bg-warning/15 text-warning hover:bg-warning/20">
          <Clock size={12} /> {state}
        </Badge>
      );
    case "PENDING":
      return (
        <Badge
          variant="secondary"
          className="gap-1.5 font-medium pr-2 bg-muted/60 text-muted-foreground hover:bg-muted"
        >
          <Clock size={12} /> {state}
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary" className="gap-1.5 font-medium pr-2">
          <Clock size={12} /> {state}
        </Badge>
      );
  }
};

export default function JobQueue({ jobs, searchQuery, onJobRemoved }: JobQueueProps) {
  const [activeTab, setActiveTab] = useState<QueueTabFilter>("ALL");
  const [actionJobId, setActionJobId] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<RenderJob | null>(null);
  const [masterAction, setMasterAction] = useState<"pause" | "resume" | null>(null);
  const [isExecutingMaster, setIsExecutingMaster] = useState<boolean>(false);

  const normalizedQuery = searchQuery.trim().toLowerCase();

  // In-flight active jobs only (excluding completed/finished)
  const inFlightJobs = useMemo(
    () => jobs.filter((j) => j.status !== "Completed" && j.backendState !== "FINISHED"),
    [jobs],
  );

  const runningCount = useMemo(() => inFlightJobs.filter((j) => j.status === "Rendering").length, [inFlightJobs]);
  const pendingCount = useMemo(() => inFlightJobs.filter((j) => j.backendState === "PENDING").length, [inFlightJobs]);
  const pausedCount = useMemo(() => inFlightJobs.filter((j) => j.status === "Paused").length, [inFlightJobs]);
  const failedCount = useMemo(() => inFlightJobs.filter((j) => j.status === "Failed").length, [inFlightJobs]);

  const filteredJobs = useMemo<RenderJob[]>(() => {
    let result = inFlightJobs;

    if (activeTab === "RUNNING") {
      result = result.filter((j) => j.status === "Rendering");
    } else if (activeTab === "PENDING") {
      result = result.filter((j) => j.backendState === "PENDING");
    } else if (activeTab === "PAUSED") {
      result = result.filter((j) => j.status === "Paused");
    } else if (activeTab === "FAILED") {
      result = result.filter((j) => j.status === "Failed");
    }

    if (normalizedQuery) {
      result = result.filter((job) => matchesJobSearch(job, normalizedQuery));
    }

    return result;
  }, [inFlightJobs, activeTab, normalizedQuery]);

  // Handle single job pause / resume
  const handleTransition = async (jobId: string, action: "pause" | "resume"): Promise<void> => {
    setActionJobId(jobId);
    try {
      if (action === "pause") {
        await pauseJob(jobId);
        toast.success("Job paused");
      } else {
        await resumeJob(jobId);
        toast.success("Job resumed");
      }
      await onJobRemoved();
    } catch (error) {
      toast.error("Action failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  // Handle single job delete
  const handleDelete = async (jobId: string): Promise<void> => {
    setActionJobId(jobId);
    try {
      await deleteJob(jobId);
      toast.success("Job deleted");
      await onJobRemoved();
    } catch (error) {
      toast.error("Delete failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
      setJobToDelete(null);
    }
  };

  // Handle emergency batch pause / resume
  const handleMasterBatchAction = async (): Promise<void> => {
    if (!masterAction) return;
    setIsExecutingMaster(true);
    const targetJobs =
      masterAction === "pause"
        ? inFlightJobs.filter((j) => j.status === "Rendering")
        : inFlightJobs.filter((j) => j.status === "Paused");

    try {
      await Promise.all(targetJobs.map((j) => (masterAction === "pause" ? pauseJob(j.id) : resumeJob(j.id))));
      toast.success(
        masterAction === "pause"
          ? `Paused ${targetJobs.length} active jobs`
          : `Resumed ${targetJobs.length} paused jobs`,
      );
      await onJobRemoved();
    } catch (error) {
      toast.error("Batch action failed", { description: formatApiError(error) });
    } finally {
      setIsExecutingMaster(false);
      setMasterAction(null);
    }
  };

  const tabs: Array<{ id: QueueTabFilter; label: string; count: number }> = [
    { id: "ALL", label: "All", count: inFlightJobs.length },
    { id: "RUNNING", label: "Running", count: runningCount },
    { id: "PENDING", label: "Pending", count: pendingCount },
    { id: "PAUSED", label: "Paused", count: pausedCount },
    { id: "FAILED", label: "Failed", count: failedCount },
  ];

  return (
    <>
      <Card className="flex flex-col justify-between h-full border-border p-0 gap-0">
        <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <CardTitle className="text-sm font-bold text-foreground mr-2 flex items-center gap-2.5">
              <ListOrdered size={15} className="text-primary" />
              Live Job Queue
            </CardTitle>
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              const hasAlert = tab.id === "FAILED" && tab.count > 0;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer",
                    isActive
                      ? "bg-primary text-primary-foreground font-semibold"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                    hasAlert && !isActive && "text-destructive hover:text-destructive bg-destructive/10",
                  )}
                >
                  <span>{tab.label}</span>
                  <span
                    className={cn(
                      "text-xs rounded-full px-2 py-0.5 min-w-5 text-center font-mono leading-none",
                      isActive
                        ? "bg-primary-foreground/20 text-primary-foreground font-bold"
                        : hasAlert
                          ? "bg-destructive text-destructive-foreground font-bold"
                          : "bg-muted text-muted-foreground",
                    )}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          <Link
            href="/jobs"
            className="text-xs font-medium text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 shrink-0 group"
          >
            <span>Full Queue</span>
            <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
          </Link>
        </CardHeader>

        <CardContent className="flex-1 p-0 overflow-hidden">
          <Table className="table-fixed" containerClassName="h-full overflow-auto">
            <TableHeader className="bg-card sticky top-0 z-10 border-b border-border/50">
              <TableRow className="hover:bg-transparent bg-muted/30">
                <TableHead className="pl-4 w-[35%] font-semibold text-xs text-muted-foreground">
                  Job ID / Project
                </TableHead>
                <TableHead className="w-[13%] font-semibold text-xs text-muted-foreground">
                  <div className="flex justify-center items-center w-full">State</div>
                </TableHead>
                <TableHead className="w-[8%] font-semibold text-xs text-muted-foreground">
                  <div className="flex justify-center items-center w-full">Priority</div>
                </TableHead>
                <TableHead className="w-[14%] font-semibold text-xs text-muted-foreground">
                  <div className="flex justify-center items-center w-full">Runtime</div>
                </TableHead>
                <TableHead className="w-[20%] font-semibold text-xs text-muted-foreground">
                  <div className="flex justify-center items-center w-full">Tasks Progress</div>
                </TableHead>
                <TableHead className="pr-4 w-[10%] text-right font-semibold text-xs text-muted-foreground">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs">
              {filteredJobs.length > 0 ? (
                filteredJobs.map((job) => {
                  const isActioning = actionJobId === job.id;

                  return (
                    <TableRow key={job.id} className="hover:bg-muted/40 transition-colors group">
                      <TableCell className="pl-4 py-3 text-left">
                        <div className="flex flex-col gap-0.5 min-w-0">
                          <Link
                            className="font-semibold text-primary hover:text-primary/80 transition-colors truncate"
                            href={`/jobs/${job.id}`}
                          >
                            {job.displayId}
                          </Link>
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground truncate">
                            <span className="font-medium text-foreground/80">{job.project}</span>
                            <span>•</span>
                            <span>{job.department}</span>
                            <span>•</span>
                            <span>{job.user}</span>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-center py-3">
                        <div className="flex flex-col items-center gap-1.5">
                          {getJobStateBadge(job.backendState)}
                          {(job.depend_tasks ?? 0) > 0 && (
                            <Tooltip>
                              <TooltipTrigger
                                className={cn(
                                  badgeVariants({ variant: "warning" }),
                                  "gap-1.5 text-xs h-5 px-2 cursor-help",
                                )}
                              >
                                <Link2 className="size-2.5" />
                                {job.depend_tasks} blocked
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                <p>
                                  Waiting on {job.depend_tasks} upstream task{job.depend_tasks !== 1 ? "s" : ""} to
                                  complete.
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-center py-3">
                        <div className="flex justify-center items-center">
                          <Badge variant="outline" className="text-xs h-5 px-2 font-bold tracking-wide font-mono">
                            {job.priority}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-center py-3">
                        <div className="flex flex-col items-center gap-0.5 font-mono">
                          <div className="text-xs font-semibold text-foreground">{formatRuntime(job.created_at)}</div>
                        </div>
                      </TableCell>
                      <TableCell className="text-center py-3 px-2">
                        <div className="w-full">
                          <SegmentedProgressBar
                            total={job.total_tasks || 1}
                            succeeded={job.succeeded_tasks}
                            failed={job.failed_tasks}
                            running={job.running_tasks}
                            ready={job.ready_tasks}
                            waiting={job.waiting_tasks}
                            skipped={job.skipped_tasks}
                            showCounts={true}
                          />
                        </div>
                      </TableCell>
                      <TableCell className="pr-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
                          {job.status === "Paused" || job.backendState === "PAUSED" ? (
                            <Tooltip>
                              <TooltipTrigger
                                render={
                                  <Button
                                    size="icon"
                                    variant="ghost"
                                    className="size-7 text-muted-foreground hover:text-success hover:bg-success/10"
                                    disabled={isActioning}
                                    onClick={() => void handleTransition(job.id, "resume")}
                                    aria-label="Resume job"
                                  >
                                    <Play size={13} />
                                  </Button>
                                }
                              />
                              <TooltipContent>Resume Job</TooltipContent>
                            </Tooltip>
                          ) : job.status === "Rendering" ||
                            job.status === "Queued" ||
                            job.backendState === "RUNNING" ||
                            job.backendState === "PENDING" ? (
                            <Tooltip>
                              <TooltipTrigger
                                render={
                                  <Button
                                    size="icon"
                                    variant="ghost"
                                    className="size-7 text-muted-foreground hover:text-warning hover:bg-warning/10"
                                    disabled={isActioning}
                                    onClick={() => void handleTransition(job.id, "pause")}
                                    aria-label="Pause job"
                                  >
                                    <Pause size={13} />
                                  </Button>
                                }
                              />
                              <TooltipContent>Pause Job</TooltipContent>
                            </Tooltip>
                          ) : null}

                          <Tooltip>
                            <TooltipTrigger
                              render={
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="size-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                  disabled={isActioning}
                                  onClick={() => setJobToDelete(job)}
                                  aria-label="Delete job"
                                >
                                  <Trash2 size={13} />
                                </Button>
                              }
                            />
                            <TooltipContent>Delete Job</TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow className="hover:bg-transparent border-0">
                  <TableCell colSpan={6} className="h-44 text-center">
                    <div className="flex flex-col items-center justify-center p-6 text-center">
                      {normalizedQuery ? (
                        <>
                          <Search size={32} className="mb-2 text-primary opacity-30" />
                          <p className="text-sm font-bold text-foreground">No matching render jobs found</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            No jobs match your search query &quot;{searchQuery}&quot;.
                          </p>
                        </>
                      ) : activeTab === "FAILED" ? (
                        <>
                          <ShieldCheck size={32} className="stroke-1.5 text-success mb-2" />
                          <p className="text-sm font-bold text-foreground">Zero Farm Errors</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            All dispatches in the current queue are executing without failures.
                          </p>
                        </>
                      ) : activeTab === "RUNNING" ? (
                        <>
                          <Layers size={32} className="mb-2 text-primary opacity-30" />
                          <p className="text-sm font-bold text-foreground">No Running Jobs</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            The compute cluster is idle and ready for new render dispatches.
                          </p>
                        </>
                      ) : activeTab === "PAUSED" ? (
                        <>
                          <Clock size={32} className="mb-2 text-muted-foreground opacity-30" />
                          <p className="text-sm font-bold text-foreground">No Paused Jobs</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            There are currently no paused render jobs in the queue.
                          </p>
                        </>
                      ) : activeTab === "PENDING" ? (
                        <>
                          <Clock size={32} className="mb-2 text-muted-foreground opacity-30" />
                          <p className="text-sm font-bold text-foreground">No Pending Jobs</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            There are no pending render jobs waiting for dispatcher allocation.
                          </p>
                        </>
                      ) : (
                        <>
                          <Layers size={32} className="mb-2 text-primary opacity-30" />
                          <p className="text-sm font-bold text-foreground">Queue Idle — No Active Renders</p>
                          <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                            All jobs have finished or the farm is currently idle. You can submit a new job or inspect
                            finished jobs in the full queue.
                          </p>
                          <div className="mt-3 flex items-center gap-2">
                            <Link
                              href="/jobs/submit"
                              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                            >
                              <Plus size={13} /> Submit New Job
                            </Link>
                            <Link
                              href="/jobs"
                              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-accent transition-colors"
                            >
                              View Job History
                            </Link>
                          </div>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>

        <span className="border-t border-border/50"></span>
        <CardFooter className="px-4 py-3 bg-muted/15 flex flex-col sm:flex-row items-center justify-between gap-2.5 text-xs shrink-0">
          <div className="flex items-center gap-2 text-muted-foreground text-xs font-mono">
            <span>
              Showing <strong className="text-foreground font-bold">{filteredJobs.length}</strong> of{" "}
              <strong className="text-foreground font-bold">{inFlightJobs.length}</strong> active jobs
            </span>
            {runningCount > 0 && (
              <>
                <span className="opacity-40">•</span>
                <span className="text-primary font-medium">{runningCount} actively rendering</span>
              </>
            )}
          </div>

          {/* Master Emergency Dispatch Controls */}
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={runningCount === 0}
                    onClick={() => setMasterAction("pause")}
                    className={cn(
                      "h-7 px-2.5 text-xs gap-1.5 font-medium transition-colors",
                      runningCount > 0
                        ? "text-warning border-warning/40 bg-warning/5 hover:bg-warning/15 hover:border-warning/60 cursor-pointer"
                        : "text-muted-foreground/50 border-border/40 opacity-50 cursor-not-allowed",
                    )}
                  >
                    <Pause size={12} />
                    <span>Pause Active</span>
                    {runningCount > 0 && (
                      <span className="bg-warning/20 text-warning px-1.5 py-0.5 rounded text-xs font-mono font-bold">
                        {runningCount}
                      </span>
                    )}
                  </Button>
                }
              />
              <TooltipContent>
                {runningCount > 0
                  ? `Emergency pause all ${runningCount} active rendering jobs`
                  : "No active rendering jobs to pause"}
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pausedCount === 0}
                    onClick={() => setMasterAction("resume")}
                    className={cn(
                      "h-7 px-2.5 text-xs gap-1.5 font-medium transition-colors",
                      pausedCount > 0
                        ? "text-success border-success/40 bg-success/5 hover:bg-success/15 hover:border-success/60 cursor-pointer"
                        : "text-muted-foreground/50 border-border/40 opacity-50 cursor-not-allowed",
                    )}
                  >
                    <Play size={12} />
                    <span>Resume Paused</span>
                    {pausedCount > 0 && (
                      <span className="bg-success/20 text-success px-1.5 py-0.5 rounded text-xs font-mono font-bold">
                        {pausedCount}
                      </span>
                    )}
                  </Button>
                }
              />
              <TooltipContent>
                {pausedCount > 0 ? `Resume dispatch for all ${pausedCount} paused jobs` : "No paused jobs to resume"}
              </TooltipContent>
            </Tooltip>
          </div>
        </CardFooter>
      </Card>

      {/* Delete Confirmation Modal */}
      <Dialog open={!!jobToDelete} onOpenChange={(open) => !open && setJobToDelete(null)}>
        <DialogContent>
          <DialogHeader className="sm:text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-destructive/10 mb-4">
              <AlertTriangle className="size-6 text-destructive" />
            </div>
            <DialogTitle className="text-center text-lg">Delete Render Job</DialogTitle>
            <DialogDescription className="text-center pt-2">
              Are you sure you want to delete <strong className="text-foreground">{jobToDelete?.displayId}</strong>?
              <br />
              This will abort any active tasks and remove the job from the queue.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJobToDelete(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => jobToDelete && void handleDelete(jobToDelete.id)}>
              Delete Job
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Master Emergency Pause/Resume Confirmation Modal */}
      <Dialog open={!!masterAction} onOpenChange={(open) => !open && setMasterAction(null)}>
        <DialogContent>
          <DialogHeader className="sm:text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-warning/10 mb-4">
              <AlertCircle className="size-6 text-warning" />
            </div>
            <DialogTitle className="text-center text-lg">
              {masterAction === "pause" ? "Pause All Active Jobs?" : "Resume All Paused Jobs?"}
            </DialogTitle>
            <DialogDescription className="text-center pt-2">
              {masterAction === "pause" ? (
                <>
                  This will suspend dispatching for all <strong className="text-foreground">{runningCount}</strong>{" "}
                  active rendering jobs on the farm.
                </>
              ) : (
                <>
                  This will resume dispatching for all <strong className="text-foreground">{pausedCount}</strong> paused
                  jobs in the queue.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMasterAction(null)} disabled={isExecutingMaster}>
              Cancel
            </Button>
            <Button
              variant={masterAction === "pause" ? "default" : "default"}
              className={masterAction === "pause" ? "bg-warning text-warning-foreground hover:bg-warning/90" : ""}
              onClick={() => void handleMasterBatchAction()}
              disabled={isExecutingMaster}
            >
              {isExecutingMaster ? (
                <Loader2 className="size-4 animate-spin mr-1.5" />
              ) : masterAction === "pause" ? (
                <Pause className="size-4 mr-1.5" />
              ) : (
                <Play className="size-4 mr-1.5" />
              )}
              {masterAction === "pause" ? "Pause All Active" : "Resume All Paused"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
