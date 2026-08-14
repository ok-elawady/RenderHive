"use client";

import { ReactNode } from "react";
import { AlertTriangle, AlertCircle, Info, Loader2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ConfirmDialogVariant = "destructive" | "warning" | "info" | "default";

export interface ConfirmDialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: ReactNode;
  title: ReactNode;
  description: ReactNode;
  variant?: ConfirmDialogVariant;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void | Promise<void>;
  isLoading?: boolean;
  className?: string;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  trigger,
  title,
  description,
  variant = "default",
  confirmText = "Confirm",
  cancelText = "Cancel",
  onConfirm,
  isLoading = false,
  className,
}: ConfirmDialogProps) {
  const isDestructive = variant === "destructive";
  const isWarning = variant === "warning";
  const isInfo = variant === "info" || variant === "default";

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      {trigger && <AlertDialogTrigger render={trigger as never} />}
      <AlertDialogContent className={cn("sm:max-w-md p-6 border-border bg-card", className)}>
        <AlertDialogHeader className="sm:text-center">
          {/* Variant Icon Badge */}
          <div className="mx-auto flex size-12 items-center justify-center rounded-full mb-3 shrink-0">
            {isDestructive && (
              <div className="flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive border border-destructive/20">
                <AlertTriangle className="size-6" />
              </div>
            )}
            {isWarning && (
              <div className="flex size-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/20">
                <AlertCircle className="size-6" />
              </div>
            )}
            {isInfo && (
              <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary border border-primary/20">
                <Info className="size-6" />
              </div>
            )}
          </div>

          <AlertDialogTitle className="text-center text-lg font-bold text-foreground">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-center text-xs text-muted-foreground leading-relaxed pt-1 max-w-sm mx-auto">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter className="sm:justify-center gap-2 pt-2">
          <AlertDialogCancel disabled={isLoading}>
            {cancelText}
          </AlertDialogCancel>
          <Button
            variant={isDestructive ? "destructive" : "default"}
            disabled={isLoading}
            onClick={async (e) => {
              e.preventDefault();
              await onConfirm();
              if (onOpenChange) {
                onOpenChange(false);
              }
            }}
          >
            {isLoading && <Loader2 className="mr-2 size-4 animate-spin" />}
            {confirmText}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
