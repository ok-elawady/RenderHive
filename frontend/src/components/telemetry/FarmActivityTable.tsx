"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Copy,
  Info,
  Layers,
  Search,
  Server,
  Terminal,
  User as UserIcon,
} from "lucide-react";
import type { FarmEvent } from "@/types/dashboard";
import { fetchFarmEvents } from "@/services/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { PageControlBar, type FilterChip } from "@/components/common/PageControlBar";
import { TableSortHeader } from "@/components/common/TableSortHeader";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type SeverityFilter = "ALL" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

function getSeverityBadge(severity: string) {
  switch (severity) {
    case "CRITICAL":
      return (
        <Badge
          variant="destructive"
          className="bg-rose-600/20 text-rose-400 border-rose-500/40 text-[10px] font-mono h-5 px-1.5 inline-flex items-center gap-1"
        >
          <AlertOctagon className="size-3" /> CRIT
        </Badge>
      );
    case "ERROR":
      return (
        <Badge
          variant="destructive"
          className="bg-destructive/15 text-destructive border-destructive/30 text-[10px] font-mono h-5 px-1.5 inline-flex items-center gap-1"
        >
          <AlertCircle className="size-3" /> ERR
        </Badge>
      );
    case "WARNING":
      return (
        <Badge
          variant="outline"
          className="bg-warning/15 text-warning border-warning/30 text-[10px] font-mono h-5 px-1.5 inline-flex items-center gap-1"
        >
          <AlertTriangle className="size-3" /> WARN
        </Badge>
      );
    default:
      return (
        <Badge
          variant="outline"
          className="bg-info/10 text-info border-info/30 text-[10px] font-mono h-5 px-1.5 inline-flex items-center gap-1"
        >
          <Info className="size-3" /> INFO
        </Badge>
      );
  }
}

function formatEventTime(isoString?: string): string {
  if (!isoString) return "--:--:--";
  const date = new Date(isoString);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatEventDate(isoString?: string): string {
  if (!isoString) return "";
  const date = new Date(isoString);
  return date.toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function getTargetDisplayName(evt: FarmEvent): { label: string; isHost: boolean } {
  // 1. Direct backend target_display or target_name
  if (evt.target_display && evt.target_display.trim()) {
    return { label: evt.target_display.trim(), isHost: evt.target_type === "worker" };
  }
  if (evt.target_name && evt.target_name.trim()) {
    return { label: evt.target_name.trim(), isHost: evt.target_type === "worker" };
  }

  const payload = (evt.payload && typeof evt.payload === "object" ? evt.payload : {}) as Record<string, unknown>;

  // 2. Check payload for worker hostname
  const host = payload.hostname || payload.worker_hostname || payload.worker_name || payload.worker || payload.node;
  if (typeof host === "string" && host.trim()) {
    return { label: host.trim(), isHost: true };
  }

  // 3. Check for human-readable job name or visible name
  const jobName = payload.job_name || payload.visible_name || payload.job;
  if (typeof jobName === "string" && jobName.trim()) {
    return { label: jobName.trim(), isHost: false };
  }

  // 4. Check if target_id itself is a hostname (short string without standard UUID dashes)
  if (evt.target_id && !evt.target_id.includes("-") && evt.target_id.length < 32) {
    return { label: evt.target_id, isHost: true };
  }

  // 5. Target ID fallback (shortened if UUID)
  if (evt.target_id) {
    const shortId = evt.target_id.length > 8 ? evt.target_id.slice(0, 8) : evt.target_id;
    const prefix = evt.target_type ? `${evt.target_type}:` : "";
    return { label: `${prefix}${shortId}`, isHost: false };
  }

  return { label: "Cluster Wide", isHost: false };
}

export function FarmActivityTable() {
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedEvent, setSelectedEvent] = useState<FarmEvent | null>(null);
  const [hasCopied, setHasCopied] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);
  const [sortConfig, setSortConfig] = useState<{
    key: string;
    direction: "asc" | "desc";
  }>({
    key: "created_at",
    direction: "desc",
  });

  const {
    data: allEvents = [],
    isLoading,
    isValidating,
    error: fetchError,
  } = useSWR<FarmEvent[]>("/api/telemetry/events/?limit=100", () => fetchFarmEvents(100), {
    refreshInterval: 10000,
    dedupingInterval: 3000,
    revalidateOnFocus: true,
  });

  const chips: FilterChip<SeverityFilter>[] = useMemo(() => {
    const infoCount = allEvents.filter((e) => e.severity === "INFO").length;
    const warnCount = allEvents.filter((e) => e.severity === "WARNING").length;
    const errCount = allEvents.filter((e) => e.severity === "ERROR" || e.severity === "CRITICAL").length;
    return [
      { id: "ALL", label: "All", count: allEvents.length },
      { id: "INFO", label: "Info", count: infoCount },
      { id: "WARNING", label: "Warn", count: warnCount },
      { id: "ERROR", label: "Error", count: errCount, alert: errCount > 0 },
    ];
  }, [allEvents]);

  const handleSort = (key: string) => {
    setSortConfig((cur) => ({
      key,
      direction: cur.key === key && cur.direction === "desc" ? "asc" : "desc",
    }));
  };

  const filteredAndSortedEvents = useMemo(() => {
    let result = allEvents;

    if (severityFilter === "ERROR") {
      result = result.filter((e) => e.severity === "ERROR" || e.severity === "CRITICAL");
    } else if (severityFilter !== "ALL") {
      result = result.filter((e) => e.severity === severityFilter);
    }

    const q = searchQuery.trim().toLowerCase();
    if (q) {
      result = result.filter((e) => {
        const targetInfo = getTargetDisplayName(e);
        return (
          String(e.event_type || "").toLowerCase().includes(q) ||
          String(e.message || "").toLowerCase().includes(q) ||
          targetInfo.label.toLowerCase().includes(q) ||
          (Boolean(e.actor_username) && String(e.actor_username).toLowerCase().includes(q)) ||
          (Boolean(e.target_type) && String(e.target_type).toLowerCase().includes(q)) ||
          (Boolean(e.target_id) && String(e.target_id).toLowerCase().includes(q))
        );
      });
    }

    // Apply Sorting
    return [...result].sort((a, b) => {
      let valA: any = "";
      let valB: any = "";

      if (sortConfig.key === "created_at") {
        valA = new Date(a.created_at).getTime();
        valB = new Date(b.created_at).getTime();
      } else if (sortConfig.key === "severity") {
        valA = String(a.severity || "");
        valB = String(b.severity || "");
      } else if (sortConfig.key === "event_type") {
        valA = String(a.event_type || "");
        valB = String(b.event_type || "");
      } else if (sortConfig.key === "target_id") {
        valA = getTargetDisplayName(a).label;
        valB = getTargetDisplayName(b).label;
      } else if (sortConfig.key === "message") {
        valA = String(a.message || "");
        valB = String(b.message || "");
      }

      if (valA < valB) return sortConfig.direction === "asc" ? -1 : 1;
      if (valA > valB) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [allEvents, severityFilter, searchQuery, sortConfig]);

  const totalPages = Math.max(1, Math.ceil(filteredAndSortedEvents.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const startIndex = (safePage - 1) * pageSize;
  const paginatedEvents = useMemo(() => {
    return filteredAndSortedEvents.slice(startIndex, startIndex + pageSize);
  }, [filteredAndSortedEvents, startIndex, pageSize]);

  const itemStart = filteredAndSortedEvents.length === 0 ? 0 : startIndex + 1;
  const itemEnd = Math.min(startIndex + pageSize, filteredAndSortedEvents.length);

  const handleCopyPayload = (payload: unknown) => {
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setHasCopied(true);
    toast.success("Payload copied to clipboard");
    setTimeout(() => setHasCopied(false), 2000);
  };

  return (
    <div className="space-y-4 font-sans">
      {/* Page-level Control Bar: Severity Chips on Left, Search on Right */}
      <PageControlBar
        chips={chips}
        selectedChip={severityFilter}
        onSelectChip={(id) => {
          setSeverityFilter(id);
          setCurrentPage(1);
        }}
        search={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          setCurrentPage(1);
        }}
        searchPlaceholder="Search events, hostnames, messages, actors..."
      />

      {/* Dedicated Table Card exactly matching Jobs Page */}
      <Card className="flex flex-col border-border p-0 gap-0 overflow-hidden bg-card">
        <CardContent className="p-0 overflow-hidden">
          <Table className="table-fixed">
            <TableHeader className="bg-card sticky top-0 z-10 border-b border-border/50">
              <TableRow className="hover:bg-muted/30 bg-muted/30">
                <TableHead className="w-[11%] pl-6">
                  <TableSortHeader
                    label="Severity"
                    sortKey="severity"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[14%]">
                  <TableSortHeader
                    label="Timestamp"
                    sortKey="created_at"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[18%]">
                  <TableSortHeader
                    label="Event Type"
                    sortKey="event_type"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[18%]">
                  <TableSortHeader
                    label="Target / Hostname"
                    sortKey="target_id"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[31%]">
                  <TableSortHeader
                    label="Message"
                    sortKey="message"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="font-semibold text-right pr-6 w-[8%] text-xs text-muted-foreground">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>

            <TableBody
              className={cn(
                "transition-opacity duration-200 text-xs",
                isValidating && !isLoading && "opacity-60",
              )}
            >
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i} className="hover:bg-transparent">
                    <TableCell className="pl-6 py-3.5">
                      <Skeleton className="h-5 w-16" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-24" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-28" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-24" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-full max-w-[280px]" />
                    </TableCell>
                    <TableCell className="pr-6 py-3.5">
                      <Skeleton className="h-5 w-5 ml-auto" />
                    </TableCell>
                  </TableRow>
                ))
              ) : fetchError ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-36 text-center text-destructive">
                    <AlertCircle size={22} className="mx-auto mb-1.5" />
                    <p className="text-xs font-bold">Failed to load farm activity feed</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Could not reach backend telemetry service.
                    </p>
                  </TableCell>
                </TableRow>
              ) : filteredAndSortedEvents.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-36 text-center text-muted-foreground">
                    <Search size={22} className="opacity-30 text-primary mx-auto mb-1.5" />
                    <p className="text-xs font-bold text-foreground">No farm events found</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {searchQuery
                        ? "Try refining your search query."
                        : "Cluster events such as worker heartbeats, task timeouts, and failovers will stream here."}
                    </p>
                  </TableCell>
                </TableRow>
              ) : (
                paginatedEvents.map((evt) => {
                  const targetInfo = getTargetDisplayName(evt);

                  return (
                    <TableRow
                      key={evt.id}
                      className="hover:bg-muted/40 transition-colors group cursor-pointer"
                      onClick={() => setSelectedEvent(evt)}
                    >
                      {/* 1. Severity */}
                      <TableCell className="pl-6 py-3.5 text-left align-middle font-medium">
                        {getSeverityBadge(String(evt.severity))}
                      </TableCell>

                      {/* 2. Timestamp */}
                      <TableCell className="py-3.5 text-muted-foreground align-middle whitespace-nowrap text-left">
                        <div className="flex flex-col">
                          <span className="font-semibold text-foreground font-mono">{formatEventTime(evt.created_at)}</span>
                          <span className="text-[10px] opacity-70">{formatEventDate(evt.created_at)}</span>
                        </div>
                      </TableCell>

                      {/* 3. Event Type */}
                      <TableCell className="py-3.5 text-left align-middle truncate font-semibold text-foreground">
                        <span className="bg-muted/60 px-2 py-0.5 rounded border border-border/60 text-[11px] font-mono">
                          {String(evt.event_type)}
                        </span>
                      </TableCell>

                      {/* 4. Target / Hostname */}
                      <TableCell className="py-3.5 text-left align-middle truncate text-muted-foreground">
                        <div className="flex flex-col gap-0.5 min-w-0">
                          <span className="font-semibold text-foreground text-xs truncate">
                            {targetInfo.label}
                          </span>
                          {Boolean(evt.actor_username) && (
                            <span className="text-[10px] text-muted-foreground">
                              @{String(evt.actor_username)}
                            </span>
                          )}
                        </div>
                      </TableCell>

                      {/* 5. Message */}
                      <TableCell className="py-3.5 text-left align-middle text-xs max-w-0">
                        <p className="text-foreground/90 leading-relaxed truncate" title={String(evt.message)}>
                          {String(evt.message)}
                        </p>
                      </TableCell>

                      {/* 6. Actions: Right Aligned Chevron */}
                      <TableCell className="pr-6 py-3.5 text-right align-middle">
                        <ChevronRight
                          className="ml-auto text-muted-foreground group-hover:text-foreground transition-colors"
                          size={16}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>

        {/* Table Footer with Pagination Controls */}
        {filteredAndSortedEvents.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border/50 bg-muted/15 px-6 py-3 text-xs text-muted-foreground">
            {/* Left: Item Range & Page Size Selector */}
            <div className="flex items-center gap-4">
              <span>
                Showing <strong className="font-semibold text-foreground font-mono">{itemStart}–{itemEnd}</strong> of{" "}
                <strong className="font-semibold text-foreground font-mono">{filteredAndSortedEvents.length}</strong> events
              </span>

              <div className="flex items-center gap-1.5 pl-3 border-l border-border/60">
                <span>Rows per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="h-7 rounded-md border border-border/80 bg-surface-deep px-2 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 cursor-pointer"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>

            {/* Right: Page Navigation Controls */}
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs mr-1">
                Page <strong className="text-foreground">{safePage}</strong> of{" "}
                <strong className="text-foreground">{totalPages}</strong>
              </span>

              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safePage <= 1}
                  onClick={() => setCurrentPage(1)}
                  title="First page"
                >
                  <ChevronsLeft className="size-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safePage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  title="Previous page"
                >
                  <ChevronLeft className="size-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safePage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  title="Next page"
                >
                  <ChevronRight className="size-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safePage >= totalPages}
                  onClick={() => setCurrentPage(totalPages)}
                  title="Last page"
                >
                  <ChevronsRight className="size-3.5" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Side Sheet Matching Users Page Layout */}
      <Sheet open={Boolean(selectedEvent)} onOpenChange={(open) => !open && setSelectedEvent(null)}>
        <SheetContent
          side="right"
          className="w-full border-border bg-card sm:max-w-md md:max-w-lg flex flex-col h-full overflow-hidden p-0 font-sans"
        >
          {Boolean(selectedEvent) && selectedEvent ? (
            <>
              {/* Sheet Header */}
              <SheetHeader className="border-b border-border p-6 shrink-0">
                <SheetTitle className="text-xl font-black text-foreground">
                  {String(selectedEvent.event_type)}
                </SheetTitle>
                <SheetDescription className="mt-1.5 leading-relaxed font-mono text-xs text-muted-foreground break-all">
                  Event ID: {String(selectedEvent.id)}
                </SheetDescription>
              </SheetHeader>

              {/* Sheet Body Content matching Users Page */}
              <div className="flex-1 overflow-y-auto p-6 flex flex-col space-y-5">
                {/* Severity & Status Section */}
                <div>
                  <p className="text-xs uppercase text-muted-foreground font-semibold">
                    Severity & Classification
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {getSeverityBadge(String(selectedEvent.severity))}
                    <Badge variant="outline" className="font-mono text-xs">
                      {String(selectedEvent.event_type)}
                    </Badge>
                  </div>
                </div>

                {/* Log Message Section */}
                <div className="border-t border-border pt-5 space-y-2">
                  <p className="text-xs uppercase text-muted-foreground font-semibold">
                    Log Message
                  </p>
                  <div className="p-3.5 bg-surface-deep rounded-lg border border-border text-xs font-mono leading-relaxed text-foreground break-words select-text">
                    {String(selectedEvent.message || "")}
                  </div>
                </div>

                {/* Event Context & References Section */}
                <div className="grid gap-4 border-t border-border pt-5">
                  <div className="flex items-start gap-3">
                    <UserIcon className="mt-0.5 text-primary shrink-0" size={16} />
                    <div>
                      <p className="text-xs text-muted-foreground">Actor</p>
                      <p className="mt-1 text-sm font-medium text-foreground">
                        {Boolean(selectedEvent.actor_username)
                          ? `@${String(selectedEvent.actor_username)}`
                          : "System / Daemon"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <Server className="mt-0.5 text-primary shrink-0" size={16} />
                    <div>
                      <p className="text-xs text-muted-foreground">Target Host / Resource</p>
                      <p className="mt-1 text-sm font-bold text-foreground">
                        {getTargetDisplayName(selectedEvent).label}
                      </p>
                      {Boolean(selectedEvent.target_type) && (
                        <p className="text-[11px] text-muted-foreground capitalize mt-0.5">
                          Type: {String(selectedEvent.target_type)}
                        </p>
                      )}
                    </div>
                  </div>

                  {Boolean(selectedEvent.target_id) && (
                    <div className="flex items-start gap-3">
                      <Layers className="mt-0.5 text-primary shrink-0" size={16} />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-muted-foreground">Target Identifier (UUID)</p>
                        <p className="mt-1 text-xs font-mono font-bold text-muted-foreground break-all select-all">
                          {String(selectedEvent.target_id)}
                        </p>
                      </div>
                    </div>
                  )}

                  <div className="flex items-start gap-3">
                    <CalendarDays className="mt-0.5 text-primary shrink-0" size={16} />
                    <div>
                      <p className="text-xs text-muted-foreground">Recorded Timestamp</p>
                      <p className="mt-1 text-sm font-mono text-foreground">
                        {formatEventDate(selectedEvent.created_at)} at{" "}
                        {formatEventTime(selectedEvent.created_at)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Structured JSON Payload & Diagnostics */}
                {Boolean(
                  selectedEvent.payload &&
                    typeof selectedEvent.payload === "object" &&
                    Object.keys(selectedEvent.payload as Record<string, unknown>).length > 0,
                ) && (
                  <div className="border-t border-border pt-5 space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-xs uppercase text-muted-foreground font-semibold flex items-center gap-1.5">
                        <Terminal size={13} className="text-primary" />
                        Diagnostic Payload
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCopyPayload(selectedEvent.payload)}
                        className="h-7 px-2.5 text-xs font-mono gap-1.5 bg-surface-deep border-border"
                      >
                        {hasCopied ? (
                          <>
                            <Check size={12} className="text-emerald-500" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy size={12} />
                            Copy JSON
                          </>
                        )}
                      </Button>
                    </div>

                    <div className="p-3.5 bg-surface-deep rounded-lg border border-border text-xs text-foreground/90 font-mono overflow-x-auto select-text max-h-60 leading-relaxed">
                      <pre className="text-[11px]">
                        {JSON.stringify(selectedEvent.payload, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
