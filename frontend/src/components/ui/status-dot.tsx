export function StatusDot({ online, warning }: { online: boolean; warning?: boolean }) {
  const colorClass = warning ? "bg-amber-500" : online ? "bg-success" : "bg-destructive";
  return (
    <span className="relative flex h-2.5 w-2.5 shrink-0">
      {online && (
        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-60 ${colorClass}`} />
      )}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${colorClass}`} />
    </span>
  );
}
