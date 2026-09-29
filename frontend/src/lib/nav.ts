import {
  Activity,
  BookOpen,
  FileText,
  History,
  LayoutDashboard,
  MessagesSquare,
  Radio,
  Settings,
  type LucideIcon,
} from "lucide-react";
import type { TKey } from "@/i18n";

export interface NavItem {
  to: string;
  label: TKey;
  icon: LucideIcon;
  group: "groupWork" | "groupData" | "groupSystem";
  shortcut?: string;
}

export const NAV: NavItem[] = [
  { to: "/", label: "nav.overview", icon: LayoutDashboard, group: "groupWork", shortcut: "G O" },
  { to: "/live", label: "nav.live", icon: Activity, group: "groupWork", shortcut: "G L" },
  { to: "/files", label: "nav.files", icon: FileText, group: "groupData", shortcut: "G F" },
  { to: "/messages", label: "nav.messages", icon: MessagesSquare, group: "groupData" },
  { to: "/channels", label: "nav.channels", icon: Radio, group: "groupData", shortcut: "G C" },
  { to: "/subjects", label: "nav.subjects", icon: BookOpen, group: "groupData", shortcut: "G S" },
  { to: "/runs", label: "nav.runs", icon: History, group: "groupSystem", shortcut: "G R" },
  { to: "/settings", label: "nav.settings", icon: Settings, group: "groupSystem" },
];
