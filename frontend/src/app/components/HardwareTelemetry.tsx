"use client";

import { useMemo, useState } from "react";
import { Cpu as CpuIcon, X } from "lucide-react";
import type {
  TelemetryMetrics,
  TelemetryPoint,
} from "../types/dashboard";

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

export default function HardwareTelemetry({
  telemetry,
}: HardwareTelemetryProps) {
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [animationKey, setAnimationKey] = useState<number>(0);
  const points =
    telemetry.points.length > 0 ? telemetry.points : fallbackPoints;

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

  const closeModal = (): void => {
    setIsModalOpen(false);
  };

  return (
    <>
      <div className="bg-[#FFFFFF] dark:bg-[#171A24] border border-[#D7DBE3] dark:border-[#343B4D] p-6 rounded-lg space-y-6 shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.22)]">
        <div className="flex items-center gap-2">
          <CpuIcon className="text-[#5A1FA6]" size={18} />
          <h3 className="text-base font-bold text-[#1A1D23] dark:text-[#F5F7FA]">
            Hardware Utilization
          </h3>
        </div>

        <div className="space-y-4 text-xs font-mono">
          <div className="space-y-1.5">
            <div className="flex justify-between text-[#6B7280] dark:text-[#8A92A5]">
              <span>VRAM Usage</span>
              <span className="text-[#5A1FA6] font-bold">
                {telemetry.vramUsage}%
              </span>
            </div>
            <div className="w-full bg-[#E7E9EF] dark:bg-[#2A3040] h-2 rounded-full overflow-hidden">
              <div
                className="bg-gradient-to-r from-[#5A1FA6] to-[#7A39D9] h-full transition-all duration-700 shadow-[0_0_10px_rgba(90,31,166,0.4)]"
                style={{ width: `${telemetry.vramUsage}%` }}
              ></div>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between text-[#6B7280] dark:text-[#8A92A5]">
              <span>CPU Cluster Load</span>
              <span className="text-[#5A1FA6] font-bold">
                {telemetry.cpuLoad}%
              </span>
            </div>
            <div className="w-full bg-[#E7E9EF] dark:bg-[#2A3040] h-2 rounded-full overflow-hidden">
              <div
                className="bg-gradient-to-r from-[#5A1FA6] to-[#7A39D9] h-full transition-all duration-700 shadow-[0_0_10px_rgba(90,31,166,0.4)]"
                style={{ width: `${telemetry.cpuLoad}%` }}
              ></div>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={openModal}
          className="w-full pt-2 text-left cursor-pointer group"
          aria-label="Open telemetry history analytics"
        >
          <p className="text-[11px] font-mono text-[#6B7280] dark:text-[#8A92A5] mb-2">
            Telemetry History (24h)
          </p>
          <div className="w-full h-32 bg-[#F7F8FA] dark:bg-[#1F2330] rounded-lg border border-[#D7DBE3] dark:border-[#2A3143] relative overflow-hidden flex items-end transition-all duration-300 group-hover:border-[#5A1FA6] group-hover:shadow-[0_0_18px_rgba(90,31,166,0.18)]">
            <svg
              className="w-full h-full p-1"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              <defs>
                <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#5A1FA6" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#5A1FA6" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d={chartPaths.vramArea} fill="url(#chartGradient)" />
              <path
                d={chartPaths.vramLine}
                fill="none"
                stroke="#9C73F2"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </div>
        </button>
      </div>

      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={closeModal}
        >
          <div
            className="w-full max-w-5xl bg-[#FFFFFF] dark:bg-[#171A24] border border-[#D7DBE3] dark:border-[#343B4D] rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/90 overflow-hidden animate-[modalPopIn_0.3s_ease-out_forwards]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#D7DBE3] dark:border-[#343B4D] px-6 py-4 bg-[#F7F8FA]/80 dark:bg-[#0E1016]/40">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#6B7280] dark:text-[#8A92A5]">
                  Backend Micro-Analytics
                </p>
                <h3 className="mt-1 text-lg font-bold text-[#1A1D23] dark:text-[#F5F7FA]">
                  Telemetry History (24h)
                </h3>
              </div>
              <button
                type="button"
                onClick={closeModal}
                className="text-[#6B7280] dark:text-[#8A92A5] hover:text-[#1A1D23] dark:hover:text-[#F5F7FA] transition-colors cursor-pointer"
                aria-label="Close telemetry analytics"
              >
                <X size={22} />
              </button>
            </div>

            <div className="p-6">
              <div className="mb-4 flex flex-wrap items-center gap-4 text-xs font-mono text-[#6B7280] dark:text-[#8A92A5]">
                <span className="inline-flex items-center gap-2">
                  <span className="h-2 w-4 rounded-full bg-[#5A1FA6]"></span>
                  VRAM Usage
                </span>
                <span className="inline-flex items-center gap-2">
                  <span className="h-2 w-4 rounded-full bg-[#4DA3FF]"></span>
                  CPU Cluster Load
                </span>
              </div>

              <div className="h-[420px] rounded-xl border border-[#D7DBE3] dark:border-[#2A3143] bg-[#F7F8FA] dark:bg-[#11161F] overflow-hidden">
                <svg
                  key={animationKey}
                  className="h-full w-full p-5"
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                >
                  <defs>
                    <linearGradient
                      id="vramModalGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor="#5A1FA6"
                        stopOpacity="0.28"
                      />
                      <stop offset="100%" stopColor="#5A1FA6" stopOpacity="0" />
                    </linearGradient>
                    <linearGradient
                      id="cpuModalGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor="#4DA3FF"
                        stopOpacity="0.18"
                      />
                      <stop offset="100%" stopColor="#4DA3FF" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <g className="telemetry-area-sweep">
                    <path
                      d={chartPaths.vramArea}
                      fill="url(#vramModalGradient)"
                    />
                    <path
                      d={chartPaths.cpuArea}
                      fill="url(#cpuModalGradient)"
                    />
                  </g>
                  <path
                    d={chartPaths.vramLine}
                    className="telemetry-line-sweep"
                    pathLength={1}
                    fill="none"
                    stroke="#5A1FA6"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d={chartPaths.cpuLine}
                    className="telemetry-line-sweep telemetry-line-sweep-delayed"
                    pathLength={1}
                    fill="none"
                    stroke="#4DA3FF"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
