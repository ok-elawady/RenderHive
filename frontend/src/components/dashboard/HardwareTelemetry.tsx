"use client";

import { useMemo, useState } from "react";
import type { TelemetryMetrics, TelemetryPoint } from "@/types/dashboard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface HardwareTelemetryProps {
  telemetry: TelemetryMetrics;
}

const fallbackPoints: TelemetryPoint[] = [
  { x: 0, vram: 0, cpu: 0 },
  { x: 100, vram: 0, cpu: 0 },
];

function buildLinePath(points: TelemetryPoint[], key: "vram" | "cpu"): string {
  return points
    .map((point, index) => {
      const command = index === 0 ? "M" : "L";
      return `${command}${point.x},${100 - point[key]}`;
    })
    .join(" ");
}

function buildAreaPath(points: TelemetryPoint[], key: "vram" | "cpu"): string {
  const line = buildLinePath(points, key);
  const lastPoint = points[points.length - 1];
  const firstPoint = points[0];

  return `${line} L${lastPoint.x},100 L${firstPoint.x},100 Z`;
}

export default function HardwareTelemetry({ telemetry }: HardwareTelemetryProps) {
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [animationKey, setAnimationKey] = useState<number>(0);
  const points = telemetry.points.length > 0 ? telemetry.points : fallbackPoints;

  const chartPaths = useMemo(
    () => ({
      vramLine: buildLinePath(points, "vram"),
      cpuLine: buildLinePath(points, "cpu"),
      vramArea: buildAreaPath(points, "vram"),
      cpuArea: buildAreaPath(points, "cpu"),
    }),
    [points],
  );

  const openModal = (): void => {
    setAnimationKey((currentKey) => currentKey + 1);
    setIsModalOpen(true);
  };

  return (
    <>
      <Card className="border-border">
        <CardHeader>
          <div className="flex items-center gap-2">
            <CardTitle className="text-base font-bold text-foreground">Hardware Utilization</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4 text-xs font-mono">
            <div className="space-y-1.5">
              <div className="flex justify-between text-muted-foreground">
                <span>VRAM Usage</span>
                <span className="text-primary font-bold">{telemetry.vramUsage}%</span>
              </div>
              <Progress value={telemetry.vramUsage} className="h-2" />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-muted-foreground">
                <span>CPU Cluster Load</span>
                <span className="text-primary font-bold">{telemetry.cpuLoad}%</span>
              </div>
              <Progress value={telemetry.cpuLoad} className="h-2" />
            </div>
          </div>

          <button
            type="button"
            onClick={openModal}
            className="w-full pt-2 text-left cursor-pointer group"
            aria-label="Open telemetry history analytics"
          >
            <p className="text-[11px] font-mono text-muted-foreground mb-2">Telemetry History (24h)</p>
            <div className="w-full h-32 bg-surface-deep rounded-lg border border-input relative overflow-hidden flex items-end transition-all duration-300 group-hover:border-primary group-hover:shadow-[0_0_18px] group-hover:shadow-primary/20">
              <svg className="w-full h-full p-1" viewBox="0 0 100 100" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.35" />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d={chartPaths.vramArea} fill="url(#chartGradient)" />
                <path
                  d={chartPaths.vramLine}
                  fill="none"
                  stroke="var(--primary)"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </button>
        </CardContent>
      </Card>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-5xl p-0 gap-0 overflow-hidden border-border bg-surface shadow-2xl shadow-black/20 dark:shadow-black/90">
          <DialogHeader className="border-b border-border px-6 py-4 bg-background/80">
            <div className="text-left">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                Backend Micro-Analytics
              </p>
              <DialogTitle className="mt-1 text-lg font-bold text-foreground">Telemetry History (24h)</DialogTitle>
            </div>
          </DialogHeader>

          <div className="p-6">
            <div className="mb-4 flex flex-wrap items-center gap-4 text-xs font-mono text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <span className="h-2 w-4 rounded-full bg-primary"></span>
                VRAM Usage
              </span>
              <span className="inline-flex items-center gap-2">
                <span className="h-2 w-4 rounded-full bg-info"></span>
                CPU Cluster Load
              </span>
            </div>

            <div className="h-[420px] rounded-xl border border-input bg-surface-deep overflow-hidden">
              <svg key={animationKey} className="h-full w-full p-5" viewBox="0 0 100 100" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="vramModalGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.28" />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="cpuModalGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--info)" stopOpacity="0.18" />
                    <stop offset="100%" stopColor="var(--info)" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <g className="telemetry-area-sweep">
                  <path d={chartPaths.vramArea} fill="url(#vramModalGradient)" />
                  <path d={chartPaths.cpuArea} fill="url(#cpuModalGradient)" />
                </g>
                <path
                  d={chartPaths.vramLine}
                  className="telemetry-line-sweep"
                  pathLength={1}
                  fill="none"
                  stroke="var(--primary)"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d={chartPaths.cpuLine}
                  className="telemetry-line-sweep telemetry-line-sweep-delayed"
                  pathLength={1}
                  fill="none"
                  stroke="var(--info)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
