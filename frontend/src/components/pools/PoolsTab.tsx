"use client";

import {
  type KeyboardEvent,
  useMemo,
  useState,
} from "react";
import {
  CalendarDays,
  ChevronRight,
  Loader2,
  Pencil,
  Trash2,
  Layers,
  Server,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageControlBar } from "@/components/common/PageControlBar";
import { TableSortHeader } from "@/components/common/TableSortHeader";
import {
  createPool,
  deletePool,
  formatApiError,
  updatePool,
  type WorkerPool,
} from "@/services/api";

import { CreatePoolForm } from "@/components/pools/CreatePoolForm";
import { EditPoolForm } from "@/components/pools/EditPoolForm";
import type { CreatePoolFormValues, UpdatePoolFormValues } from "@/components/pools/schema";

function formatDate(value: string | null): string {
  if (!value) return "Never";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

interface PoolsTabProps {
  pools: WorkerPool[];
  setPools: React.Dispatch<React.SetStateAction<WorkerPool[]>>;
  isLoading: boolean;
  isCreateOpen: boolean;
  setIsCreateOpen: (open: boolean) => void;
}

export function PoolsTab({ 
  pools, 
  setPools, 
  isLoading, 
  isCreateOpen, 
  setIsCreateOpen 
}: PoolsTabProps) {
  
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [sheetMode, setSheetMode] = useState<"view" | "edit">("view");
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [deletingPoolId, setDeletingPoolId] = useState<string | null>(null);
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);
  const [search, setSearch] = useState("");
  
  const [selectedPool, setSelectedPool] = useState<WorkerPool | null>(null);

  const handleSort = (key: string) => {
    setSortConfig(current => {
      if (current?.key === key) {
        if (current.direction === "asc") return { key, direction: "desc" };
        return null;
      }
      return { key, direction: "asc" };
    });
  };

  const sortedPools = useMemo(() => {
    let filtered = pools;
    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.description && p.description.toLowerCase().includes(q))
      );
    }
    
    if (!sortConfig) return filtered;

    return [...pools].sort((a, b) => {
      const aValue = String(a[sortConfig.key as keyof WorkerPool] || "").toLowerCase();
      const bValue = String(b[sortConfig.key as keyof WorkerPool] || "").toLowerCase();

      if (aValue < bValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [pools, sortConfig, search]);

  const handleRowKeyDown = (
    event: KeyboardEvent<HTMLTableRowElement>,
    selected: WorkerPool,
  ): void => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setSelectedPool(selected);
      setSheetMode("view");
    }
  };

  const handleCreateSubmit = async (data: CreatePoolFormValues): Promise<void> => {
    setIsCreating(true);
    
    try {
      const createdPool = await createPool({
        name: data.name.trim(),
        description: data.description?.trim(),
      });
      setPools((current) =>
        [...current, createdPool].sort((left, right) =>
          left.name.localeCompare(right.name),
        ),
      );
      setIsCreateOpen(false);
      setSelectedPool(createdPool);
      setSheetMode("view");
      toast.success("Worker pool created", {
        description: `${createdPool.name} is now available for routing jobs.`,
      });
    } catch (error) {
      toast.error("Unable to create pool", {
        description: formatApiError(error),
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleEditSubmit = async (data: UpdatePoolFormValues): Promise<void> => {
    if (!selectedPool) return;
    setIsUpdating(true);

    try {
      const updatedPool = await updatePool(selectedPool.id, {
        name: data.name.trim(),
        description: data.description?.trim(),
      });
      setPools((current) =>
        current.map((entry) => (entry.id === updatedPool.id ? updatedPool : entry)),
      );
      setSheetMode("view");
      setSelectedPool(updatedPool);
      toast.success("Pool updated", {
        description: `${updatedPool.name} has been modified successfully.`,
      });
    } catch (error) {
      toast.error("Unable to update pool", {
        description: formatApiError(error),
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async (selected: WorkerPool): Promise<void> => {
    setDeletingPoolId(selected.id);
    try {
      await deletePool(selected.id);
      setPools((current) => current.filter((entry) => entry.id !== selected.id));
      setSelectedPool(null);
      toast.success("Pool deleted", {
        description: `${selected.name} was permanently removed.`,
      });
    } catch (error) {
      toast.error("Unable to delete pool", {
        description: formatApiError(error),
      });
    } finally {
      setDeletingPoolId(null);
    }
  };

  return (
    <div className="flex-1 font-mono h-full flex flex-col space-y-4">
      {/* Control Bar: Matching Jobs and Nodes pages */}
      <PageControlBar
        chips={[{ id: "ALL", label: "All Pools", count: pools.length }]}
        selectedChip="ALL"
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search pools by name or description..."
      />

      {/* Main Pools Table Card */}
      <Card className="flex flex-col border-border p-0 gap-0 overflow-hidden bg-card">
        <CardContent className="p-0 overflow-hidden">
          <Table className="table-fixed">
            <TableHeader className="bg-card sticky top-0 z-10 border-b border-border/50">
              <TableRow className="hover:bg-transparent bg-muted/30">
                <TableHead className="w-[28%] pl-6">
                  <TableSortHeader
                    label="Pool Name"
                    sortKey="name"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[36%]">
                  <TableSortHeader
                    label="Description"
                    sortKey="description"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[16%]">
                  <TableSortHeader
                    label="Created"
                    sortKey="created_at"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="center"
                  />
                </TableHead>
                <TableHead className="w-[12%]">
                  <TableSortHeader
                    label="Nodes"
                    sortKey="worker_count"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="center"
                  />
                </TableHead>
                <TableHead className="font-semibold pr-6 text-right w-[8%] text-xs text-muted-foreground align-middle">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs">
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-44 text-center text-muted-foreground">
                    <Loader2 className="mx-auto mb-2 animate-spin text-primary" size={22} />
                    Loading worker pools...
                  </TableCell>
                </TableRow>
              ) : sortedPools.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-44 text-center text-muted-foreground">
                    No worker pools found.
                  </TableCell>
                </TableRow>
              ) : (
                sortedPools.map((item) => (
                  <TableRow
                    key={item.id}
                    tabIndex={0}
                    className="group cursor-pointer hover:bg-muted/40 transition-colors focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                    onClick={() => { setSelectedPool(item); setSheetMode("view"); }}
                    onKeyDown={(event) => handleRowKeyDown(event, item)}
                    aria-label={`View ${item.name}`}
                  >
                    <TableCell className="pl-6 py-3 text-left">
                      <span className="font-bold text-foreground">
                        {item.name}
                      </span>
                    </TableCell>
                    <TableCell className="py-3 text-muted-foreground truncate max-w-[240px]">
                      {item.description || "No description provided"}
                    </TableCell>
                    <TableCell className="py-3 text-muted-foreground text-center">
                      {new Intl.DateTimeFormat("en", { dateStyle: "short" }).format(new Date(item.created_at))}
                    </TableCell>
                    <TableCell className="py-3 text-center">
                      <Badge variant="secondary" className="font-mono gap-1.5 px-2 bg-primary/10 text-primary hover:bg-primary/20 border-primary/20 text-[11px] h-5">
                        <Server size={11} />
                        {item.worker_count ?? 0} Nodes
                      </Badge>
                    </TableCell>
                    <TableCell className="pr-6 py-3 text-right">
                      <ChevronRight className="ml-auto text-muted-foreground group-hover:text-foreground transition-colors" size={16} />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Edit Profile / Details Sheet */}
      <Sheet open={selectedPool !== null} onOpenChange={(open) => !open && setSelectedPool(null)}>
        <SheetContent className="w-full border-border bg-card sm:max-w-md flex flex-col h-full overflow-hidden p-0">
          {selectedPool && (
            <>
              <SheetHeader className="border-b border-border p-6 shrink-0">
                <SheetTitle className="text-xl font-black">
                  {selectedPool.name}
                </SheetTitle>
                <SheetDescription className="mt-1.5 leading-relaxed">
                  {selectedPool.description || "Worker pool for job routing"}
                </SheetDescription>
              </SheetHeader>
              
              <div className="flex-1 overflow-y-auto p-6 flex flex-col">
                {sheetMode === "edit" ? (
                  <EditPoolForm
                    pool={selectedPool}
                    onSubmit={handleEditSubmit}
                    onCancel={() => setSheetMode("view")}
                    isSubmitting={isUpdating}
                  />
                ) : (
                  <div className="space-y-5 flex flex-col flex-1">
                    <div className="grid gap-4 pt-1">
                      <div className="flex items-start gap-3">
                        <Layers className="mt-0.5 text-primary" size={16} />
                        <div>
                          <p className="text-xs text-muted-foreground">Description</p>
                          <p className="mt-1 break-words text-sm text-foreground leading-relaxed">
                            {selectedPool.description || "No description provided"}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <CalendarDays className="mt-0.5 text-primary" size={16} />
                        <div>
                          <p className="text-xs text-muted-foreground">Date Created</p>
                          <p className="mt-1 text-sm text-foreground">{formatDate(selectedPool.created_at)}</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3 border-t border-border pt-4">
                        <Server className="mt-0.5 text-primary" size={16} />
                        <div className="w-full">
                          <p className="text-xs text-muted-foreground mb-2">Worker Nodes ({selectedPool.worker_count ?? 0})</p>
                          {selectedPool.workers && selectedPool.workers.length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {selectedPool.workers.map((workerName: string) => (
                                <Badge key={workerName} variant="secondary" className="font-mono text-xs px-2 py-0.5">
                                  {workerName}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-muted-foreground">No worker nodes assigned to this pool.</p>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="border-t border-border pt-5 mt-4">
                      <p className="text-xs uppercase text-muted-foreground">Actions</p>
                      <div className="mt-3">
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={() => setSheetMode("edit")}
                        >
                          <Pencil size={15} className="mr-2" />
                          Edit Pool
                        </Button>
                      </div>
                    </div>

                    <div className="pt-6 mt-auto">
                      <ConfirmDialog
                        variant="destructive"
                        title="Delete Worker Pool"
                        description={
                          <>
                            Are you sure you want to delete{" "}
                            <span className="font-semibold text-foreground">
                              {selectedPool.name}
                            </span>
                            ? This will not affect active jobs, but nodes in this pool will no longer be targeted using this pool name.
                          </>
                        }
                        confirmText="Delete Pool"
                        isLoading={deletingPoolId === selectedPool.id}
                        onConfirm={() => handleDelete(selectedPool)}
                        trigger={
                          <Button
                            variant="ghost"
                            className="w-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                            disabled={deletingPoolId === selectedPool.id}
                          >
                            <Trash2 size={15} className="mr-2" />
                            Delete Worker Pool
                          </Button>
                        }
                      />
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      {/* Add New Pool Sheet */}
      <Sheet
        open={isCreateOpen}
        onOpenChange={(open) => {
          if (!isCreating) setIsCreateOpen(open);
        }}
      >
        <SheetContent className="w-full border-border bg-card sm:max-w-md flex flex-col h-full overflow-hidden p-0">
          <SheetHeader className="border-b border-border p-6 shrink-0">
            <SheetTitle className="text-xl font-black">
              Add New Pool
            </SheetTitle>
            <SheetDescription className="mt-1.5 leading-relaxed">
              Create a new worker pool for dispatching jobs to specific sets of nodes.
            </SheetDescription>
          </SheetHeader>
          <div className="flex-1 overflow-y-auto p-6">
            <CreatePoolForm
              onSubmit={handleCreateSubmit}
              onCancel={() => setIsCreateOpen(false)}
              isSubmitting={isCreating}
            />
          </div>
        </SheetContent>
      </Sheet>

    </div>
  );
}
