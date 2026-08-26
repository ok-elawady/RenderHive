"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  backTo?: string;
  onBack?: () => void;
  children?: React.ReactNode;
}

export function PageHeader({ title, description, backTo, onBack, children }: PageHeaderProps) {
  const router = useRouter();

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else if (backTo) {
      router.push(backTo);
    } else {
      router.back();
    }
  };

  const showBackButton = !!backTo || !!onBack;

  return (
    <div className="flex items-center justify-between gap-4 border-b border-border bg-card px-6 py-3">
      <div className="flex items-center gap-4">
        {showBackButton && (
          <Button variant="ghost" size="icon" onClick={handleBack} aria-label="Go back" className="shrink-0">
            <ArrowLeft size={18} />
          </Button>
        )}
        <div>
          <h1 className="text-lg font-black tracking-tight">{title}</h1>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      </div>
      {children && (
        <div className="flex items-center gap-2">
          {children}
        </div>
      )}
    </div>
  );
}
