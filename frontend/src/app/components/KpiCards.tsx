"use client";

import { ArrowUpRight, ShieldCheck } from "lucide-react";

interface KpiCardsProps {
  activeJobs: number;
  farmEfficiency: number;
}

export default function KpiCards({ activeJobs, farmEfficiency }: KpiCardsProps) {
  const cardClass =
    "bg-[#FFFFFF] dark:bg-[#171A24] border border-[#D7DBE3] dark:border-[#343B4D] p-6 rounded-lg space-y-2 hover:border-[#5A1FA6] transition-all shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.18)]";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-wider text-[#6B7280] dark:text-[#8A92A5]">
          Total Nodes
        </p>
        <p className="text-3xl font-bold tracking-tight text-[#1A1D23] dark:text-[#F5F7FA]">
          1,024
        </p>
        <p className="text-xs font-mono text-[#3DDC84] flex items-center gap-1">
          <ArrowUpRight size={14} /> +12 online
        </p>
      </div>

      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-wider text-[#6B7280] dark:text-[#8A92A5]">
          Active Jobs
        </p>
        <p className="text-3xl font-bold tracking-tight text-[#1A1D23] dark:text-[#F5F7FA]">
          {activeJobs}
        </p>
        <p className="text-xs font-mono text-[#5A1FA6]">
          {"\u26A1"} Processing
        </p>
      </div>

      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-wider text-[#6B7280] dark:text-[#8A92A5]">
          Farm Efficiency
        </p>
        <p className="text-3xl font-bold tracking-tight text-[#1A1D23] dark:text-[#F5F7FA]">
          {farmEfficiency}%
        </p>
        <div className="w-full bg-[#E7E9EF] dark:bg-[#2A3040] h-1.5 rounded-full overflow-hidden mt-2">
          <div
            className="bg-gradient-to-r from-[#5A1FA6] to-[#7A39D9] h-full transition-all duration-700 shadow-[0_0_10px_rgba(90,31,166,0.4)]"
            style={{ width: `${farmEfficiency}%` }}
          ></div>
        </div>
      </div>

      <div className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-wider text-[#6B7280] dark:text-[#8A92A5]">
          System Status
        </p>
        <div className="flex items-center gap-2 text-xl font-bold text-[#3DDC84]">
          <ShieldCheck size={22} />
          Optimal
        </div>
        <p className="text-[11px] font-mono text-[#6B7280] dark:text-[#8A92A5]">
          Lat: 12ms / Packets: OK
        </p>
      </div>
    </div>
  );
}
