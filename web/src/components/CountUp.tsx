"use client";

import { animate, useInView } from "framer-motion";
import { useEffect, useRef } from "react";

export default function CountUp({
  value,
  decimals = 0,
  suffix = "",
  className,
  duration = 1.1,
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });

  useEffect(() => {
    if (!inView || !ref.current) return;
    const controls = animate(0, value, {
      duration,
      ease: "easeOut",
      onUpdate: (latest) => {
        if (ref.current) ref.current.textContent = latest.toFixed(decimals) + suffix;
      },
    });
    return () => controls.stop();
  }, [inView, value, decimals, suffix, duration]);

  return (
    <span ref={ref} className={className}>
      {(0).toFixed(decimals)}
      {suffix}
    </span>
  );
}
