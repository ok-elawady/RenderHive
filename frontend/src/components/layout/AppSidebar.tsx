"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Cpu, LayoutDashboard, ListOrdered, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
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
import { GlobalSearch } from "@/components/layout/GlobalSearch";

import type { SidebarItem } from "@/types/dashboard";

const sidebarItems: SidebarItem[] = [
  { icon: <LayoutDashboard size={18} />, label: "Dashboard", href: "/" },
  { icon: <ListOrdered size={18} />, label: "Active Queue", href: "/jobs" },
  { icon: <Cpu size={18} />, label: "Node Pool", href: "/nodes" },
  { icon: <Bot size={18} />, label: "AI Rules", href: "/logs" },
  { icon: <Settings size={18} />, label: "Settings", href: "/settings" },
];

export default function AppSidebar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();
  const displayName = user?.displayName ?? "RenderHive User";
  const role = user?.role ?? "Authenticated";
  const initials = user?.initials ?? "RH";

  return (
    <Sidebar className="border-r-0">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              render={<Link href="/" className="cursor-pointer" />}
            >
              <div className="relative flex aspect-square size-10 items-center justify-center shrink-0 mr-1">
                <Image
                  src="/Logo2.png"
                  alt="RenderHive Logo"
                  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                  loading="eager"
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
            <SidebarMenuItem className="mb-2 px-2">
              <GlobalSearch />
            </SidebarMenuItem>
            {sidebarItems.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);

              return (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton
                    isActive={isActive}
                    render={<Link href={item.href} />}
                    tooltip={item.label}
                  >
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
            <SidebarMenuButton
              size="lg"
              render={<Link href="/settings" className="cursor-pointer" />}
              tooltip="Account Settings"
            >
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#d01fc7] to-primary text-xs font-bold text-white shrink-0">
                {initials}
              </div>
              <div className="flex flex-col gap-0.5 leading-none">
                <span className="font-semibold text-foreground text-sm">{displayName}</span>
                <span className="text-[10px] text-primary font-mono">{role}</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={logout}>
              <LogOut size={16} />
              <span>Sign Out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
