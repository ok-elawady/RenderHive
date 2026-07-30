"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, useRef, type ChangeEvent } from "react";
import { 
  Pause, Play, RefreshCw, Search, Trash2, 
  Loader2, CheckCircle2, AlertCircle, XCircle, Clock, LayoutGrid, Link2
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  deleteJob,
  formatApiError,
  getJobs,
  pauseJob,
  resumeJob,
  type BackendJob,
  type JobFilters,
  type JobStateFilter,
} from "@/services/api";

const jobStates: Array<JobStateFilter | ""> = [
  "",
  "PENDING",
  "RUNNING",
  "PAUSED",
  "FINISHED",
  "FAILED",
];

function getJobStateBadge(state: BackendJob["state"]) {
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
        <Badge variant="destructive" className="gap-1.5 font-medium pr-2 bg-destructive/15 text-destructive hover:bg-destructive/20">
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
        <Badge variant="secondary" className="gap-1.5 font-medium pr-2 bg-muted/60 text-muted-foreground hover:bg-muted">
          <Clock size={12} /> {state}
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary" className="gap-1.5 font-medium pr-2">
          <AlertCircle size={12} /> {state}
        </Badge>
      );
  }
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<BackendJob[]>([]);
  const [filters, setFilters] = useState<JobFilters>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [actionJobId, setActionJobId] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<BackendJob | null>(null);

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter(Boolean).length,
    [filters],
  );

  const fetchData = useCallback(async (showLoadingState = true): Promise<void> => {
    if (showLoadingState) setIsLoading(true);
    setIsRefreshing(true);
    try {
      setJobs(await getJobs(filters));
    } catch (error) {
      toast.error("Unable to load jobs", { description: formatApiError(error) });
    } finally {
      if (showLoadingState) setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [filters]);

  const initialLoad = useRef(true);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchData(initialLoad.current);
      initialLoad.current = false;
    }, 300);
    return () => window.clearTimeout(timer);
  }, [fetchData]);

  const updateFilter =
    (key: keyof JobFilters) =>
    (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>): void => {
      const value = event.target.value;
      setFilters((current) => ({
        ...current,
        [key]: value || undefined,
      }));
    };

  const handleTransition = async (jobId: string, action: "pause" | "resume"): Promise<void> => {
    setActionJobId(jobId);
    try {
      if (action === "pause") {
        await pauseJob(jobId);
      } else {
        await resumeJob(jobId);
      }
      toast.success(action === "pause" ? "Job paused" : "Job resumed");
      await fetchData(false);
    } catch (error) {
      toast.error("Job action failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  const handleRemoveJob = async (jobId: string): Promise<void> => {
    setActionJobId(jobId);
    try {
      await deleteJob(jobId);
      setJobs((currentJobs) => currentJobs.filter((job) => job.id !== jobId));
      toast.success("Job deleted");
      await fetchData(false);
    } catch (error) {
      toast.error("Delete failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader 
        title="Job Queue" 
        description="Monitor, prioritize, and manage the active render queue."
      >
        <Button variant="outline" onClick={() => void fetchData(false)} className="gap-2">
          <RefreshCw size={14} className={isLoading || isRefreshing ? "animate-spin" : ""} />
          Refresh
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">
          
          {/* Sleek Inline Filter Bar */}
          <div className="flex flex-col md:flex-row gap-3 items-center w-full bg-card/50 border border-border rounded-xl p-3 backdrop-blur-sm">
            <div className="flex items-center gap-2 pl-2 pr-4 border-r border-border/50 text-muted-foreground font-semibold text-sm">
              <Search size={16} />
              Filters
              {activeFilterCount > 0 && (
                <Badge variant="info" className="ml-1 px-1.5 py-0 rounded-full h-5 text-[10px]">
                  {activeFilterCount}
                </Badge>
              )}
            </div>
            <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 w-full">
              <Input
                value={filters.project ?? ""}
                onChange={updateFilter("project")}
                placeholder="Filter by Project"
                className="h-9 bg-input/40 border-transparent focus-visible:border-ring transition-colors shadow-none text-sm"
              />
              <Input
                value={filters.department ?? ""}
                onChange={updateFilter("department")}
                placeholder="Filter by Department"
                className="h-9 bg-input/40 border-transparent focus-visible:border-ring transition-colors shadow-none text-sm"
              />
              <select
                value={filters.state ?? ""}
                onChange={updateFilter("state")}
                className="h-9 w-full rounded-md border border-transparent bg-input/40 px-3 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring"
              >
                {jobStates.map((state) => (
                  <option key={state || "all"} value={state}>
                    {state || "All States"}
                  </option>
                ))}
              </select>
              <Input
                value={filters.user ?? ""}
                onChange={updateFilter("user")}
                placeholder="Filter by User"
                className="h-9 bg-input/40 border-transparent focus-visible:border-ring transition-colors text-sm"
              />
            </div>
          </div>

          <Card className="border-border overflow-hidden p-0 gap-0">
            <CardContent className="p-0">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="pl-6 font-semibold w-[20%]">Job ID</TableHead>
                    <TableHead className="font-semibold text-center w-[8%]">Priority</TableHead>
                    <TableHead className="font-semibold text-center w-[12%]">Project</TableHead>
                    <TableHead className="font-semibold text-center w-[12%]">Department</TableHead>
                    <TableHead className="font-semibold text-center w-[10%]">User</TableHead>
                    <TableHead className="font-semibold text-center w-[12%]">State</TableHead>
                    <TableHead className="font-semibold text-center w-[16%]">Progress</TableHead>
                    <TableHead className="font-semibold text-right pr-6 w-[10%]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    Array.from({ length: 5 }).map((_, i) => (
                      <TableRow key={i} className="hover:bg-transparent">
                        <TableCell className="pl-6 py-4"><Skeleton className="h-5 w-32" /></TableCell>
                        <TableCell className="text-center py-4"><Skeleton className="h-5 w-8 mx-auto" /></TableCell>
                        <TableCell className="text-center py-4"><Skeleton className="h-5 w-20 mx-auto" /></TableCell>
                        <TableCell className="py-4"><Skeleton className="h-5 w-24 mx-auto" /></TableCell>
                        <TableCell className="py-4"><Skeleton className="h-5 w-20 mx-auto" /></TableCell>
                        <TableCell className="py-4"><Skeleton className="h-6 w-24 rounded-full mx-auto" /></TableCell>
                        <TableCell className="align-middle py-4 px-4">
                          <div className="flex flex-col items-center gap-1.5">
                            <Skeleton className="h-3 w-full max-w-[120px]" />
                            <Skeleton className="h-1.5 w-full max-w-[120px]" />
                          </div>
                        </TableCell>
                        <TableCell className="pr-6 py-4"><Skeleton className="h-8 w-16 ml-auto" /></TableCell>
                      </TableRow>
                    ))
                  ) : jobs.length > 0 ? (
                    jobs.map((job) => {
                      const completed = job.succeeded_tasks + job.skipped_tasks;
                      const total = job.total_tasks || 1;
                      const percentage = Math.round((completed / total) * 100);
                      
                      return (
                        <TableRow key={job.id} className="hover:bg-muted/40 transition-colors group">
                          <TableCell className="pl-6 font-medium py-4">
                            <Link
                              className="text-primary hover:text-primary/80 transition-colors"
                              href={`/jobs/${job.id}`}
                            >
                              {job.visible_name || job.name}
                            </Link>
                          </TableCell>
                          <TableCell className="text-center font-bold text-foreground py-4">
                            {job.priority ?? 50}
                          </TableCell>
                          <TableCell className="text-center text-muted-foreground py-4">{job.project}</TableCell>
                          <TableCell className="text-center text-muted-foreground py-4">{job.department}</TableCell>
                          <TableCell className="text-center text-muted-foreground py-4">{job.user}</TableCell>
                          <TableCell className="text-center py-4">
                            <div className="flex flex-col items-center gap-1">
                              {getJobStateBadge(job.state)}
                              {(job.depend_tasks ?? 0) > 0 && (
                                <Badge
                                  id={`blocked-pill-${job.id}`}
                                  variant="warning"
                                  className="gap-1 text-[10px] h-4 px-1.5"
                                >
                                  <Link2 className="size-2.5" />
                                  {job.depend_tasks} blocked
                                </Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-center align-middle px-4 py-4">
                            <div className="flex items-center justify-center gap-3 w-full max-w-[200px] mx-auto">
                              <span className="text-xs text-muted-foreground w-8 text-right font-medium">{percentage}%</span>
                              <Progress value={percentage} className="h-1.5 flex-1 bg-input/50 rounded-full" />
                              <span className="text-[11px] text-muted-foreground text-left whitespace-nowrap w-12">
                                {completed}/{job.total_tasks}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell className="text-right pr-6 align-middle py-4">
                            <TooltipProvider delay={150}>
                              <div className="flex justify-end gap-1.5 transition-opacity">
                                <Tooltip>
                                  <TooltipTrigger render={
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className={
                                        job.state === "PAUSED"
                                          ? "h-8 w-8 text-muted-foreground hover:text-success hover:bg-success/10 border border-transparent hover:border-success/20"
                                          : "h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background border border-transparent hover:border-border"
                                      }
                                      disabled={
                                        actionJobId === job.id ||
                                        job.state === "FINISHED" ||
                                        job.state === "FAILED"
                                      }
                                      onClick={() =>
                                        void handleTransition(
                                          job.id,
                                          job.state === "PAUSED" ? "resume" : "pause"
                                        )
                                      }
                                    >
                                      {job.state === "PAUSED" ? <Play size={14} /> : <Pause size={14} />}
                                    </Button>
                                  } />
                                  <TooltipContent>
                                    {job.state === "PAUSED" ? "Resume Job" : "Pause Job"}
                                  </TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                  <TooltipTrigger render={
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 border border-transparent hover:border-destructive/20"
                                      disabled={actionJobId === job.id}
                                      onClick={() => setJobToDelete(job)}
                                    >
                                      <Trash2 size={14} />
                                    </Button>
                                  } />
                                  <TooltipContent>Delete Job</TooltipContent>
                                </Tooltip>
                              </div>
                            </TooltipProvider>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  ) : (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={7} className="h-[400px]">
                        <div className="flex flex-col items-center justify-center text-center h-full text-muted-foreground space-y-4">
                          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted/50 border border-border/50">
                            <LayoutGrid size={24} className="text-muted-foreground/60" />
                          </div>
                          <div className="space-y-1">
                            <h3 className="text-base font-semibold text-foreground">No jobs found</h3>
                            <p className="text-sm">There are no render jobs matching your current filters.</p>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!jobToDelete} onOpenChange={(open) => !open && setJobToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Render Job</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <strong className="text-foreground">{jobToDelete?.visible_name || jobToDelete?.name}</strong>? 
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
    </div>
  );
}
