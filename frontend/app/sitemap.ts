import type { MetadataRoute } from "next";

import { listCaseIds } from "@/lib/server/data";
import { SITE } from "@/lib/site";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE.url}/`, lastModified: now, changeFrequency: "hourly", priority: 1 },
    { url: `${SITE.url}/privacy-policy`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE.url}/terms-and-conditions`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
  ];
  const cases = (await listCaseIds()).map((id) => ({
    url: `${SITE.url}/cases/${id}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));
  return [...staticRoutes, ...cases];
}
