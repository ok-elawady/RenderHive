"use client";

import Image from "next/image";
import { Bot, Cpu, LayoutDashboard, ListOrdered, Settings } from "lucide-react";
import { useNavigation } from "./NavigationProvider";
import type { SidebarItem } from "../types/dashboard";

const sidebarItems: SidebarItem[] = [
  { icon: <LayoutDashboard size={20} />, label: "Dashboard" },
  { icon: <ListOrdered size={20} />, label: "Active Queue" },
  { icon: <Cpu size={20} />, label: "Node Pool" },
  { icon: <Bot size={20} />, label: "AI Rules" },
  { icon: <Settings size={20} />, label: "Settings" },
];

export default function AppSidebar() {
  const { activeView, setActiveView } = useNavigation();

  return (
    <aside className="w-64 bg-[#FFFFFF] dark:bg-[#171A24] border-r border-[#D7DBE3] dark:border-[#343B4D] flex flex-col justify-between p-6 shrink-0 select-none">
      <div>
        <div className="flex items-center gap-3 mb-10 pl-2">
          <div className="relative h-9 w-9 shrink-0">
            <Image
              src="/Logo2.png"
              alt="RenderHive Logo"
              width={66}
              height={66}
              className="object-contain"
              priority
            />
          </div>
          <div className="flex flex-col font-mono">
            <span className="text-xl font-black tracking-wider bg-gradient-to-r from-[#1A1D23] to-[#6B7280] dark:from-[#FFFFFF] dark:to-[#AAABAD] bg-clip-text text-transparent">
              Render<span className="text-[#9C73F2]">Hive</span>
            </span>
            <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#6B7280] dark:text-[#8A92A5] -mt-0.5">
              RENDER MANAGEMENT
            </span>
          </div>
        </div>

        <nav className="space-y-2">
          {sidebarItems.map((item) => {
            const isActive = activeView === item.label;

            return (
              <button
                key={item.label}
                type="button"
                onClick={() => setActiveView(item.label)}
                className={`w-full flex items-center gap-4 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer ${
                  isActive
                    ? "bg-[#5A1FA6] hover:bg-[#6C2AC4] text-[#F5F7FA] shadow-lg shadow-[#5A1FA6]/25"
                    : "text-[#6B7280] dark:text-[#8A92A5] hover:bg-[#F1F3F6] dark:hover:bg-[#1F2330] hover:text-[#1A1D23] dark:hover:text-[#F5F7FA]"
                }`}
              >
                {item.icon}
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="border-t border-[#D7DBE3] dark:border-[#2A3143] pt-4 flex items-center gap-3 pl-2">
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-[#d01fc7] to-[#9C73F2] flex items-center justify-center font-bold text-xs text-[#F5F7FA]">
          SA
        </div>
        <div>
          <p className="text-xs font-semibold text-[#1A1D23] dark:text-[#D7DBE5]">
            Seif Ashraf
          </p>
          <p className="text-[10px] text-[#9C73F2] font-mono">TD Admin</p>
        </div>
      </div>
    </aside>
  );
}
