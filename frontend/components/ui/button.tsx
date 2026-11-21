"use client";

import { cn } from "@/lib/utils";
import React, { ReactNode, forwardRef } from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  children: ReactNode;
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant = "secondary", size = "md", children, asChild, type = "button", ...props },
    ref
  ) => {
    const variants = {
      primary:
        "bg-gradient-to-r from-accent to-accent-dim text-white font-semibold shadow-lg shadow-accent/20 hover:brightness-110",
      secondary: "bg-surface-2 text-foreground border border-border hover:bg-surface-3",
      ghost: "text-muted hover:text-foreground hover:bg-white/5",
      danger: "bg-error/10 text-error border border-error/40 hover:bg-error/20",
    };

    const sizes = {
      sm: "px-3 py-1.5 text-sm rounded-lg",
      md: "px-4 py-2 text-sm rounded-xl",
      lg: "px-6 py-3 text-base rounded-xl",
    };

    const classes = cn(
      "inline-flex items-center justify-center gap-2 transition-all duration-200 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed",
      variants[variant],
      sizes[size],
      className
    );

    if (asChild && React.isValidElement(children)) {
      // Anchors cannot take a button type or a disabled attribute.
      const child = children as React.ReactElement<{ className?: string }>;
      const { disabled: _disabled, ...anchorProps } = props;
      return React.cloneElement(child, {
        className: cn(classes, child.props.className),
        ...anchorProps,
      });
    }

    return (
      <button ref={ref} type={type} className={classes} {...props}>
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
