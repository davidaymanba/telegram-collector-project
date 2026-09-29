import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("h-7 w-7 shrink-0", className)}>
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path
        d="M9 11h14M16 11v12M11 17l5 6 5-6"
        className="stroke-primary-foreground"
        strokeWidth="2.4"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
