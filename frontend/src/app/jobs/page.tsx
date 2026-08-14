"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { useCallback, useEffect, useMemo, useState, useRef, type ChangeEvent } from "react";
import {
  Pause,
  Play,
  RefreshCw,
  Trash2,
  Loader2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Clock,
  LayoutGrid,
  Link2,
  Edit3,
  AlertTriangle,
  Filter,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { SegmentedProgressBar } from "@/components/ui/segmented-progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageControlBar } from "@/components/common/PageControlBar";
import { TableSortHeader } from "@/components/common/TableSortHeader";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  deleteJob,
  formatApiError,
  getJobs,
  pauseJob,
  resumeJob,
  updateJob,
  type BackendJob,
  type JobFilters,
  type JobStateFilter,
} from "@/services/api";

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
          <AlertCircle size={12} /> {state}
        </Badge>
      );
  }
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

export default function JobsPage() {
  const [jobs, setJobs] = useState<BackendJob[]>([]);
  const [selectedState, setSelectedState] = useState<JobStateFilter | "">("");
  const [filters, setFilters] = useState<Omit<JobFilters, "state">>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [actionJobId, setActionJobId] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<BackendJob | null>(null);

  const [jobToEditPriority, setJobToEditPriority] = useState<BackendJob | null>(null);
  const [newPriority, setNewPriority] = useState<number>(50);

  const [sortConfig, setSortConfig] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.project) count++;
    if (filters.department) count++;
    if (filters.user) count++;
    return count;
  }, [filters]);

  const stateCounts = useMemo(() => {
    const counts: Record<string, number> = {
      RUNNING: 0,
      PENDING: 0,
      PAUSED: 0,
      FINISHED: 0,
      FAILED: 0,
    };
    for (const job of jobs) {
      if (job.state && counts[job.state] !== undefined) {
        counts[job.state]++;
      }
    }
    return counts;
  }, [jobs]);

  const stateChips: Array<{ id: JobStateFilter | ""; label: string; count: number; alert?: boolean }> = [
    { id: "", label: "All Jobs", count: jobs.length },
    { id: "RUNNING", label: "Running", count: stateCounts.RUNNING ?? 0 },
    { id: "PENDING", label: "Pending", count: stateCounts.PENDING ?? 0 },
    { id: "PAUSED", label: "Paused", count: stateCounts.PAUSED ?? 0 },
    { id: "FINISHED", label: "Finished", count: stateCounts.FINISHED ?? 0 },
    { id: "FAILED", label: "Failed", count: stateCounts.FAILED ?? 0, alert: (stateCounts.FAILED ?? 0) > 0 },
  ];

  const displayedJobs = useMemo(() => {
    if (!selectedState) return jobs;
    return jobs.filter((job) => job.state === selectedState);
  }, [jobs, selectedState]);

  const handleSort = (key: string) => {
    let nextConfig: { key: string; direction: "asc" | "desc" } | null = null;
    setSortConfig((current) => {
      let newDirection: "asc" | "desc" = "asc";
      if (current?.key === key) {
        if (current.direction === "asc") newDirection = "desc";
        else {
          nextConfig = null;
          return null;
        }
      }
      nextConfig = { key, direction: newDirection };
      return nextConfig;
    });
    setFilters((current) => ({
      ...current,
      ordering: nextConfig ? `${nextConfig.direction === "desc" ? "-" : ""}${nextConfig.key}` : undefined,
    }));
  };

  const fetchData = useCallback(
    async (showLoadingState = true): Promise<void> => {
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
    },
    [filters],
  );

  const initialLoad = useRef(true);

  useEffect(() => {
    if (!initialLoad.current) {
      setIsRefreshing(true);
    }
    const timer = window.setTimeout(() => {
      void fetchData(initialLoad.current);
      initialLoad.current = false;
    }, 300);
    return () => window.clearTimeout(timer);
  }, [fetchData]);

  const updateFilter =
    (key: keyof Omit<JobFilters, "state">) =>
    (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>): void => {
      const value = event.target.value;
      setFilters((current) => ({
        ...current,
        [key]: value || undefined,
      }));
    };

  const handleUpdatePriority = async (): Promise<void> => {
    if (!jobToEditPriority) return;
    setIsRefreshing(true);
    try {
      await updateJob(jobToEditPriority.id, { priority: newPriority });
      toast.success("Priority updated");
      setJobToEditPriority(null);
      await fetchData(false);
    } catch (error) {
      toast.error("Update failed", { description: formatApiError(error) });
    } finally {
      setIsRefreshing(false);
    }
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
    <div className="flex h-screen flex-col bg-background font-sans text-foreground overflow-hidden">
      <PageHeader title="Job Queue" description="Monitor, prioritize, and manage the render queue.">
        <Button variant="outline" onClick={() => void fetchData(false)} className="gap-2">
          <RefreshCw size={14} className={isLoading || isRefreshing ? "animate-spin" : ""} />
          Refresh
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {/* Page-level Control Bar: State Filters on Left, Search & Advanced Filters on Right */}
        <PageControlBar
          chips={stateChips.map((c) => ({
            id: c.id,
            label: c.label,
            count: c.count,
            alert: c.alert,
          }))}
          selectedChip={selectedState}
          onSelectChip={(id) => setSelectedState(id)}
          search={filters.search ?? ""}
          onSearchChange={(val) => updateFilter("search")({ target: { value: val } } as ChangeEvent<HTMLInputElement>)}
          searchPlaceholder="Search jobs, projects, users..."
          extraRight={
            <Popover>
              <PopoverTrigger
                className={cn(
                  "inline-flex shrink-0 items-center justify-center rounded-lg border border-border text-xs font-semibold whitespace-nowrap transition-all outline-none cursor-pointer h-8 gap-1.5 px-3 font-sans",
                  activeFilterCount > 0
                    ? "bg-primary/10 text-primary border-primary/40 hover:bg-primary/20"
                    : "bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Filter size={13} className={activeFilterCount > 0 ? "text-primary" : "text-muted-foreground"} />
                <span className="hidden sm:inline">Filters</span>
                {activeFilterCount > 0 && (
                  <span className="size-4.5 min-w-4.5 px-1 rounded-full bg-primary text-primary-foreground text-[11px] font-bold flex items-center justify-center leading-none">
                    {activeFilterCount}
                  </span>
                )}
              </PopoverTrigger>
              <PopoverContent
                align="end"
                className="w-[320px] p-4 border border-border bg-popover text-popover-foreground rounded-xl"
              >
                <div className="flex items-center justify-between border-b border-border/50 pb-2.5">
                  <div className="font-semibold text-xs flex items-center gap-2">
                    <Filter size={13} className="text-primary" />
                    Advanced Filters
                  </div>
                  {(filters.project || filters.department || filters.user) && (
                    <button
                      type="button"
                      onClick={() =>
                        setFilters((cur) => ({ ...cur, project: undefined, department: undefined, user: undefined }))
                      }
                      className="text-[10px] font-medium text-muted-foreground hover:text-destructive transition-colors flex items-center gap-1 bg-muted/40 hover:bg-destructive/10 px-2 py-0.5 rounded-md cursor-pointer"
                    >
                      <X size={10} /> Clear all
                    </button>
                  )}
                </div>

                <div className="space-y-3 pt-3">
                  <div className="space-y-1 group">
                    <label
                      htmlFor="filter-project"
                      className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5"
                    >
                      Project
                    </label>
                    <Input
                      id="filter-project"
                      value={filters.project ?? ""}
                      onChange={updateFilter("project")}
                      placeholder="e.g. Apollo"
                      className="h-8 text-xs bg-background border-border shadow-none"
                    />
                  </div>
                  <div className="space-y-1 group">
                    <label
                      htmlFor="filter-department"
                      className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5"
                    >
                      Department
                    </label>
                    <Input
                      id="filter-department"
                      value={filters.department ?? ""}
                      onChange={updateFilter("department")}
                      placeholder="e.g. Lighting"
                      className="h-8 text-xs bg-background border-border shadow-none"
                    />
                  </div>
                  <div className="space-y-1 group">
                    <label
                      htmlFor="filter-user"
                      className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5"
                    >
                      User
                    </label>
                    <Input
                      id="filter-user"
                      value={filters.user ?? ""}
                      onChange={updateFilter("user")}
                      placeholder="e.g. j.doe"
                      className="h-8 text-xs bg-background border-border shadow-none"
                    />
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          }
        />

        {/* Dedicated Table Card */}
        <Card className="flex flex-col border-border p-0 gap-0 overflow-hidden bg-card">
          <CardContent className="p-0 overflow-hidden">
            <Table className="table-fixed">
              <TableHeader className="bg-card sticky top-0 z-10 border-b border-border/50">
                <TableRow className="hover:bg-transparent bg-muted/30">
                  <TableHead className="w-[14%] pl-6">
                    <TableSortHeader
                      label="Job ID"
                      sortKey="name"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="left"
                    />
                  </TableHead>
                  <TableHead className="w-[9%]">
                    <TableSortHeader
                      label="State"
                      sortKey="state"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="w-[7%]">
                    <TableSortHeader
                      label="Priority"
                      sortKey="priority"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="w-[11%]">
                    <TableSortHeader
                      label="Project"
                      sortKey="project"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="w-[11%]">
                    <TableSortHeader
                      label="Department"
                      sortKey="department"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="w-[9%]">
                    <TableSortHeader
                      label="User"
                      sortKey="user"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="font-semibold text-center w-[9%] text-xs text-muted-foreground">
                    Pools
                  </TableHead>
                  <TableHead className="w-[8%]">
                    <TableSortHeader
                      label="Runtime"
                      sortKey="created_at"
                      currentSortKey={sortConfig?.key}
                      currentDirection={sortConfig?.direction}
                      onSort={handleSort}
                      align="center"
                    />
                  </TableHead>
                  <TableHead className="font-semibold text-center w-[14%] text-xs text-muted-foreground">
                    Tasks Progress
                  </TableHead>
                  <TableHead className="font-semibold text-right pr-6 w-[8%] text-xs text-muted-foreground">
                    Actions
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody
                className={cn(
                  "transition-opacity duration-200 text-xs",
                  isRefreshing && !isLoading && "opacity-50 pointer-events-none",
                )}
              >
                {isLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i} className="hover:bg-transparent">
                      <TableCell className="pl-6 py-3.5">
                        <Skeleton className="h-6 w-28" />
                      </TableCell>
                      <TableCell className="text-center py-3.5">
                        <Skeleton className="h-6 w-16 mx-auto" />
                      </TableCell>
                      <TableCell className="text-center py-3.5">
                        <Skeleton className="h-6 w-10 mx-auto" />
                      </TableCell>
                      <TableCell className="text-center py-3.5">
                        <Skeleton className="h-6 w-20 mx-auto" />
                      </TableCell>
                      <TableCell className="text-center py-3.5">
                        <Skeleton className="h-6 w-20 mx-auto" />
                      </TableCell>
                      <TableCell className="text-center py-3.5">
                        <Skeleton className="h-6 w-16 mx-auto" />
                      </TableCell>
                      <TableCell className="text-center py-3.5">
                        <Skeleton className="h-6 w-14 mx-auto" />
                      </TableCell>
                      <TableCell className="text-center py-3.5">
                        <Skeleton className="h-6 w-14 mx-auto" />
                      </TableCell>
                      <TableCell className="align-middle py-3.5 px-3">
                        <Skeleton className="h-3 w-full" />
                      </TableCell>
                      <TableCell className="pr-6 py-3.5">
                        <Skeleton className="h-7 w-14 ml-auto" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : displayedJobs.length > 0 ? (
                  displayedJobs.map((job) => {
                    return (
                      <TableRow key={job.id} className="hover:bg-muted/40 transition-colors group">
                        {/* Job ID */}
                        <TableCell className="pl-6 py-3 text-left font-medium">
                          <Link
                            className="text-primary hover:text-primary/80 font-bold transition-colors truncate block max-w-[180px]"
                            href={`/jobs/${job.id}`}
                            title={job.visible_name || job.name}
                          >
                            {job.visible_name || job.name}
                          </Link>
                        </TableCell>

                        {/* State */}
                        <TableCell className="text-center py-3">
                          <div className="flex flex-col items-center gap-1">
                            {getJobStateBadge(job.state)}
                            {(job.depend_tasks ?? 0) > 0 && (
                              <Tooltip>
                                <TooltipTrigger
                                  className={cn(
                                    badgeVariants({ variant: "warning" }),
                                    "gap-1 text-[10px] h-4 px-1.5 cursor-help",
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

                        {/* Priority */}
                        <TableCell className="text-center py-3">
                          <div className="flex justify-center items-center">
                            <Badge
                              variant="outline"
                              className="gap-1 text-xs h-5 px-2 cursor-pointer hover:bg-muted hover:border-primary/50 transition-colors font-mono font-bold"
                              onClick={() => {
                                setJobToEditPriority(job);
                                setNewPriority(job.priority ?? 50);
                              }}
                            >
                              {job.priority ?? 50}
                              <Edit3 size={10} className="text-muted-foreground ml-0.5" />
                            </Badge>
                          </div>
                        </TableCell>

                        {/* Project */}
                        <TableCell className="text-center py-3 font-medium text-foreground/90 truncate">
                          {job.project || "-"}
                        </TableCell>

                        {/* Department */}
                        <TableCell className="text-center py-3 text-muted-foreground truncate">
                          {job.department || "-"}
                        </TableCell>

                        {/* User */}
                        <TableCell className="text-center py-3 text-muted-foreground truncate">
                          {job.user || "-"}
                        </TableCell>

                        {/* Pools */}
                        <TableCell className="text-center py-3">
                          <div className="flex flex-wrap items-center justify-center gap-1">
                            {job.included_pools && job.included_pools.length > 0 ? (
                              job.included_pools.map((poolName) => (
                                <Badge
                                  key={poolName}
                                  variant="secondary"
                                  className="text-[10px] px-1.5 py-0 h-4 bg-muted/60 text-muted-foreground"
                                >
                                  {poolName}
                                </Badge>
                              ))
                            ) : (
                              <span className="text-xs text-muted-foreground/60">-</span>
                            )}
                          </div>
                        </TableCell>

                        {/* Runtime */}
                        <TableCell className="text-center py-3">
                          <div className="flex flex-col items-center gap-0.5 font-mono">
                            <div className="text-xs font-semibold text-foreground">{formatRuntime(job.created_at)}</div>
                          </div>
                        </TableCell>

                        {/* Tasks Progress */}
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

                        {/* Actions */}
                        <TableCell className="pr-6 py-3 text-right">
                          <div className="flex items-center justify-end gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
                            {job.state === "PAUSED" ? (
                              <Tooltip>
                                <TooltipTrigger
                                  render={
                                    <Button
                                      size="icon"
                                      variant="ghost"
                                      className="size-7 text-muted-foreground hover:text-success hover:bg-success/10"
                                      disabled={actionJobId === job.id}
                                      onClick={() => void handleTransition(job.id, "resume")}
                                      aria-label="Resume job"
                                    >
                                      <Play size={13} />
                                    </Button>
                                  }
                                />
                                <TooltipContent>Resume Job</TooltipContent>
                              </Tooltip>
                            ) : job.state === "RUNNING" || job.state === "PENDING" ? (
                              <Tooltip>
                                <TooltipTrigger
                                  render={
                                    <Button
                                      size="icon"
                                      variant="ghost"
                                      className="size-7 text-muted-foreground hover:text-warning hover:bg-warning/10"
                                      disabled={actionJobId === job.id}
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
                                    disabled={actionJobId === job.id}
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
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={10} className="h-44 text-center">
                      <div className="flex flex-col items-center justify-center p-6 text-center">
                        <div className="size-10 rounded-full bg-muted flex items-center justify-center mb-2">
                          <LayoutGrid size={20} className="text-muted-foreground/60" />
                        </div>
                        <p className="text-sm font-bold text-foreground">No render jobs found</p>
                        <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                          {selectedState
                            ? `There are currently no jobs with state "${selectedState}".`
                            : "There are no render jobs matching your current filters."}
                        </p>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!jobToDelete}
        onOpenChange={(open) => !open && setJobToDelete(null)}
        variant="destructive"
        title="Delete Render Job"
        description={
          <>
            Are you sure you want to delete{" "}
            <strong className="text-foreground">{jobToDelete?.visible_name || jobToDelete?.name}</strong>?<br />
            This will permanently delete the job and all associated layers and tasks. This action cannot be undone.
          </>
        }
        confirmText="Delete Job"
        isLoading={actionJobId === jobToDelete?.id}
        onConfirm={async () => {
          if (jobToDelete) {
            await handleRemoveJob(jobToDelete.id);
            setJobToDelete(null);
          }
        }}
      />

      {/* Edit Priority Dialog */}
      <Dialog open={!!jobToEditPriority} onOpenChange={(open) => !open && setJobToEditPriority(null)}>
        <DialogContent className="sm:max-w-[300px]">
          <DialogHeader>
            <DialogTitle>Edit Priority</DialogTitle>
            <DialogDescription>
              Update priority for job <strong className="text-foreground">{jobToEditPriority?.visible_name}</strong>.
            </DialogDescription>
          </DialogHeader>
          <div className="py-6 space-y-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center text-xs font-medium text-muted-foreground px-1">
                <span>Low</span>
                <span className="text-primary text-xl font-bold font-mono">{newPriority}</span>
                <span>Critical</span>
              </div>
              <input
                type="range"
                min="1"
                max="100"
                value={newPriority}
                aria-label="Job priority slider"
                onChange={(e) => setNewPriority(parseInt(e.target.value))}
                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: "Low", val: 10 },
                { label: "Normal", val: 50 },
                { label: "High", val: 80 },
                { label: "Critical", val: 100 },
              ].map((preset) => (
                <Button
                  key={preset.val}
                  variant={newPriority === preset.val ? "default" : "outline"}
                  size="sm"
                  className="h-8 text-xs px-1 font-medium"
                  onClick={() => setNewPriority(preset.val)}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJobToEditPriority(null)}>
              Cancel
            </Button>
            <Button onClick={() => void handleUpdatePriority()}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
