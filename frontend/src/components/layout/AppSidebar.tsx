"use client";

import Image from "next/image";
import { Bot, Cpu, LayoutDashboard, ListOrdered, Settings } from "lucide-react";
import { useNavigation } from "@/components/common/NavigationProvider";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

import type { SidebarItem } from "@/types/dashboard";

const sidebarItems: SidebarItem[] = [
  { icon: <LayoutDashboard size={18} />, label: "Dashboard" },
  { icon: <ListOrdered size={18} />, label: "Active Queue" },
  { icon: <Cpu size={18} />, label: "Node Pool" },
  { icon: <Bot size={18} />, label: "AI Rules" },
  { icon: <Settings size={18} />, label: "Settings" },
];

export default function AppSidebar() {
  const { activeView, setActiveView } = useNavigation();

  return (
    <Sidebar className="border-r-0">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg">
              <div className="relative flex aspect-square size-10 items-center justify-center shrink-0 mr-1">
                <Image
                  src="/Logo2.png"
                  alt="RenderHive Logo"
                  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                  fill
                  className="object-contain"
                />
              </div>
              <div className="flex flex-col gap-0.5 leading-none font-mono">
                <span className="font-black tracking-wider bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
                  Render<span className="text-primary">Hive</span>
                </span>
                <span className="text-[9px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
                  RENDER MANAGEMENT
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Application</SidebarGroupLabel>
          <SidebarMenu>
            {sidebarItems.map((item) => {
              const isActive = activeView === item.label;

              return (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton isActive={isActive} onClick={() => setActiveView(item.label)} tooltip={item.label}>
                    {item.icon}
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg">
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#d01fc7] to-primary text-xs font-bold text-white shrink-0">
                SA
              </div>
              <div className="flex flex-col gap-0.5 leading-none">
                <span className="font-semibold text-foreground text-sm">Seif Ashraf</span>
                <span className="text-[10px] text-primary font-mono">TD Admin</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
