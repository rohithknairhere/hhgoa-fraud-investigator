import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Terms and conditions",
  description: "Terms governing use of the HHGOA Fraud Investigator demonstration.",
  alternates: { canonical: "/terms-and-conditions" },
};

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms and conditions"
      updated="24 September 2026"
      sections={[
        {
          heading: "Demonstration only",
          body: (
            <p>
              This application is a research and hackathon prototype. Its recommendations, including blocks, allows
              and Suspicious Activity Report narratives, are generated from simulated data. They are not financial,
              legal or compliance advice and are not filed with any authority.
            </p>
          ),
        },
        {
          heading: "Acceptable use",
          body: (
            <p>
              Do not submit real personal data, card numbers or credentials in analyst notes. Do not attempt to
              disrupt the service, bypass rate limits or probe it for vulnerabilities without permission.
            </p>
          ),
        },
        {
          heading: "Automated decisions",
          body: (
            <p>
              The agent logs its uncertainty and requests more evidence when its confidence is below 0.60. In any real
              deployment, a qualified human analyst must review decisions with a material effect on a customer.
            </p>
          ),
        },
        {
          heading: "No warranty",
          body: (
            <p>
              The service is provided &quot;as is&quot;, without warranties of any kind. To the extent permitted by
              law, the authors are not liable for losses arising from its use.
            </p>
          ),
        },
        {
          heading: "Privacy",
          body: (
            <p>
              Our{" "}
              <Link href="/privacy-policy" className="font-semibold text-accent underline underline-offset-4">
                privacy policy
              </Link>{" "}
              explains how we handle data.
            </p>
          ),
        },
      ]}
    />
  );
}
