import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function StatChip({
  icon: Icon,
  label,
  value,
  tooltip,
}: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
  tooltip?: string;
}) {
  const inner = (
    <div className="flex flex-col items-center justify-center gap-1 px-4 py-3 hover:bg-muted/40 transition-colors h-full w-full text-center">
      <div className="flex items-center justify-center gap-1.5 text-muted-foreground/80">
        <Icon size={14} className="shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <span className="text-[13px] font-mono font-bold text-foreground/90 truncate w-full text-center">{value}</span>
    </div>
  );

  if (!tooltip) return <div className="h-full w-full block">{inner}</div>;

  return (
    <Tooltip>
      <TooltipTrigger render={<div className="cursor-help h-full w-full block" />}>
        {inner}
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-xs">
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
}
