import type { Metadata, Viewport } from "next";

import { Analytics } from "@/components/Analytics";
import { CookieConsent } from "@/components/CookieConsent";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { SITE } from "@/lib/site";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: { default: `${SITE.name} | Fraud cases on TigerGraph`, template: `%s | ${SITE.shortName}` },
  description: SITE.description,
  applicationName: SITE.name,
  keywords: ["fraud investigation", "TigerGraph", "GraphRAG", "MCP", "LangGraph", "IEEE-CIS", "next best action"],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: SITE.name,
    title: SITE.name,
    description: SITE.description,
    url: "/",
    locale: "en_US",
  },
  twitter: { card: "summary_large_image", title: SITE.name, description: SITE.description },
  robots: { index: true, follow: true },
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  themeColor: "#eaf1f1",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {process.env.NODE_ENV === "production" && (
          <meta httpEquiv="Content-Security-Policy" content="upgrade-insecure-requests" />
        )}
      </head>
      <body className="min-h-screen">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-xl focus:bg-surface focus:px-4 focus:py-2 focus:shadow-neu"
        >
          Skip to content
        </a>
        <SiteHeader />
        <main id="main" className="mx-auto w-full max-w-7xl px-4 pb-24 pt-6 sm:px-6 lg:px-8">
          {children}
        </main>
        <SiteFooter />
        <CookieConsent />
        <Analytics />
      </body>
    </html>
  );
}
