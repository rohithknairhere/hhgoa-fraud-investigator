import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: "How the HHGOA Fraud Investigator demo handles data, cookies and analytics.",
  alternates: { canonical: "/privacy-policy" },
};

export default function PrivacyPolicyPage() {
  return (
    <LegalPage
      title="Privacy policy"
      updated="24 September 2026"
      sections={[
        {
          heading: "Who we are",
          body: (
            <p>
              HHGOA Fraud Investigator is a hackathon demonstration built for the Hacker House Goa challenge. It
              investigates simulated alerts over a TigerGraph fraud graph.
            </p>
          ),
        },
        {
          heading: "Data we process",
          body: (
            <>
              <p>
                All transactions, cards, devices, IP addresses and customers shown in this application are synthetic.
                They follow the column layout of the public IEEE-CIS fraud detection dataset but contain no real
                cardholder or personal data.
              </p>
              <p>
                If you submit an analyst note, we store the name you enter, your chosen disposition and the note text
                in the memory of the demo backend. Notes are discarded when the backend restarts.
              </p>
            </>
          ),
        },
        {
          heading: "Cookies and local storage",
          body: (
            <p>
              We store a single essential entry in your browser&apos;s local storage to remember your cookie choice. We
              set no advertising or cross-site tracking cookies.
            </p>
          ),
        },
        {
          heading: "Analytics",
          body: (
            <p>
              The analytics script is a mock. If you select &quot;Accept&quot;, anonymous page-view and button events
              are queued in your browser&apos;s memory only. Nothing is transmitted to us or any third party. If you
              select &quot;Essential only&quot;, no events are recorded.
            </p>
          ),
        },
        {
          heading: "Security",
          body: (
            <p>
              We serve all traffic over HTTPS with HSTS. Our API rejects plaintext HTTP and rate-limits every client.
              Server credentials never reach your browser.
            </p>
          ),
        },
        {
          heading: "Your rights and contact",
          body: (
            <p>
              You can clear your stored choice at any time by clearing this site&apos;s data in your browser. For
              questions, contact the project team through the Hacker House Goa submission page. See also our{" "}
              <Link href="/terms-and-conditions" className="font-semibold text-accent underline underline-offset-4">
                terms and conditions
              </Link>
              .
            </p>
          ),
        },
      ]}
    />
  );
}
