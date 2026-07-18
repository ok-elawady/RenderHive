"use client";

import { ArrowUpRight, ShieldCheck, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface KpiCardsProps {
  activeJobs: number;
  farmEfficiency: number;
}

export default function KpiCards({ activeJobs, farmEfficiency }: KpiCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Total Nodes
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <p className="text-3xl font-bold tracking-tight text-foreground">1,024</p>
          <p className="text-xs font-mono text-success flex items-center gap-1">
            <ArrowUpRight size={14} /> +12 online
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Active Jobs
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <p className="text-3xl font-bold tracking-tight text-foreground">{activeJobs}</p>
          <p className="text-xs font-mono text-primary flex items-center gap-1">
            <Zap size={14} /> Processing
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Farm Efficiency
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-3xl font-bold tracking-tight text-foreground">{farmEfficiency}%</p>
          <Progress value={farmEfficiency} className="h-1.5" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            System Status
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <div className="flex items-center gap-2 text-xl font-bold text-success">
            <ShieldCheck size={22} />
            Optimal
          </div>
          <p className="text-[11px] font-mono text-muted-foreground">Lat: 12ms / Packets: OK</p>
        </CardContent>
      </Card>
    </div>
  );
}
