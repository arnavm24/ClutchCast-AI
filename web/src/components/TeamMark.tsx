"use client";

import { logoFor, teamColor } from "@/lib/nba";

export default function TeamMark({ tricode, size = 44 }: { tricode: string; size?: number }) {
  const logo = logoFor(tricode);
  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/15 bg-white/5"
      style={{ width: size, height: size }}
    >
      <span className="absolute text-[0.6em] font-black" style={{ color: teamColor(tricode) }}>
        {tricode}
      </span>
      {logo && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logo}
          alt={`${tricode} logo`}
          className="absolute inset-0 h-full w-full object-contain p-1"
          loading="lazy"
        />
      )}
    </span>
  );
}
