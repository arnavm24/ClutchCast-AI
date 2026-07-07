import type { MetadataRoute } from "next";
import { listAnalyzedGameIds } from "@/lib/data";

const BASE = "https://clutchcast-ai.vercel.app";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const gameIds = await listAnalyzedGameIds();
  return [
    { url: BASE, changeFrequency: "daily", priority: 1 },
    { url: `${BASE}/models`, changeFrequency: "weekly", priority: 0.8 },
    ...gameIds.map((id) => ({
      url: `${BASE}/game/${id}`,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
  ];
}
