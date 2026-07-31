"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { Play, Pause, MoreHorizontal, Loader2, CheckCircle2, XCircle, Clock, Trash2, Search, Link2 } from "lucide-react";
import { toast } from "sonner";
import { deleteJob, pauseJob, resumeJob, formatApiError } from "@/services/api";
import type { RenderJob } from "@/types/dashboard";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { SegmentedProgressBar } from "@/components/ui/segmented-progress";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface JobQueueProps {
  jobs: RenderJob[];
  searchQuery: string;
  onJobRemoved: () => Promise<void>;
}

function matchesJobSearch(job: RenderJob, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;

  return [job.id, job.displayId, job.user, job.backendState].some((value) =>
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

const getJobStateBadge = (state: string) => {
  switch (state) {
    case "RUNNING":
      return (
        <Badge variant="info" className="gap-1.5 font-medium pr-2">
          <Loader2 className="animate-spin" size={12} /> {state}
        </Badge>
      );
    case "FINISHED":
    case "COMPLETED":
      return (
        <Badge variant="success" className="gap-1.5 font-medium pr-2 bg-success/15 text-success hover:bg-success/20">
          <CheckCircle2 size={12} /> {state}
        </Badge>
      );
    case "FAILED":
    case "ERROR":
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
          <Pause size={12} /> {state}
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
  const router = useRouter();
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null);
  const [actionJobId, setActionJobId] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<RenderJob | null>(null);

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredJobs = useMemo<RenderJob[]>(
    () => jobs.filter((job) => matchesJobSearch(job, normalizedQuery)),
    [jobs, normalizedQuery],
  );

  const handleRemoveJob = async (jobId: string): Promise<void> => {
    setDeletingJobId(jobId);

    try {
      await deleteJob(jobId);
      await onJobRemoved();
      router.refresh();
      toast.success("Job deleted");
    } catch (error) {
      toast.error("Delete failed", {
        description: formatApiError(error),
      });
    } finally {
      setDeletingJobId(null);
    }
  };

  const handleTransition = async (jobId: string, action: "pause" | "resume") => {
    setActionJobId(jobId);
    try {
      if (action === "pause") {
        await pauseJob(jobId);
        toast.success("Job paused");
      } else {
        await resumeJob(jobId);
        toast.success("Job resumed");
      }
      await onJobRemoved(); // Refresh dashboard data
    } catch (error) {
      toast.error(`Failed to ${action} job`, { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  return (
    <>
      <Card className="flex flex-col justify-between h-full border-border p-0 gap-0">
        <CardHeader className="p-4 pb-3 border-b border-border/50">
          <CardTitle className="text-base font-bold text-foreground">Live Job Queue</CardTitle>
        </CardHeader>

        <CardContent className="flex-1 p-0 overflow-hidden">
          <Table className="table-fixed" containerClassName="h-full overflow-auto">
              <TableHeader className="bg-card sticky top-0 z-10 shadow-sm">
                <TableRow className="hover:bg-transparent bg-muted/30">
                  <TableHead className="pl-6 w-[35%] font-semibold">Job ID / Project</TableHead>
                  <TableHead className="w-[12%] text-center font-semibold">State</TableHead>
                  <TableHead className="w-[10%] text-center font-semibold">Priority</TableHead>
                  <TableHead className="w-[20%] text-center font-semibold">Runtime</TableHead>
                  <TableHead className="pr-6 w-[23%] text-center font-semibold">Tasks Progress</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="text-xs">
                {filteredJobs.length > 0 ? (
                  filteredJobs.map((job) => (
                    <TableRow key={job.id} className="hover:bg-muted/40 transition-colors group">
                      <TableCell className="pl-6 py-4">
                        <div className="flex flex-col gap-1">
                          <Link
                            className="font-semibold text-primary hover:text-primary/80 transition-colors truncate"
                            href={`/jobs/${job.id}`}
                          >
                            {job.displayId}
                          </Link>
                          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                            <span className="font-medium text-foreground/80">{job.project}</span>
                            <span className="opacity-50">•</span>
                            <span>{job.department}</span>
                            <span className="opacity-50">•</span>
                            <span>{job.user}</span>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-center py-4">
                        <div className="flex flex-col items-center gap-1.5">
                          {getJobStateBadge(job.backendState)}
                          {(job.depend_tasks ?? 0) > 0 && (
                            <TooltipProvider delayDuration={150}>
                              <Tooltip>
                                <TooltipTrigger className={cn(badgeVariants({ variant: "warning" }), "gap-1 text-[10px] h-4 px-1.5 cursor-help")}>
                                  <Link2 className="size-2.5" />
                                  {job.depend_tasks} blocked
                                </TooltipTrigger>
                                <TooltipContent side="top">
                                  <p>Waiting on {job.depend_tasks} upstream task{job.depend_tasks !== 1 ? 's' : ''} to complete.</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-center py-4">
                        <Badge variant="outline" className="text-xs h-5 px-2 font-bold tracking-wide">
                          {job.priority}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center py-4">
                        <div className="flex flex-col items-center gap-1">
                          <div className="text-xs font-semibold text-foreground">
                            {formatRuntime(job.created_at)}
                          </div>
                          {job.created_at && (
                            <div className="text-[10px] text-muted-foreground whitespace-nowrap">
                              {new Date(job.created_at).toLocaleString([], {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-center py-4 pr-6">
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
                      </TableRow>
                    ))
                  ) : (
                    <TableRow className="hover:bg-transparent border-0">
                      <TableCell colSpan={6} className="h-32 text-center">
                        <div className="flex flex-col items-center justify-center">
                          <Search size={34} className="mb-3 text-primary opacity-25" />
                          <p className="text-sm font-bold text-foreground">No matching active render jobs found</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Try a Job ID, node name, or status keyword.
                          </p>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
        </CardContent>
      </Card>

      <Dialog open={!!jobToDelete} onOpenChange={(open) => !open && setJobToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Render Job</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <strong className="text-foreground">{jobToDelete?.displayId}</strong>?
              This will permanently delete the job and all associated layers and tasks. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJobToDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (jobToDelete) {
                  void handleRemoveJob(jobToDelete.id);
                  setJobToDelete(null);
                }
              }}
            >
              Delete Job
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
