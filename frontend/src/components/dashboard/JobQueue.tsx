"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Play, Pause, MoreHorizontal, Loader2, CheckCircle2, XCircle, Clock, Trash2, Search } from "lucide-react";
import { toast } from "sonner";
import { deleteJob, pauseJob, resumeJob, formatApiError } from "@/services/api";
import type { RenderJob } from "@/types/dashboard";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
      <Card className="flex flex-col justify-between h-full border-border">
        <CardHeader>
          <CardTitle className="text-base font-bold text-foreground">Live Job Queue</CardTitle>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col">
          <div className="rounded-md border border-border overflow-hidden flex-1 flex flex-col">
            <div className="flex-1 overflow-auto">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow>
                    <TableHead className="w-[20%]">Job ID</TableHead>
                    <TableHead className="w-[10%] text-center">Priority</TableHead>
                    <TableHead className="w-[15%] text-center">User</TableHead>
                    <TableHead className="w-[15%] text-center">State</TableHead>
                    <TableHead className="w-[30%] text-center">Progress</TableHead>
                    <TableHead className="w-[10%] text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="text-xs font-mono">
                  {filteredJobs.length > 0 ? (
                    filteredJobs.map((job) => (
                      <TableRow key={job.id} className="hover:bg-muted/40 group transition-colors">
                        <TableCell className="font-medium text-foreground py-4">
                          <Link
                            className="text-primary hover:text-primary/80 transition-colors"
                            href={`/jobs/${job.id}`}
                          >
                            {job.displayId}
                          </Link>
                        </TableCell>
                        <TableCell className="text-center font-bold text-foreground py-4">{job.priority}</TableCell>
                        <TableCell className="text-muted-foreground text-center py-4">{job.user}</TableCell>
                        <TableCell className="text-center py-4">{getJobStateBadge(job.backendState)}</TableCell>
                        <TableCell className="text-center py-4">
                          <div className="flex items-center justify-center gap-3 w-full max-w-[200px] mx-auto">
                            <span className="text-xs text-muted-foreground w-8 text-right font-medium">
                              {job.progress}%
                            </span>
                            <Progress value={job.progress} className="h-[6px] flex-1 bg-input/50 rounded-full" />
                            <span className="text-[11px] text-muted-foreground text-left whitespace-nowrap w-12">
                              {job.taskCounts}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right py-4 pr-4">
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              render={
                                <Button variant="ghost" className="h-8 w-8 p-0">
                                  <span className="sr-only">Open menu</span>
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              }
                            />
                            <DropdownMenuContent align="end">
                              <DropdownMenuGroup>
                                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                                {job.backendState !== "FINISHED" && job.backendState !== "FAILED" && (
                                  <>
                                    <DropdownMenuItem
                                      onClick={() =>
                                        void handleTransition(
                                          job.id,
                                          job.backendState === "PAUSED" ? "resume" : "pause",
                                        )
                                      }
                                      disabled={actionJobId === job.id}
                                      className="cursor-pointer"
                                    >
                                      {job.backendState === "PAUSED" ? (
                                        <Play className="mr-2 h-4 w-4" />
                                      ) : (
                                        <Pause className="mr-2 h-4 w-4" />
                                      )}
                                      {job.backendState === "PAUSED" ? "Resume job" : "Pause job"}
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                  </>
                                )}
                                <DropdownMenuItem
                                  className="text-destructive focus:bg-destructive/10 focus:text-destructive cursor-pointer"
                                  onClick={() => setJobToDelete(job)}
                                  disabled={deletingJobId === job.id}
                                >
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  Delete job
                                </DropdownMenuItem>
                              </DropdownMenuGroup>
                            </DropdownMenuContent>
                          </DropdownMenu>
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
            </div>
          </div>
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
