"use client";

import { cn } from "@/lib/utils";
import { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes, useId } from "react";

interface FieldProps {
  label: string;
  hint?: string;
  children: (id: string) => ReactNode;
  className?: string;
}

/** Label + control + hint, with the id wiring done once for the whole app. */
export function Field({ label, hint, children, className }: FieldProps) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-xs font-medium text-muted mb-1.5">
        {label}
      </label>
      {children(id)}
      {hint && <p className="text-[11px] text-muted mt-1.5 leading-relaxed">{hint}</p>}
    </div>
  );
}

const controlClass =
  "w-full rounded-lg bg-surface-2 border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:border-accent/60 transition-colors";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(controlClass, props.className)} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(controlClass, "resize-y", props.className)} />;
}

export function Select({ children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={cn(controlClass, props.className)}>
      {children}
    </select>
  );
}

export function SectionTitle({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 mb-4">
      <div>
        <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
        {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function ErrorBanner({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-error/40 bg-error/10 px-3 py-2.5"
    >
      <div className="flex-1 min-w-0">
        <p className="text-xs text-error break-words">{message}</p>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="text-[11px] text-muted hover:text-foreground shrink-0"
      >
        Dismiss
      </button>
    </div>
  );
}

export function EmptyState({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border px-4 py-10 text-center">
      <div className="flex justify-center mb-3 text-muted">{icon}</div>
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs text-muted mt-1 max-w-sm mx-auto leading-relaxed">{body}</p>
    </div>
  );
}
