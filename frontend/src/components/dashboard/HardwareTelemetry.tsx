"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Activity, Cpu, Layers, RefreshCw, ArrowRight } from "lucide-react";
import type { TelemetryMetrics, TelemetryPoint } from "@/types/dashboard";
import { fetchClusterTelemetryHistory } from "@/services/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface HardwareTelemetryProps {
  telemetry: TelemetryMetrics;
}

type TimeRange = "1h" | "24h" | "7d";

const fallbackPoints: TelemetryPoint[] = [
  { x: 0, vram: 0, cpu: 0, active_tasks: 0 },
  { x: 50, vram: 0, cpu: 0, active_tasks: 0 },
  { x: 100, vram: 0, cpu: 0, active_tasks: 0 },
];

interface Coord {
  x: number;
  y: number;
}

interface AxisTick {
  x: number;
  label: string;
  isFirst: boolean;
  isLast: boolean;
}

function buildClampedSpline(coords: Coord[], topY: number = 20, baselineY: number = 245): string {
  if (coords.length === 0) return "";
  if (coords.length === 1) return `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)}`;
  if (coords.length === 2) {
    return `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)} L ${coords[1].x.toFixed(1)} ${coords[1].y.toFixed(1)}`;
  }

  let path = `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)}`;
  for (let i = 0; i < coords.length - 1; i++) {
    const p0 = coords[Math.max(0, i - 1)];
    const p1 = coords[i];
    const p2 = coords[i + 1];
    const p3 = coords[Math.min(coords.length - 1, i + 2)];

    // Flat segment along baseline
    if (Math.abs(p1.y - baselineY) < 0.1 && Math.abs(p2.y - baselineY) < 0.1) {
      path += ` L ${p2.x.toFixed(1)} ${baselineY.toFixed(1)}`;
      continue;
    }

    let cp1x = p1.x + (p2.x - p0.x) * 0.16;
    let cp1y = p1.y + (p2.y - p0.y) * 0.16;
    let cp2x = p2.x - (p3.x - p1.x) * 0.16;
    let cp2y = p2.y - (p3.y - p1.y) * 0.16;

    // Hard boundary clamping: never exceed baseline (0%) or go above topY (100%)
    cp1y = Math.min(baselineY, Math.max(topY, cp1y));
    cp2y = Math.min(baselineY, Math.max(topY, cp2y));

    // Monotone clamping to prevent curve sag below either endpoint
    const minY = Math.min(p1.y, p2.y);
    const maxY = Math.max(p1.y, p2.y);
    cp1y = Math.min(maxY, Math.max(minY, cp1y));
    cp2y = Math.min(maxY, Math.max(minY, cp2y));

    path += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return path;
}

function buildClampedArea(coords: Coord[], topY: number = 20, baselineY: number = 245): string {
  const linePath = buildClampedSpline(coords, topY, baselineY);
  if (!linePath || coords.length === 0) return "";
  const last = coords[coords.length - 1];
  const first = coords[0];
  return `${linePath} L ${last.x.toFixed(1)} ${baselineY.toFixed(1)} L ${first.x.toFixed(1)} ${baselineY.toFixed(1)} Z`;
}

function formatTooltipDate(isoString?: string, range: TimeRange = "1h"): string {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (range === "7d") {
    return (
      d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) +
      " " +
      d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    );
  }
  if (range === "24h") {
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function getAxisTicks(points: TelemetryPoint[], range: TimeRange, minX: number, maxX: number): AxisTick[] {
  if (!points || points.length === 0) return [];
  const plotWidth = maxX - minX;
  const n = Math.max(1, points.length - 1);

  let rawIndices: number[] = [];
  if (range === "7d") {
    // 7 distinct daily ticks across 28 points
    rawIndices = [0, 4, 8, 12, 16, 20, 24, n];
  } else if (range === "24h") {
    // 7 ticks every 4 hours across 24 points
    rawIndices = [0, 4, 8, 12, 16, 20, n];
  } else {
    // 6 ticks every 12 mins across 15 points
    rawIndices = [0, 3, 6, 9, 12, n];
  }

  const uniqueIndices = Array.from(new Set(rawIndices)).filter((idx) => idx <= n);

  return uniqueIndices.map((idx, i) => {
    const p = points[idx];
    const d = new Date(p.timestamp || "");
    const isFirst = i === 0;
    const isLast = i === uniqueIndices.length - 1;

    let label = "";
    if (range === "7d") {
      label = isLast ? "Today" : d.toLocaleDateString([], { weekday: "short", month: "numeric", day: "numeric" });
    } else if (range === "24h") {
      label = isLast ? "Now" : d.toLocaleTimeString([], { hour: "numeric" });
    } else {
      label = isLast ? "Now" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    return {
      x: minX + (idx / n) * plotWidth,
      label,
      isFirst,
      isLast,
    };
  });
}

export default function HardwareTelemetry({ telemetry: liveTelemetry }: HardwareTelemetryProps) {
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [timeRange, setTimeRange] = useState<TimeRange>("1h");
  const [hoveredPointIndex, setHoveredPointIndex] = useState<number | null>(null);

  // 1. Always fetch 1h history for the card preview
  const { data: cardHistoryData } = useSWR(
    `/api/telemetry/cluster/history/?range=1h`,
    () => fetchClusterTelemetryHistory("1h"),
    {
      refreshInterval: 10000,
      revalidateOnFocus: true,
      dedupingInterval: 3000,
    },
  );

  const cardPoints = useMemo(() => {
    if (cardHistoryData?.points && cardHistoryData.points.length > 0) {
      return cardHistoryData.points.map((p) => ({
        x: p.x,
        cpu: p.cpu,
        vram: p.vram,
        ram: p.ram ?? 0,
        active_tasks: p.active_tasks ?? 0,
        timestamp: p.timestamp,
      }));
    }
    return fallbackPoints;
  }, [cardHistoryData]);

  // Mini card SVG curves (high-res 400x120 coordinate space with axis margins)
  const miniCoords = useMemo(() => {
    const minX = 32;
    const maxX = 390;
    const plotWidth = maxX - minX;
    const topY = 12;
    const baselineY = 100;
    const plotHeight = baselineY - topY;

    const n = Math.max(1, cardPoints.length - 1);

    const vramCoords: Coord[] = cardPoints.map((p, i) => ({
      x: minX + (i / n) * plotWidth,
      y: baselineY - (Math.min(100, Math.max(0, p.vram)) / 100) * plotHeight,
    }));

    const cpuCoords: Coord[] = cardPoints.map((p, i) => ({
      x: minX + (i / n) * plotWidth,
      y: baselineY - (Math.min(100, Math.max(0, p.cpu)) / 100) * plotHeight,
    }));

    const ramCoords: Coord[] = cardPoints.map((p, i) => ({
      x: minX + (i / n) * plotWidth,
      y: baselineY - (Math.min(100, Math.max(0, p.ram ?? 0)) / 100) * plotHeight,
    }));

    const maxMiniTaskVal = Math.max(1, ...cardPoints.map((p) => p.active_tasks || 0));
    const taskCoords: Coord[] = cardPoints.map((p, i) => ({
      x: minX + (i / n) * plotWidth,
      y: baselineY - ((p.active_tasks || 0) / maxMiniTaskVal) * plotHeight,
    }));

    return {
      minX,
      maxX,
      topY,
      baselineY,
      vramLine: buildClampedSpline(vramCoords, topY, baselineY),
      vramArea: buildClampedArea(vramCoords, topY, baselineY),
      cpuLine: buildClampedSpline(cpuCoords, topY, baselineY),
      cpuArea: buildClampedArea(cpuCoords, topY, baselineY),
      ramLine: buildClampedSpline(ramCoords, topY, baselineY),
      ramArea: buildClampedArea(ramCoords, topY, baselineY),
      taskLine: buildClampedSpline(taskCoords, topY, baselineY),
    };
  }, [cardPoints]);

  // 2. Fetch specific range history when modal is active
  const {
    data: modalHistoryData,
    isLoading: isModalLoading,
    isValidating: isModalValidating,
    mutate: mutateModalHistory,
  } = useSWR(
    isModalOpen ? [`/api/telemetry/cluster/history/`, timeRange] : null,
    () => fetchClusterTelemetryHistory(timeRange),
    {
      refreshInterval: 10000,
      revalidateOnFocus: true,
      dedupingInterval: 2000,
      keepPreviousData: true,
    },
  );

  const modalPoints = useMemo(() => {
    if (modalHistoryData?.points && modalHistoryData.points.length > 0) {
      return modalHistoryData.points.map((p) => ({
        x: p.x,
        cpu: p.cpu,
        vram: p.vram,
        ram: p.ram ?? 0,
        active_tasks: p.active_tasks ?? 0,
        timestamp: p.timestamp,
      }));
    }
    return cardPoints;
  }, [modalHistoryData, cardPoints]);

  // Modal Plot geometry: Width = 800, Height = 280, X in [45, 775], Y in [20, 245]
  const plotGeometry = useMemo(() => {
    const minX = 45;
    const maxX = 775;
    const plotWidth = maxX - minX;
    const topY = 20;
    const baselineY = 245;
    const plotHeight = baselineY - topY;

    const n = Math.max(1, modalPoints.length - 1);

    const vramCoords: Coord[] = modalPoints.map((p, i) => {
      const x = minX + (i / n) * plotWidth;
      const y = baselineY - (Math.min(100, Math.max(0, p.vram)) / 100) * plotHeight;
      return { x, y };
    });

    const cpuCoords: Coord[] = modalPoints.map((p, i) => {
      const x = minX + (i / n) * plotWidth;
      const y = baselineY - (Math.min(100, Math.max(0, p.cpu)) / 100) * plotHeight;
      return { x, y };
    });

    const ramCoords: Coord[] = modalPoints.map((p, i) => {
      const x = minX + (i / n) * plotWidth;
      const y = baselineY - (Math.min(100, Math.max(0, p.ram ?? 0)) / 100) * plotHeight;
      return { x, y };
    });

    const maxModalTaskVal = Math.max(1, ...modalPoints.map((p) => p.active_tasks || 0));
    const taskCoords: Coord[] = modalPoints.map((p, i) => {
      const x = minX + (i / n) * plotWidth;
      const y = baselineY - ((p.active_tasks || 0) / maxModalTaskVal) * plotHeight;
      return { x, y };
    });

    const axisTicks = getAxisTicks(modalPoints, timeRange, minX, maxX);

    return {
      minX,
      maxX,
      topY,
      baselineY,
      vramCoords,
      cpuCoords,
      ramCoords,
      taskCoords,
      axisTicks,
      vramLine: buildClampedSpline(vramCoords, topY, baselineY),
      vramArea: buildClampedArea(vramCoords, topY, baselineY),
      cpuLine: buildClampedSpline(cpuCoords, topY, baselineY),
      cpuArea: buildClampedArea(cpuCoords, topY, baselineY),
      ramLine: buildClampedSpline(ramCoords, topY, baselineY),
      ramArea: buildClampedArea(ramCoords, topY, baselineY),
      taskLine: buildClampedSpline(taskCoords, topY, baselineY),
    };
  }, [modalPoints, timeRange]);

  const hoveredPoint = hoveredPointIndex !== null ? modalPoints[hoveredPointIndex] : null;
  const hoveredCoord = hoveredPointIndex !== null ? plotGeometry.vramCoords[hoveredPointIndex] : null;

  return (
    <>
      <Card className="border-border p-0 gap-0 h-full flex flex-col justify-between">
        <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Cpu size={15} className="text-primary" />
            <CardTitle className="text-sm font-bold text-foreground">Cluster Resource Utilization</CardTitle>
          </div>
          <Badge
            variant="outline"
            className="text-[11px] font-mono border-primary/30 text-primary bg-primary/5 px-1.5 py-0 font-medium"
          >
            Live
          </Badge>
        </CardHeader>
        <CardContent className="p-3.5 space-y-5">
          <div className="space-y-3.5 text-xs font-mono">
            <div className="space-y-1.5">
              <div className="flex justify-between text-muted-foreground">
                <span>CPU Load</span>
                <span className="text-info font-bold">{liveTelemetry.cpuLoad}%</span>
              </div>
              <Progress
                value={liveTelemetry.cpuLoad}
                className="h-2"
                indicatorClassName="bg-gradient-to-r from-info to-info/80 shadow-[0_0_10px] shadow-info/40"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-muted-foreground">
                <span>Memory Usage</span>
                <span className="text-emerald-400 font-bold">
                  {liveTelemetry.memoryUsage ?? liveTelemetry.ramUsage ?? 0}%
                </span>
              </div>
              <Progress
                value={liveTelemetry.memoryUsage ?? liveTelemetry.ramUsage ?? 0}
                className="h-2"
                indicatorClassName="bg-gradient-to-r from-emerald-500 to-emerald-500/80 shadow-[0_0_10px] shadow-emerald-500/40"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-muted-foreground">
                <span>VRAM Usage</span>
                <span className="text-primary font-bold">{liveTelemetry.vramUsage}%</span>
              </div>
              <Progress
                value={liveTelemetry.vramUsage}
                className="h-2"
                indicatorClassName="bg-gradient-to-r from-primary to-primary/80 shadow-[0_0_10px] shadow-primary/40"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="w-full pt-1 text-left cursor-pointer group"
            aria-label="Open telemetry history analytics"
          >
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-xs font-mono text-muted-foreground group-hover:text-foreground transition-colors">
                Cluster Load Telemetry (1h)
              </p>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-xs font-medium text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 shrink-0 group">
                  <span className="text-primary group-hover:underline font-mono">Expand ↗</span>
                </span>
              </div>
            </div>
            <div className="w-full h-32 bg-surface-deep rounded-lg border border-input relative overflow-hidden flex items-end transition-all duration-300 group-hover:border-primary">
              <svg className="w-full h-full p-2" viewBox="0 0 400 120" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="miniChartGradientVram" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.25" />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="miniChartGradientCpu" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--info)" stopOpacity="0.18" />
                    <stop offset="100%" stopColor="var(--info)" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="miniChartGradientRam" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.16" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                  </linearGradient>
                </defs>

                {/* Y-Axis Horizontal Gridlines & Scale Labels */}
                <g>
                  <line
                    x1={miniCoords.minX}
                    y1="12"
                    x2={miniCoords.maxX}
                    y2="12"
                    stroke="var(--border)"
                    strokeOpacity="0.4"
                    strokeDasharray="3 3"
                    vectorEffect="non-scaling-stroke"
                  />
                  <text
                    x={miniCoords.minX - 6}
                    y="15"
                    textAnchor="end"
                    fill="var(--muted-foreground)"
                    fontSize="8.5"
                    fontFamily="monospace"
                  >
                    100%
                  </text>

                  <line
                    x1={miniCoords.minX}
                    y1="56"
                    x2={miniCoords.maxX}
                    y2="56"
                    stroke="var(--border)"
                    strokeOpacity="0.4"
                    strokeDasharray="3 3"
                    vectorEffect="non-scaling-stroke"
                  />
                  <text
                    x={miniCoords.minX - 6}
                    y="59"
                    textAnchor="end"
                    fill="var(--muted-foreground)"
                    fontSize="8.5"
                    fontFamily="monospace"
                  >
                    50%
                  </text>

                  <line
                    x1={miniCoords.minX}
                    y1={miniCoords.baselineY}
                    x2={miniCoords.maxX}
                    y2={miniCoords.baselineY}
                    stroke="var(--border)"
                    strokeOpacity="0.7"
                    vectorEffect="non-scaling-stroke"
                  />
                  <text
                    x={miniCoords.minX - 6}
                    y={miniCoords.baselineY + 3}
                    textAnchor="end"
                    fill="var(--muted-foreground)"
                    fontSize="8.5"
                    fontFamily="monospace"
                  >
                    0%
                  </text>
                </g>

                {/* Filled Spline Areas */}
                <path d={miniCoords.vramArea} fill="url(#miniChartGradientVram)" />
                <path d={miniCoords.cpuArea} fill="url(#miniChartGradientCpu)" />
                <path d={miniCoords.ramArea} fill="url(#miniChartGradientRam)" />

                {/* Smooth Curve Lines */}
                <path
                  d={miniCoords.vramLine}
                  fill="none"
                  stroke="var(--primary)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  d={miniCoords.cpuLine}
                  fill="none"
                  stroke="var(--info)"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="3 2"
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  d={miniCoords.ramLine}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="4 2"
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  d={miniCoords.taskLine}
                  fill="none"
                  stroke="var(--warning)"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="2 2"
                  vectorEffect="non-scaling-stroke"
                />

                {/* X-Axis Time Labels */}
                <g>
                  <text
                    x={miniCoords.minX}
                    y="114"
                    textAnchor="start"
                    fill="var(--muted-foreground)"
                    fontSize="8.5"
                    fontFamily="monospace"
                  >
                    -60m
                  </text>
                  <text
                    x={(miniCoords.minX + miniCoords.maxX) / 2}
                    y="114"
                    textAnchor="middle"
                    fill="var(--muted-foreground)"
                    fontSize="8.5"
                    fontFamily="monospace"
                  >
                    -30m
                  </text>
                  <text
                    x={miniCoords.maxX}
                    y="114"
                    textAnchor="end"
                    fill="var(--muted-foreground)"
                    fontSize="8.5"
                    fontFamily="monospace"
                  >
                    Now
                  </text>
                </g>
              </svg>
            </div>
          </button>
        </CardContent>
      </Card>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-5xl sm:max-w-5xl p-0 gap-0 overflow-hidden border-border bg-surface shadow-2xl">
          <DialogHeader className="border-b border-border px-6 py-4 bg-background/90 flex flex-row items-center justify-between space-y-0">
            <div className="text-left">
              <DialogTitle className="text-lg font-bold text-foreground flex items-center gap-2">
                <Activity className="size-5 text-primary" />
                Cluster Telemetry Analytics
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground font-mono mt-0.5">
                Aggregated hardware load and active task concurrency across worker nodes.
              </DialogDescription>
            </div>
          </DialogHeader>

          <div className="p-6 space-y-4">
            {/* Top Toolbar: Range Selector on Left, Hover Inspection Stats on Right */}
            <div className="h-9 flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-1.5 bg-surface-deep border border-border/80 rounded-lg p-1">
                {(["1h", "24h", "7d"] as TimeRange[]).map((range) => (
                  <Button
                    key={range}
                    variant={timeRange === range ? "default" : "ghost"}
                    size="sm"
                    onClick={() => {
                      setTimeRange(range);
                      setHoveredPointIndex(null);
                    }}
                    className={`h-7 px-3 text-xs font-mono uppercase ${
                      timeRange === range
                        ? "bg-primary text-primary-foreground font-bold shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {range}
                  </Button>
                ))}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => void mutateModalHistory()}
                  disabled={isModalValidating}
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  title="Refresh history"
                >
                  <RefreshCw className={`size-3.5 ${isModalValidating ? "animate-spin" : ""}`} />
                </Button>
              </div>

              <div className="flex items-center">
                {hoveredPoint ? (
                  <div className="flex items-center gap-2 font-mono text-xs animate-in fade-in">
                    <Badge
                      variant="outline"
                      className="text-muted-foreground font-mono text-xs h-6 px-2 border-border/80 bg-surface-deep"
                    >
                      {formatTooltipDate(hoveredPoint.timestamp, timeRange)}
                    </Badge>
                    <Badge
                      variant="outline"
                      className="text-info font-mono text-xs h-6 px-2 border-info/40 bg-info/10 font-bold"
                    >
                      CPU: {hoveredPoint.cpu}%
                    </Badge>
                    <Badge
                      variant="outline"
                      className="text-emerald-400 font-mono text-xs h-6 px-2 border-emerald-500/40 bg-emerald-500/10 font-bold"
                    >
                      RAM: {hoveredPoint.ram ?? 0}%
                    </Badge>
                    <Badge
                      variant="outline"
                      className="text-primary font-mono text-xs h-6 px-2 border-primary/40 bg-primary/10 font-bold"
                    >
                      VRAM: {hoveredPoint.vram}%
                    </Badge>
                    <Badge
                      variant="outline"
                      className="text-warning font-mono text-xs h-6 px-2 border-warning/40 bg-warning/10 font-bold"
                    >
                      {hoveredPoint.active_tasks ?? 0} Tasks
                    </Badge>
                  </div>
                ) : (
                  <span className="text-muted-foreground text-xs">
                    Hover along the {timeRange.toUpperCase()} timeline to inspect bucket metrics
                  </span>
                )}
              </div>
            </div>

            {/* Main Interactive Chart with High-Resolution SVG Canvas */}
            <div className="h-[360px] rounded-xl border border-input bg-surface-deep overflow-hidden relative group">
              {isModalLoading && !modalHistoryData && (
                <div className="absolute inset-0 bg-background/50 backdrop-blur-xs flex items-center justify-center z-10">
                  <RefreshCw className="size-6 text-primary animate-spin" />
                </div>
              )}

              <svg
                className="h-full w-full cursor-crosshair select-none"
                viewBox="0 0 800 280"
                preserveAspectRatio="none"
                onMouseLeave={() => setHoveredPointIndex(null)}
              >
                <defs>
                  <linearGradient id="vramModalGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.35" />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="cpuModalGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--info)" stopOpacity="0.22" />
                    <stop offset="100%" stopColor="var(--info)" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="ramModalGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.2" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                  </linearGradient>
                </defs>

                {/* Horizontal Gridlines & Y-Axis Scale Labels */}
                {[
                  { pct: 100, y: 20 },
                  { pct: 75, y: 76.25 },
                  { pct: 50, y: 132.5 },
                  { pct: 25, y: 188.75 },
                  { pct: 0, y: 245 },
                ].map(({ pct, y }) => (
                  <g key={pct}>
                    <line
                      x1={plotGeometry.minX}
                      y1={y}
                      x2={plotGeometry.maxX}
                      y2={y}
                      stroke="var(--border)"
                      strokeOpacity="0.7"
                      strokeDasharray="3 3"
                      strokeWidth="1"
                    />
                    <text
                      x={plotGeometry.minX - 8}
                      y={y + 3.5}
                      textAnchor="end"
                      fill="var(--muted-foreground)"
                      fontSize="10"
                      fontFamily="monospace"
                    >
                      {pct}%
                    </text>
                  </g>
                ))}

                {/* X-Axis Bottom Baseline */}
                <line
                  x1={plotGeometry.minX}
                  y1={plotGeometry.baselineY}
                  x2={plotGeometry.maxX}
                  y2={plotGeometry.baselineY}
                  stroke="var(--border)"
                  strokeWidth="1"
                />

                {/* Filled Spline Areas */}
                <path d={plotGeometry.vramArea} fill="url(#vramModalGradient)" />
                <path d={plotGeometry.cpuArea} fill="url(#cpuModalGradient)" />
                <path d={plotGeometry.ramArea} fill="url(#ramModalGradient)" />

                {/* Smooth Curve Lines */}
                <path
                  d={plotGeometry.vramLine}
                  fill="none"
                  stroke="var(--primary)"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d={plotGeometry.cpuLine}
                  fill="none"
                  stroke="var(--info)"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="4 2"
                />
                <path
                  d={plotGeometry.ramLine}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="6 3"
                />
                <path
                  d={plotGeometry.taskLine}
                  fill="none"
                  stroke="var(--warning)"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="2 2"
                />

                {/* X-Axis Distinct Time Ticks (Zero overlap/collision) */}
                {plotGeometry.axisTicks.map((tick, index) => {
                  const textAnchor = tick.isFirst ? "start" : tick.isLast ? "end" : "middle";
                  return (
                    <g key={index}>
                      <line
                        x1={tick.x}
                        y1={plotGeometry.baselineY}
                        x2={tick.x}
                        y2={plotGeometry.baselineY + 4}
                        stroke="var(--border)"
                        strokeWidth="1"
                      />
                      <text
                        x={tick.x}
                        y={plotGeometry.baselineY + 18}
                        textAnchor={textAnchor}
                        fill="var(--muted-foreground)"
                        fontSize="10"
                        fontFamily="monospace"
                      >
                        {tick.label}
                      </text>
                    </g>
                  );
                })}

                {/* Invisible Hover Slices for Instant Crosshair Snap */}
                {modalPoints.map((point, index) => {
                  const coord = plotGeometry.vramCoords[index];
                  const sliceWidth = (plotGeometry.maxX - plotGeometry.minX) / Math.max(1, modalPoints.length);

                  return (
                    <rect
                      key={index}
                      x={coord.x - sliceWidth / 2}
                      y={plotGeometry.topY}
                      width={sliceWidth}
                      height={plotGeometry.baselineY - plotGeometry.topY}
                      fill="transparent"
                      className="cursor-crosshair"
                      onMouseEnter={() => setHoveredPointIndex(index)}
                    />
                  );
                })}

                {/* Active Hover Crosshair Line & Target Markers */}
                {hoveredCoord && hoveredPointIndex !== null && (
                  <g className="pointer-events-none transition-all duration-150">
                    <line
                      x1={hoveredCoord.x}
                      y1={plotGeometry.topY}
                      x2={hoveredCoord.x}
                      y2={plotGeometry.baselineY}
                      stroke="var(--primary)"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                      strokeOpacity="0.8"
                    />

                    {/* VRAM Anchor Dot */}
                    <circle
                      cx={hoveredCoord.x}
                      cy={plotGeometry.vramCoords[hoveredPointIndex].y}
                      r="4.5"
                      fill="var(--primary)"
                      stroke="var(--background)"
                      strokeWidth="2"
                    />

                    {/* System RAM Anchor Dot */}
                    <circle
                      cx={hoveredCoord.x}
                      cy={plotGeometry.ramCoords[hoveredPointIndex].y}
                      r="4.5"
                      fill="#10b981"
                      stroke="var(--background)"
                      strokeWidth="2"
                    />

                    {/* CPU Anchor Dot */}
                    <circle
                      cx={hoveredCoord.x}
                      cy={plotGeometry.cpuCoords[hoveredPointIndex].y}
                      r="4.5"
                      fill="var(--info)"
                      stroke="var(--background)"
                      strokeWidth="2"
                    />

                    {/* Active Tasks Anchor Dot */}
                    <circle
                      cx={hoveredCoord.x}
                      cy={plotGeometry.taskCoords[hoveredPointIndex].y}
                      r="4.5"
                      fill="var(--warning)"
                      stroke="var(--background)"
                      strokeWidth="2"
                    />
                  </g>
                )}
              </svg>
            </div>

            {/* Bottom Footer: Legend Chips & Refresh Interval Note */}
            <div className="flex flex-wrap items-center justify-between text-xs font-mono pt-1 text-muted-foreground">
              <div className="flex items-center gap-5">
                <span className="inline-flex items-center gap-2">
                  <span className="h-2 w-3.5 rounded-full bg-info" />
                  <span className="text-foreground font-medium">CPU Load</span>
                </span>
                <span className="inline-flex items-center gap-2">
                  <span className="h-2 w-3.5 rounded-full bg-emerald-500" />
                  <span className="text-foreground font-medium">Memory Usage</span>
                </span>
                <span className="inline-flex items-center gap-2">
                  <span className="h-2 w-3.5 rounded-full bg-primary" />
                  <span className="text-foreground font-medium">VRAM Usage</span>
                </span>
                <span className="inline-flex items-center gap-2">
                  <Layers className="h-2 w-3.5 rounded-full bg-warning" />
                  <span className="text-foreground font-medium">Active Tasks</span>
                </span>
              </div>

              <div className="text-xs text-muted-foreground">Live Snapshots (10s auto-refresh)</div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
