"use client";

function SkeletonBlock({ className }: { className: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-[#E7E9EF] dark:bg-[#2A3040] ${className}`}
    />
  );
}

export function KpiCardsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }, (_, index) => (
        <div
          key={index}
          className="bg-[#FFFFFF] dark:bg-[#171A24] border border-[#D7DBE3] dark:border-[#343B4D] p-6 rounded-lg space-y-4 shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.18)]"
        >
          <SkeletonBlock className="h-3 w-24" />
          <SkeletonBlock className="h-8 w-20" />
          <SkeletonBlock className="h-3 w-32" />
        </div>
      ))}
    </div>
  );
}

export function JobQueueSkeleton() {
  return (
    <div className="bg-[#FFFFFF] dark:bg-[#171A24] border border-[#D7DBE3] dark:border-[#343B4D] p-6 rounded-lg h-full shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.22)]">
      <div className="flex items-center justify-between mb-6">
        <SkeletonBlock className="h-4 w-36" />
        <SkeletonBlock className="h-3 w-14" />
      </div>

      <div className="rounded-lg border border-[#D7DBE3] dark:border-[#2A3143] overflow-hidden">
        <div className="grid grid-cols-5 gap-4 bg-[#F1F3F6] dark:bg-[#171C26] px-4 py-3">
          {Array.from({ length: 5 }, (_, index) => (
            <SkeletonBlock key={index} className="h-3 w-full" />
          ))}
        </div>
        <div className="divide-y divide-[#D7DBE3] dark:divide-[#2A3143]">
          {Array.from({ length: 4 }, (_, rowIndex) => (
            <div
              key={rowIndex}
              className="grid grid-cols-5 gap-4 bg-[#FFFFFF] dark:bg-[#11161F] px-4 py-4"
            >
              {Array.from({ length: 5 }, (_, columnIndex) => (
                <SkeletonBlock key={columnIndex} className="h-3 w-full" />
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
