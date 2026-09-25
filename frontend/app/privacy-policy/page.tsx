import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Privacy",
  description: "What this demo stores, and what it doesn't.",
  alternates: { canonical: "/privacy-policy" },
};

export default function PrivacyPolicyPage() {
  return (
    <LegalPage
      title="Privacy"
      updated="25 September 2026"
      sections={[
        {
          heading: "What this is",
          body: (
            <p>
              HHGOA Fraud Desk is a project built for the Hacker House Goa hackathon. It shows how our agent
              investigated twenty fraud alerts from the HHGOA IEEE-CIS dataset.
            </p>
          ),
        },
        {
          heading: "The data on this site",
          body: (
            <p>
              Every customer, card, device and transaction shown here comes from an anonymised public dataset. None of
              it belongs to a real, identifiable person.
            </p>
          ),
        },
        {
          heading: "What we keep about you",
          body: (
            <>
              <p>
                One setting in your browser&apos;s local storage, to remember your answer to the cookie banner. That&apos;s
                it. We don&apos;t set tracking or advertising cookies.
              </p>
              <p>
                If you click &quot;Accept&quot;, page views and button clicks are counted in your browser&apos;s memory
                and thrown away when you close the tab. They are never sent to us or anyone else.
              </p>
              <p>
                The analyst note form checks what you type but does not save it anywhere, so please don&apos;t enter
                personal information in it.
              </p>
            </>
          ),
        },
        {
          heading: "Security",
          body: <p>The site is served over HTTPS. Keys and passwords for the graph database never reach your browser.</p>,
        },
        {
          heading: "Questions",
          body: (
            <p>
              Clear this site&apos;s data in your browser to reset your choice at any time. For anything else, reach the
              team through the Hacker House Goa submission. The{" "}
              <Link href="/terms-and-conditions" className="font-medium text-accent hover:underline">
                terms
              </Link>{" "}
              cover how the site may be used.
            </p>
          ),
        },
      ]}
    />
  );
}
