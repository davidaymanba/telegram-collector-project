import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";

export const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { indicatorClassName?: string; indeterminate?: boolean }
>(({ className, value, indicatorClassName, indeterminate, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    value={indeterminate ? null : value}
    className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className={cn(
        "h-full rounded-full bg-primary transition-[width] duration-200",
        indeterminate && "w-1/3 animate-soft-pulse",
        indicatorClassName,
      )}
      style={indeterminate ? undefined : { width: `${Math.min(100, Math.max(0, value ?? 0))}%` }}
    />
  </ProgressPrimitive.Root>
));
Progress.displayName = "Progress";
