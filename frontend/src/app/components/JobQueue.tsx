"use client";

import { useMemo } from "react";
import { Search } from "lucide-react";
import type { JobPriority, RenderJob } from "../types/dashboard";

interface JobQueueProps {
  jobs: RenderJob[];
  searchQuery: string;
}

function getPriorityClass(priority: JobPriority): string {
  if (priority === "HIGH") return "text-[#FF5D73]";
  if (priority === "MED") return "text-[#FFB84D]";
  return "text-[#6B7280] dark:text-[#8A92A5]";
}

function matchesJobSearch(job: RenderJob, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;

  return [job.id, job.node, job.status].some((value) =>
    value.toLowerCase().includes(normalizedQuery),
  );
}

export default function JobQueue({ jobs, searchQuery }: JobQueueProps) {
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredJobs = useMemo<RenderJob[]>(
    () => jobs.filter((job) => matchesJobSearch(job, normalizedQuery)),
    [jobs, normalizedQuery],
  );

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#171A24] border border-[#D7DBE3] dark:border-[#343B4D] p-6 rounded-lg flex flex-col justify-between h-full shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.22)]">
      <div>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-base font-bold text-[#1A1D23] dark:text-[#F5F7FA]">
            Live Job Queue
          </h3>
          <button className="text-xs font-semibold text-[#5A1FA6] hover:text-[#6C2AC4] hover:underline">
            View All
          </button>
        </div>

        <div className="overflow-x-auto rounded-lg border border-[#D7DBE3] dark:border-[#2A3143]">
          <table className="w-full text-left border-collapse">
            <thead className="bg-[#F1F3F6] dark:bg-[#171C26]">
              <tr className="border-b border-[#D7DBE3] dark:border-[#2A3143] text-[11px] font-bold uppercase tracking-wider text-[#6B7280] dark:text-[#8A92A5]">
                <th className="px-4 py-3 font-medium">Job ID</th>
                <th className="px-4 py-3 font-medium">Priority</th>
                <th className="px-4 py-3 font-medium">Assigned Node</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Progress</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#D7DBE3] dark:divide-[#2A3143] text-xs font-mono">
              {filteredJobs.length > 0 ? (
                filteredJobs.map((job) => (
                  <tr
                    key={job.id}
                    className="bg-[#FFFFFF] dark:bg-[#11161F] hover:bg-[#F1F3F6] dark:hover:bg-[#1E2433] transition-all group"
                  >
                    <td className="px-4 py-4 font-medium text-[#1A1D23] dark:text-[#D7DBE5] group-hover:text-[#5A1FA6] transition-colors">
                      {job.id}
                    </td>
                    <td
                      className={`px-4 py-4 font-bold text-[10px] ${getPriorityClass(job.priority)}`}
                    >
                      {job.priority}
                    </td>
                    <td className="px-4 py-4 text-[#6B7280] dark:text-[#8A92A5]">
                      {job.node}
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] border ${job.statusColor}`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <span className="text-[#6B7280] dark:text-[#8A92A5] w-8 text-right">
                          {job.progress}%
                        </span>
                        <div className="w-20 bg-[#E7E9EF] dark:bg-[#2A3040] h-1 rounded-full overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-[#5A1FA6] to-[#7A39D9] h-full transition-all duration-500 shadow-[0_0_10px_rgba(90,31,166,0.4)]"
                            style={{ width: `${job.progress}%` }}
                          ></div>
                        </div>
                        <span className="text-[11px] text-[#6B7280] dark:text-[#8A92A5] w-12 text-left">
                          {job.eta}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="bg-[#FFFFFF] dark:bg-[#11161F]">
                  <td colSpan={5} className="px-4 py-14">
                    <div className="flex flex-col items-center justify-center text-center">
                      <Search
                        size={34}
                        className="mb-3 text-[#5A1FA6] opacity-25"
                      />
                      <p className="text-sm font-bold text-[#1A1D23] dark:text-[#F5F7FA]">
                        No matching active render jobs found
                      </p>
                      <p className="mt-1 text-xs text-[#6B7280] dark:text-[#8A92A5]">
                        Try a Job ID, node name, or status keyword.
                      </p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
