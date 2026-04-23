"use client";

import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "subtle" | "success" | "warning" | "accent" | "error";
  className?: string;
}

export function Badge({ children, variant = "subtle", className }: BadgeProps) {
  const variants = {
    subtle: "bg-surface-2 text-muted border-border",
    success: "bg-success/10 text-success border-success/20",
    warning: "bg-warning/10 text-warning border-warning/20",
    accent: "bg-accent/10 text-accent border-accent/20",
    error: "bg-error/10 text-error border-error/20",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
