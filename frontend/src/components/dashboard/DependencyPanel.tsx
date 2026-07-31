"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import {
  CheckCircle2,
  Clock,
  Link2,
  Loader2,
  Plus,
  Trash2,
  XCircle,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  LayoutList,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import { JobSelector, LayerSelector, TaskSelector } from "@/components/common/Selectors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DependencyFlow } from "@/components/dashboard/DependencyFlow";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  createDependency,
  deleteDependency,
  formatApiError,
  getJobDependencies,
  type CreateDependencyPayload,
  type Dependency,
  type DependencyType,
} from "@/services/api";

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function DependencyStatusBadge({ satisfied }: { satisfied: boolean }) {
  if (satisfied) {
    return (
      <Badge variant="success" className="gap-1.5">
        <CheckCircle2 className="size-3" />
        Satisfied
      </Badge>
    );
  }
  return (
    <Badge variant="warning" className="gap-1.5">
      <Clock className="size-3" />
      Pending
    </Badge>
  );
}

function DependencyTypeBadge({ type }: { type: DependencyType }) {
  const labels: Record<DependencyType, string> = {
    TASK_ON_TASK: "Task → Task",
    LAYER_ON_LAYER: "Layer → Layer",
    JOB_ON_JOB: "Job → Job",
  };
  return <Badge variant="outline">{labels[type]}</Badge>;
}

// ── Add Dependency Dialog ──────────────────────────────────────────────────────

interface AddDependencyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobId: string;
  onCreated: () => void;
}

function AddDependencyDialog({ open, onOpenChange, jobId, onCreated }: AddDependencyDialogProps) {
  const [type, setType] = useState<DependencyType>("JOB_ON_JOB");
  const [parentJobId, setParentJobId] = useState("");
  const [parentLayerId, setParentLayerId] = useState("");
  const [parentTaskId, setParentTaskId] = useState("");
  const [depLayerId, setDepLayerId] = useState("");
  const [depTaskId, setDepTaskId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!parentJobId.trim()) {
      toast.error("Parent Job ID is required.");
      return;
    }
    setIsSubmitting(true);
    try {
      // Automatically promote dependency type based on provided granular fields
      let finalType = type;
      if (depTaskId || parentTaskId) finalType = "TASK_ON_TASK";
      else if (depLayerId || parentLayerId) finalType = "LAYER_ON_LAYER";

      const payload: CreateDependencyPayload = {
        type: finalType,
        dep_job: jobId,
        parent_job: parentJobId.trim(),
        ...(finalType === "LAYER_ON_LAYER" && {
          dep_layer: depLayerId.trim() || null,
          parent_layer: parentLayerId.trim() || null,
        }),
        ...(finalType === "TASK_ON_TASK" && {
          dep_task: depTaskId.trim() || null,
          parent_task: parentTaskId.trim() || null,
          dep_layer: depLayerId.trim() || null,
          parent_layer: parentLayerId.trim() || null,
        }),
      };
      await createDependency(payload);
      toast.success("Dependency created successfully.");
      onCreated();
      onOpenChange(false);
      // Reset form
      setParentJobId("");
      setParentLayerId("");
      setParentTaskId("");
      setDepLayerId("");
      setDepTaskId("");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Link2 className="size-4" />
            Add Dependency
          </DialogTitle>
          <DialogDescription>
            This job will wait for the blocking entity to finish before its tasks become eligible for dispatch.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Type selector */}
          <div className="space-y-1.5">
            <Label htmlFor="dep-type-select">Dependency Type</Label>
            <select
              id="dep-type-select"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={type}
              onChange={(e) => setType(e.target.value as DependencyType)}
            >
              <option value="JOB_ON_JOB">Job on Job</option>
              <option value="LAYER_ON_LAYER">Layer on Layer</option>
              <option value="TASK_ON_TASK">Task on Task</option>
            </select>
          </div>

          {/* Blocking Job ID */}
          <div className="space-y-1.5">
            <Label htmlFor="parent-job-id">
              Blocking Job <span className="text-muted-foreground">(must finish first)</span>
            </Label>
            <JobSelector value={parentJobId} onChange={setParentJobId} />
          </div>

          {/* Layer fields */}
          {(type === "LAYER_ON_LAYER" || type === "TASK_ON_TASK") && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="parent-layer-id">Blocking Layer</Label>
                  <LayerSelector jobId={parentJobId} value={parentLayerId} onChange={setParentLayerId} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="dep-layer-id">This Layer</Label>
                  <LayerSelector jobId={jobId} value={depLayerId} onChange={setDepLayerId} />
                </div>
              </div>
            </>
          )}

          {/* Task fields */}
          {type === "TASK_ON_TASK" && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="parent-task-id">Blocking Task</Label>
                <TaskSelector
                  jobId={parentJobId}
                  layerId={parentLayerId}
                  value={parentTaskId}
                  onChange={setParentTaskId}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="dep-task-id">This Task</Label>
                <TaskSelector jobId={jobId} layerId={depLayerId} value={depTaskId} onChange={setDepTaskId} />
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
            Add Dependency
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Delete Confirmation Dialog ─────────────────────────────────────────────────

interface DeleteConfirmDialogProps {
  dep: Dependency | null;
  onClose: () => void;
  onDeleted: () => void;
}

function DeleteConfirmDialog({ dep, onClose, onDeleted }: DeleteConfirmDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    if (!dep) return;
    setIsDeleting(true);
    try {
      await deleteDependency(dep.id);
      toast.success("Dependency removed.");
      onDeleted();
      onClose();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Dialog open={!!dep} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <XCircle className="size-4" />
            Remove Dependency
          </DialogTitle>
          <DialogDescription>
            This will immediately allow the blocked tasks to be re-evaluated. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
            {isDeleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
            Remove
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

interface DependencyPanelProps {
  /** The UUID of the job whose dependencies are being managed. */
  jobId: string;
  /** Whether the current user is staff/superuser (controls delete access). */
  isStaff?: boolean;
}

export function DependencyPanel({ jobId, isStaff = false }: DependencyPanelProps) {
  const [deps, setDeps] = useState<Dependency[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Dependency | null>(null);

  const [inboundPage, setInboundPage] = useState(1);
  const [outboundPage, setOutboundPage] = useState(1);
  const PAGE_SIZE = 20;

  const inboundRef = useRef<HTMLDivElement>(null);
  const outboundRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (inboundRef.current) inboundRef.current.scrollTop = 0;
  }, [inboundPage]);

  useEffect(() => {
    if (outboundRef.current) outboundRef.current.scrollTop = 0;
  }, [outboundPage]);

  const loadDeps = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getJobDependencies(jobId);
      setDeps(data);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    loadDeps();
  }, [loadDeps]);

  const inbound = deps.filter((d) => d.dep_job === jobId);
  const outbound = deps.filter((d) => d.parent_job === jobId && d.dep_job !== jobId);

  const paginatedInbound = inbound.slice((inboundPage - 1) * PAGE_SIZE, inboundPage * PAGE_SIZE);
  const paginatedOutbound = outbound.slice((outboundPage - 1) * PAGE_SIZE, outboundPage * PAGE_SIZE);

  return (
    <Card className="border-border overflow-hidden p-0 gap-0">
      <Tabs variant="line" defaultValue="inbound" className="flex flex-col">
        <CardHeader className="p-4 pb-3 mb-0 border-b border-border/50">
          <CardTitle className="flex items-center justify-between text-sm font-bold w-full">
            <div className="flex items-center gap-2">
              <LayoutList size={16} className="text-destructive" />
              Job Dependencies
            </div>
            {isStaff && (
              <Button
                id="add-dependency-button"
                variant="outline"
                size="sm"
                className="h-7 text-xs bg-transparent hover:bg-muted -my-1"
                onClick={() => setIsAddOpen(true)}
              >
                <Plus className="size-3 mr-1.5" />
                Add Dependency
              </Button>
            )}
          </CardTitle>
        </CardHeader>
        <TabsList>
          <TabsTrigger value="inbound" className="text-xs px-3 py-1 gap-2">
            Waiting On
            {inbound.length > 0 && (
              <Badge variant="destructive" className="px-1.5 py-0 text-[10px] rounded-full h-4 min-w-4 justify-center font-normal">
                {inbound.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="outbound" className="text-xs px-3 py-1 gap-2">
            Blocking Others
            {outbound.length > 0 && (
              <Badge variant="secondary" className="px-1.5 py-0 text-[10px] rounded-full h-4 min-w-4 justify-center font-normal">
                {outbound.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>
        <CardContent className="p-0">
          <TabsContent value="inbound" className="m-0 border-none p-0 outline-none flex flex-col">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded-md" />
              ))}
            </div>
          ) : (
            <Table containerRef={inboundRef} containerClassName="max-h-[400px] overflow-y-auto">
              <TableHeader className="sticky top-0 z-10 shadow-sm bg-card">
                <TableRow className="hover:bg-transparent bg-muted/30">
                  <TableHead className="pl-6 font-semibold text-xs w-[35%]">Depends On</TableHead>
                  <TableHead className="font-semibold text-center text-xs">Type</TableHead>
                  <TableHead className="font-semibold text-center text-xs">Created</TableHead>
                  <TableHead className="font-semibold text-center text-xs">Satisfied</TableHead>
                  <TableHead className="font-semibold text-center text-xs">Status</TableHead>
                  {isStaff && <TableHead className="pr-6 font-semibold text-xs text-right">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {inbound.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={isStaff ? 6 : 5} className="h-24 text-center text-xs text-muted-foreground">
                      No inbound dependencies — this job runs freely.
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedInbound.map((dep) => (
                    <TableRow key={dep.id} className="hover:bg-muted/40 transition-colors group">
                      <TableCell className="pl-6 text-xs font-medium text-foreground py-2.5">
                        <DependencyFlow dep={dep} currentJobId={jobId} isInbound={true} />
                      </TableCell>
                      <TableCell className="text-center">
                        <DependencyTypeBadge type={dep.type} />
                      </TableCell>
                      <TableCell className="text-center text-xs text-muted-foreground">
                        {formatDate(dep.created_at)}
                      </TableCell>
                      <TableCell className="text-center text-xs text-muted-foreground">
                        {formatDate(dep.satisfied_at)}
                      </TableCell>
                      <TableCell className="text-center">
                        <DependencyStatusBadge satisfied={dep.is_satisfied} />
                      </TableCell>
                      {isStaff && (
                        <TableCell className="pr-6 text-right py-1">
                          {!dep.is_satisfied && (
                            <Button
                              id={`delete-dep-${dep.id}`}
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                              onClick={() => setPendingDelete(dep)}
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
          {inbound.length > PAGE_SIZE && (
            <div className="flex items-center justify-end space-x-2 py-2 px-4 border-t border-border/50 bg-muted/10">
              <span className="text-xs text-muted-foreground mr-2">
                Page {inboundPage} of {Math.ceil(inbound.length / PAGE_SIZE)}
              </span>
              <Button
                variant="outline"
                size="sm"
                className="h-7 w-7 p-0"
                disabled={inboundPage === 1}
                onClick={() => setInboundPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 w-7 p-0"
                disabled={inboundPage * PAGE_SIZE >= inbound.length}
                onClick={() => setInboundPage((p) => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
          </TabsContent>

          {/* Outbound: what is waiting on this job */}
          <TabsContent value="outbound" className="m-0 border-none p-0 outline-none flex flex-col">
            <Table containerRef={outboundRef} containerClassName="max-h-[250px] overflow-y-auto">
              <TableHeader className="sticky top-0 z-10 shadow-sm bg-card">
                <TableRow className="hover:bg-transparent bg-muted/30">
                  <TableHead className="pl-6 font-semibold text-xs w-[35%]">Blocks</TableHead>
                  <TableHead className="font-semibold text-center text-xs">Type</TableHead>
                  <TableHead className="font-semibold text-center text-xs">Created</TableHead>
                  <TableHead className="font-semibold text-center text-xs">Satisfied</TableHead>
                  <TableHead className="pr-6 font-semibold text-center text-xs">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedOutbound.map((dep) => (
                  <TableRow key={dep.id} className="hover:bg-muted/40 transition-colors group">
                    <TableCell className="pl-6 text-xs font-medium text-foreground py-2.5">
                      <DependencyFlow dep={dep} currentJobId={jobId} isInbound={false} />
                    </TableCell>
                    <TableCell className="text-center">
                      <DependencyTypeBadge type={dep.type} />
                    </TableCell>
                    <TableCell className="text-center text-xs text-muted-foreground">
                      {formatDate(dep.created_at)}
                    </TableCell>
                    <TableCell className="text-center text-xs text-muted-foreground">
                      {formatDate(dep.satisfied_at)}
                    </TableCell>
                    <TableCell className="pr-6 text-center">
                      <DependencyStatusBadge satisfied={dep.is_satisfied} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {outbound.length > PAGE_SIZE && (
              <div className="flex items-center justify-end space-x-2 py-2 px-4 border-t border-border/50 bg-muted/10">
                <span className="text-xs text-muted-foreground mr-2">
                  Page {outboundPage} of {Math.ceil(outbound.length / PAGE_SIZE)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={outboundPage === 1}
                  onClick={() => setOutboundPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={outboundPage * PAGE_SIZE >= outbound.length}
                  onClick={() => setOutboundPage((p) => p + 1)}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </TabsContent>
        </CardContent>
      </Tabs>

      {/* Dialogs */}
      <AddDependencyDialog open={isAddOpen} onOpenChange={setIsAddOpen} jobId={jobId} onCreated={loadDeps} />
      <DeleteConfirmDialog dep={pendingDelete} onClose={() => setPendingDelete(null)} onDeleted={loadDeps} />
    </Card>
  );
}
