"use client";

export function PageSkeleton() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] w-full p-6">
      <div className="animate-pulse flex flex-col items-center justify-center h-full w-full opacity-50 space-y-4">
        <div className="h-12 w-12 rounded-full border-4 border-primary border-t-transparent animate-spin"></div>
        <p className="text-sm font-bold text-muted-foreground uppercase tracking-widest">Loading Dashboard</p>
      </div>
    </div>
  );
}
