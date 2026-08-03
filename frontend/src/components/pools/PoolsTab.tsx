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
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  DatabaseZap,
  Server,
  Network,
  Search
} from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  isRefreshing: boolean;
  isCreateOpen: boolean;
  setIsCreateOpen: (open: boolean) => void;
}

export function PoolsTab({ 
  pools, 
  setPools, 
  isLoading, 
  isRefreshing, 
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

  const renderSortIcon = (key: string) => {
    if (sortConfig?.key !== key) return <ArrowUpDown className="ml-2 size-4 opacity-50 group-hover:opacity-100 transition-opacity" />;
    if (sortConfig.direction === "asc") return <ArrowUp className="ml-2 size-4 text-primary" />;
    return <ArrowDown className="ml-2 size-4 text-primary" />;
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

  const counts = useMemo(
    () => ({
      total: pools.length,
    }),
    [pools],
  );

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
    <div className="flex-1 font-mono h-full flex flex-col">
      <div className="space-y-6">
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Total Pools
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-3xl font-black tracking-tight text-foreground">{counts.total}</p>
              <p className="text-xs font-mono text-primary flex items-center gap-1.5">
                <DatabaseZap size={14} /> Active clusters
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Capacity Planning
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-3xl font-black tracking-tight text-foreground">Dynamic</p>
              <p className="text-xs font-mono text-info flex items-center gap-1.5">
                <Server size={14} /> Auto-scaling ready
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Routing
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-3xl font-black tracking-tight text-foreground">Enabled</p>
              <p className="text-xs font-mono text-success flex items-center gap-1.5">
                <Network size={14} /> Tag-based dispatch
              </p>
            </CardContent>
          </Card>
        </section>

        <div className="flex items-center gap-4 mt-8 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by pool name or description..."
              className="pl-9 h-10 bg-card border-border/50 shadow-none font-sans"
            />
          </div>
        </div>

        <Card className="border-border overflow-hidden bg-card/80 backdrop-blur-sm p-0">
          <CardContent className="p-0">
            <Table>
              <TableHeader className="bg-muted/30">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[30%] pl-4">
                    <Button variant="ghost" size="sm" onClick={() => handleSort('name')} className="font-semibold flex items-center group -ml-3">
                      Pool Name
                      {renderSortIcon('name')}
                    </Button>
                  </TableHead>
                  <TableHead className="w-[35%]">
                    <div className="flex justify-start w-full pl-2">
                      <Button variant="ghost" size="sm" onClick={() => handleSort('description')} className="font-semibold flex items-center group">
                        Description
                        {renderSortIcon('description')}
                      </Button>
                    </div>
                  </TableHead>
                  <TableHead className="w-[15%]">
                    <div className="flex justify-center w-full">
                      <Button variant="ghost" size="sm" onClick={() => handleSort('created_at')} className="font-semibold flex items-center group">
                        Created
                        {renderSortIcon('created_at')}
                      </Button>
                    </div>
                  </TableHead>
                  <TableHead className="w-[10%]">
                    <div className="flex justify-center w-full">
                      <Button variant="ghost" size="sm" onClick={() => handleSort('worker_count')} className="font-semibold flex items-center group">
                        Nodes
                        {renderSortIcon('worker_count')}
                      </Button>
                    </div>
                  </TableHead>
                  <TableHead className="font-semibold pr-6 text-right w-[10%] align-middle">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                      <Loader2 className="mx-auto mb-2 animate-spin text-primary" size={22} />
                      Loading worker pools...
                    </TableCell>
                  </TableRow>
                ) : sortedPools.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
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
                      <TableCell className="pl-6 py-4 text-left">
                        <span className="font-bold text-foreground flex items-center gap-2">
                          <Layers size={14} className="text-primary" />
                          {item.name}
                        </span>
                      </TableCell>
                      <TableCell className="py-4 text-muted-foreground pl-5 truncate max-w-[200px]">
                        {item.description || "No description provided"}
                      </TableCell>
                      <TableCell className="py-4 text-muted-foreground text-center">
                        {new Intl.DateTimeFormat("en", { dateStyle: "short" }).format(new Date(item.created_at))}
                      </TableCell>
                      <TableCell className="py-4 text-center">
                        <Badge variant="secondary" className="font-mono gap-1.5 px-2 bg-primary/10 text-primary hover:bg-primary/20 border-primary/20">
                          <Server size={12} />
                          {item.worker_count ?? 0} Nodes
                        </Badge>
                      </TableCell>
                      <TableCell className="pr-6 py-4 text-right">
                        <ChevronRight className="ml-auto text-muted-foreground group-hover:text-foreground transition-colors" size={16} />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Edit Profile / Details Sheet */}
      <Sheet open={selectedPool !== null} onOpenChange={(open) => !open && setSelectedPool(null)}>
        <SheetContent className="w-full border-border bg-card sm:max-w-md flex flex-col h-full overflow-hidden p-0">
          {selectedPool && (
            <>
              <SheetHeader className="border-b border-border p-6 shrink-0 bg-muted/20">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
                    <Layers size={20} />
                  </div>
                </div>
                <SheetTitle className="text-xl font-black">
                  {selectedPool.name}
                </SheetTitle>
                <SheetDescription className="mt-1.5 leading-relaxed">
                  Worker Pool ID: {selectedPool.id.substring(0, 8)}...
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
                    <div className="grid gap-4 pt-2">
                      <div className="flex items-start gap-3">
                        <Layers className="mt-0.5 text-primary" size={16} />
                        <div>
                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Description</p>
                          <p className="mt-1 break-words text-sm text-foreground/90 leading-relaxed">
                            {selectedPool.description || "No description provided"}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3 mt-2">
                        <CalendarDays className="mt-0.5 text-primary" size={16} />
                        <div>
                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Created</p>
                          <p className="mt-1 text-sm text-foreground/90">{formatDate(selectedPool.created_at)}</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3 mt-2">
                        <CalendarDays className="mt-0.5 text-primary" size={16} />
                        <div>
                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Last Updated</p>
                          <p className="mt-1 text-sm text-foreground/90">{formatDate(selectedPool.updated_at)}</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3 mt-4 pt-4 border-t border-border">
                        <Server className="mt-0.5 text-primary" size={16} />
                        <div className="w-full">
                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Worker Machines ({selectedPool.worker_count ?? 0})</p>
                          {selectedPool.workers && selectedPool.workers.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                              {selectedPool.workers.map((workerName: string) => (
                                <span key={workerName} className="font-mono bg-muted/50 border border-border px-2 py-1 rounded text-xs">
                                  {workerName}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-muted-foreground">No worker machines assigned to this pool.</p>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="border-t border-border pt-5 mt-4">
                      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Actions</p>
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        <Button
                          variant="outline"
                          className="w-full justify-start"
                          onClick={() => setSheetMode("edit")}
                        >
                          <Pencil size={15} className="mr-3" />
                          Edit Pool Configuration
                        </Button>
                      </div>
                    </div>

                    <div className="pt-6 mt-auto">
                      <AlertDialog>
                        <AlertDialogTrigger
                          render={
                            <Button
                              variant="ghost"
                              className="w-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors justify-start"
                              disabled={deletingPoolId === selectedPool.id}
                            />
                          }
                        >
                          {deletingPoolId === selectedPool.id ? (
                            <Loader2 className="animate-spin mr-3" size={15} />
                          ) : (
                            <Trash2 size={15} className="mr-3" />
                          )}
                          Delete Worker Pool
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete Worker Pool</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete{" "}
                              <span className="font-semibold text-foreground">
                                {selectedPool.name}
                              </span>
                              ? This will not affect active jobs, but nodes in this pool will no longer be targeted using this pool name.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              variant="destructive"
                              onClick={() => handleDelete(selectedPool)}
                            >
                              Delete Pool
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
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
          <SheetHeader className="border-b border-border p-6 shrink-0 bg-muted/20">
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
