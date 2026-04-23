"use client";

import { cn } from "@/lib/utils";

interface ProgressProps {
  value: number;
  className?: string;
  "aria-label"?: string;
}

export function Progress({ value, className, "aria-label": ariaLabel }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div
      className={cn("h-2.5 w-full rounded-full bg-surface-2 overflow-hidden", className)}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={ariaLabel || "Progress"}
    >
      <div
        className="h-full rounded-full bg-gradient-to-r from-accent to-indigo-400 transition-all duration-700 ease-out"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
