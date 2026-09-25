import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Terms",
  description: "Terms for using the HHGOA Fraud Desk demo.",
  alternates: { canonical: "/terms-and-conditions" },
};

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms"
      updated="25 September 2026"
      sections={[
        {
          heading: "It's a demo",
          body: (
            <p>
              This site is a hackathon project. The recommendations and reports on it were produced from an anonymised
              dataset. They are not financial, legal or compliance advice, and no report here has been filed with anyone.
            </p>
          ),
        },
        {
          heading: "Using the site",
          body: (
            <p>
              Please don&apos;t enter real personal details, card numbers or passwords anywhere on the site, and don&apos;t
              try to break or overload it.
            </p>
          ),
        },
        {
          heading: "Automated decisions",
          body: (
            <p>
              The agent asks for more evidence when it isn&apos;t sure, and anything with a real effect on a customer, such
              as blocking a card, is sent to a person for approval. In a real bank, a qualified analyst should review
              those decisions.
            </p>
          ),
        },
        {
          heading: "No warranty",
          body: (
            <p>
              The site is provided as is. To the extent the law allows, the team isn&apos;t liable for anything that comes
              from using it.
            </p>
          ),
        },
        {
          heading: "Privacy",
          body: (
            <p>
              See the{" "}
              <Link href="/privacy-policy" className="font-medium text-accent hover:underline">
                privacy page
              </Link>{" "}
              for what the site stores.
            </p>
          ),
        },
      ]}
    />
  );
}
