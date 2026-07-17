"use client";

import { ArrowUpRight, ShieldCheck } from "lucide-react";

interface KpiCardsProps {
  activeJobs: number;
  farmEfficiency: number;
}

export default function KpiCards({ activeJobs, farmEfficiency }: KpiCardsProps) {
  const cardClass =
    "bg-surface border border-border p-6 rounded-lg space-y-2 hover:border-primary transition-all shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.18)]";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Total Nodes
        </p>
        <p className="text-3xl font-bold tracking-tight text-foreground">
          1,024
        </p>
        <p className="text-xs font-mono text-success flex items-center gap-1">
          <ArrowUpRight size={14} /> +12 online
        </p>
      </div>

      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Active Jobs
        </p>
        <p className="text-3xl font-bold tracking-tight text-foreground">
          {activeJobs}
        </p>
        <p className="text-xs font-mono text-primary">
          {"\u26A1"} Processing
        </p>
      </div>

      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Farm Efficiency
        </p>
        <p className="text-3xl font-bold tracking-tight text-foreground">
          {farmEfficiency}%
        </p>
        <div className="w-full bg-input h-1.5 rounded-full overflow-hidden mt-2">
          <div
            className="bg-gradient-to-r from-primary to-primary/80 h-full transition-all duration-700 shadow-[0_0_10px] shadow-primary/40"
            style={{ width: `${farmEfficiency}%` }}
          ></div>
        </div>
      </div>

      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          System Status
        </p>
        <div className="flex items-center gap-2 text-xl font-bold text-success">
          <ShieldCheck size={22} />
          Optimal
        </div>
        <p className="text-[11px] font-mono text-muted-foreground">
          Lat: 12ms / Packets: OK
        </p>
      </div>
    </div>
  );
}
