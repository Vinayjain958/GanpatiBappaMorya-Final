import type { LucideIcon } from "lucide-react";
import { Compass, MapPinned, Bookmark, ShieldAlert, Store, UsersRound, Sparkles } from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const primaryNav: NavItem[] = [
  { label: "Discover", href: "/discover", icon: Compass },
  { label: "Trips", href: "/trip", icon: MapPinned },
  { label: "Collab", href: "/collab", icon: UsersRound },
  { label: "Saved", href: "/saved", icon: Bookmark },
  { label: "Safety", href: "/safety", icon: ShieldAlert },
  { label: "Showcase", href: "/showcase", icon: Sparkles },
  { label: "Provider", href: "/provider", icon: Store },
];
