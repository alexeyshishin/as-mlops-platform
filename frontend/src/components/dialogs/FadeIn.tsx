"use client";

import { useEffect, useState, type ReactNode } from "react";

export function FadeIn({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div
      className={`transition-all duration-500 ease-out ${shown ? "opacity-100 translate-y-0" : "translate-y-2 opacity-0"} ${className}`}
    >
      {children}
    </div>
  );
}
