"use client";

import { useMemo, useState } from "react";
import { Activity, Cpu, Layers, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ClusterTelemetryHistory } from "@/services/api";

export type TimeRange = "1h" | "24h" | "7d";

interface Coord {
  x: number;
  y: number;
}

interface AxisTick {
  x: number;
  label: string;
  isFirst?: boolean;
  isLast?: boolean;
}

function buildClampedSpline(coords: Coord[], topY: number = 20, baselineY: number = 245): string {
  if (coords.length === 0) return "";
  if (coords.length === 1) return `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)}`;

  let path = `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)}`;
  for (let i = 0; i < coords.length - 1; i++) {
    const p0 = i > 0 ? coords[i - 1] : coords[i];
    const p1 = coords[i];
    const p2 = coords[i + 1];
    const p3 = i < coords.length - 2 ? coords[i + 2] : p2;

    if (Math.abs(p1.y - baselineY) < 0.1 && Math.abs(p2.y - baselineY) < 0.1) {
      path += ` L ${p2.x.toFixed(1)} ${baselineY.toFixed(1)}`;
      continue;
    }

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    let cp1y = p1.y + (p2.y - p0.y) / 6;

    const cp2x = p2.x - (p3.x - p1.x) / 6;
    let cp2y = p2.y - (p3.y - p1.y) / 6;

    cp1y = Math.min(baselineY, Math.max(topY, cp1y));
    cp2y = Math.min(baselineY, Math.max(topY, cp2y));

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

function getAxisTicks(points: { timestamp?: string }[], range: TimeRange, minX: number, maxX: number): AxisTick[] {
  const total = points.length;
  if (total === 0) return [];
  const plotWidth = maxX - minX;

  if (range === "7d") {
    const ticks: AxisTick[] = [];
    const step = Math.max(1, Math.floor(total / 7));
    for (let i = 0; i < total; i += step) {
      const p = points[i];
      const x = minX + (i / (total - 1)) * plotWidth;
      const d = p.timestamp ? new Date(p.timestamp) : null;
      const label = d
        ? d.toLocaleDateString([], { weekday: "short", month: "numeric", day: "numeric" })
        : `D-${7 - Math.floor(i / step)}`;
      ticks.push({ x, label, isFirst: i === 0 });
    }
    if (ticks.length > 0 && Math.abs(ticks[ticks.length - 1].x - maxX) > 30) {
      ticks.push({ x: maxX, label: "Today", isLast: true });
    } else if (ticks.length > 0) {
      ticks[ticks.length - 1].label = "Today";
      ticks[ticks.length - 1].isLast = true;
    }
    return ticks;
  }

  if (range === "24h") {
    const ticks: AxisTick[] = [];
    const step = Math.max(1, Math.floor(total / 6));
    for (let i = 0; i < total; i += step) {
      const p = points[i];
      const x = minX + (i / (total - 1)) * plotWidth;
      const d = p.timestamp ? new Date(p.timestamp) : null;
      const label = d
        ? d.toLocaleTimeString([], { hour: "numeric", hour12: true })
        : `-${24 - Math.round((i / total) * 24)}h`;
      ticks.push({ x, label, isFirst: i === 0 });
    }
    if (ticks.length > 0 && Math.abs(ticks[ticks.length - 1].x - maxX) > 30) {
      ticks.push({ x: maxX, label: "Now", isLast: true });
    } else if (ticks.length > 0) {
      ticks[ticks.length - 1].label = "Now";
      ticks[ticks.length - 1].isLast = true;
    }
    return ticks;
  }

  // 1h default
  const ticks: AxisTick[] = [];
  const step = Math.max(1, Math.floor(total / 4));
  for (let i = 0; i < total; i += step) {
    const p = points[i];
    const x = minX + (i / (total - 1)) * plotWidth;
    const d = p.timestamp ? new Date(p.timestamp) : null;
    const label = d
      ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : `-${60 - Math.round((i / total) * 60)}m`;
    ticks.push({ x, label, isFirst: i === 0 });
  }
  if (ticks.length > 0 && Math.abs(ticks[ticks.length - 1].x - maxX) > 30) {
    ticks.push({ x: maxX, label: "Now", isLast: true });
  } else if (ticks.length > 0) {
    ticks[ticks.length - 1].label = "Now";
    ticks[ticks.length - 1].isLast = true;
  }
  return ticks;
}

interface TelemetryTimeseriesChartProps {
  telemetryData?: ClusterTelemetryHistory;
  timeRange: TimeRange;
  onTimeRangeChange?: (range: TimeRange) => void;
  isLoading: boolean;
}

export function TelemetryTimeseriesChart({
  telemetryData,
  timeRange,
  onTimeRangeChange,
  isLoading,
}: TelemetryTimeseriesChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const points = telemetryData?.points ?? [];

  const plotGeometry = useMemo(() => {
    const minX = 42;
    const maxX = 780;
    const topY = 25;
    const baselineY = 245;
    const plotWidth = maxX - minX;
    const plotHeight = baselineY - topY;
    const n = Math.max(1, points.length - 1);

    const vramCoords: Coord[] = points.map((p, i) => {
      const x = minX + (i / n) * plotWidth;
      const y = baselineY - (Math.min(100, Math.max(0, p.vram)) / 100) * plotHeight;
      return { x, y };
    });

    const cpuCoords: Coord[] = points.map((p, i) => {
      const x = minX + (i / n) * plotWidth;
      const y = baselineY - (Math.min(100, Math.max(0, p.cpu)) / 100) * plotHeight;
      return { x, y };
    });

    const ramCoords: Coord[] = points.map((p, i) => {
      const x = minX + (i / n) * plotWidth;
      const y = baselineY - (Math.min(100, Math.max(0, p.ram ?? 0)) / 100) * plotHeight;
      return { x, y };
    });

    const maxTaskVal = Math.max(1, ...points.map((p) => p.active_tasks || 0));
    const taskCoords: Coord[] = points.map((p, i) => {
      const x = minX + (i / n) * plotWidth;
      const y = baselineY - ((p.active_tasks || 0) / maxTaskVal) * plotHeight;
      return { x, y };
    });

    const axisTicks = getAxisTicks(points, timeRange, minX, maxX);

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
  }, [points, timeRange]);

  const hoveredPoint = hoveredIndex !== null ? points[hoveredIndex] : null;
  const hoveredCoord = hoveredIndex !== null ? plotGeometry.vramCoords[hoveredIndex] : null;

  return (
    <Card className="bg-surface border-border p-0 gap-0 overflow-hidden font-mono">
      {/* Clean Card Header with Title */}
      <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-primary" />
          <CardTitle className="text-sm font-bold text-foreground">Cluster Telemetry Analytics</CardTitle>
        </div>
      </CardHeader>

      <CardContent className="p-4 space-y-4">
        {/* Top Toolbar: Time Tabs on Left, Hover Inspection Metrics on Right */}
        <div className="h-9 flex items-center justify-between text-xs font-mono">
          {/* Left: Time Range Tabs with crisp active indicator */}
          <div className="flex items-center gap-1.5 bg-surface-deep border border-border/80 rounded-lg p-1">
            {(["1h", "24h", "7d"] as TimeRange[]).map((range) => {
              const isActive = timeRange === range;
              return (
                <Button
                  key={range}
                  variant={isActive ? "default" : "ghost"}
                  size="sm"
                  onClick={() => {
                    onTimeRangeChange?.(range);
                    setHoveredIndex(null);
                  }}
                  className={`h-7 px-3 text-xs font-mono uppercase transition-all ${
                    isActive
                      ? "bg-primary text-primary-foreground font-bold shadow-xs ring-1 ring-primary/30"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                  }`}
                >
                  {range}
                </Button>
              );
            })}
          </div>

          {/* Right: Hover Inspection Stats */}
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

        {/* High-Resolution SVG Canvas */}
        <div className="h-[360px] rounded-xl border border-input bg-surface-deep overflow-hidden relative group">
          {isLoading && !telemetryData && (
            <div className="absolute inset-0 bg-background/50 backdrop-blur-xs flex items-center justify-center z-10">
              <RefreshCw className="size-6 text-primary animate-spin" />
            </div>
          )}

          <svg
            className="h-full w-full cursor-crosshair select-none"
            viewBox="0 0 800 280"
            preserveAspectRatio="none"
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <defs>
              <linearGradient id="chartVramGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.32" />
                <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="chartCpuGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--info)" stopOpacity="0.2" />
                <stop offset="100%" stopColor="var(--info)" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="chartRamGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.18" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* Horizontal Gridlines & Y-Axis Scale Labels */}
            {[
              { pct: 100, y: 25 },
              { pct: 75, y: 80 },
              { pct: 50, y: 135 },
              { pct: 25, y: 190 },
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

            {/* X-Axis Baseline */}
            <line
              x1={plotGeometry.minX}
              y1={plotGeometry.baselineY}
              x2={plotGeometry.maxX}
              y2={plotGeometry.baselineY}
              stroke="var(--border)"
              strokeWidth="1"
            />

            {/* Filled Areas */}
            <path d={plotGeometry.vramArea} fill="url(#chartVramGradient)" />
            <path d={plotGeometry.cpuArea} fill="url(#chartCpuGradient)" />
            <path d={plotGeometry.ramArea} fill="url(#chartRamGradient)" />

            {/* Spline Lines */}
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

            {/* X-Axis Time Ticks */}
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

            {/* Invisible Hover Slices */}
            {points.map((_, index) => {
              const coord = plotGeometry.vramCoords[index];
              const sliceWidth = (plotGeometry.maxX - plotGeometry.minX) / Math.max(1, points.length);

              return (
                <rect
                  key={index}
                  x={coord.x - sliceWidth / 2}
                  y={plotGeometry.topY}
                  width={sliceWidth}
                  height={plotGeometry.baselineY - plotGeometry.topY}
                  fill="transparent"
                  className="cursor-crosshair"
                  onMouseEnter={() => setHoveredIndex(index)}
                />
              );
            })}

            {/* Active Hover Crosshair Line & Target Markers */}
            {hoveredCoord && hoveredIndex !== null && (
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
                  cy={plotGeometry.vramCoords[hoveredIndex].y}
                  r="4.5"
                  fill="var(--primary)"
                  stroke="var(--background)"
                  strokeWidth="2"
                />

                {/* System RAM Anchor Dot */}
                <circle
                  cx={hoveredCoord.x}
                  cy={plotGeometry.ramCoords[hoveredIndex].y}
                  r="4.5"
                  fill="#10b981"
                  stroke="var(--background)"
                  strokeWidth="2"
                />

                {/* CPU Anchor Dot */}
                <circle
                  cx={hoveredCoord.x}
                  cy={plotGeometry.cpuCoords[hoveredIndex].y}
                  r="4.5"
                  fill="var(--info)"
                  stroke="var(--background)"
                  strokeWidth="2"
                />

                {/* Active Tasks Anchor Dot */}
                <circle
                  cx={hoveredCoord.x}
                  cy={plotGeometry.taskCoords[hoveredIndex].y}
                  r="4.5"
                  fill="var(--warning)"
                  stroke="var(--background)"
                  strokeWidth="2"
                />
              </g>
            )}
          </svg>
        </div>

        {/* Bottom Footer: Legends on Left, Auto-refresh status on Right */}
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
      </CardContent>
    </Card>
  );
}
