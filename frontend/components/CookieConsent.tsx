"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export const CONSENT_KEY = "hhgoa-cookie-consent";
export type Consent = "accepted" | "essential";

export function readConsent(): Consent | null {
  try {
    const v = window.localStorage.getItem(CONSENT_KEY);
    return v === "accepted" || v === "essential" ? v : null;
  } catch {
    return null;
  }
}

export function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(readConsent() === null);
  }, []);

  function choose(value: Consent) {
    try {
      window.localStorage.setItem(CONSENT_KEY, value);
    } catch {
      /* storage blocked: banner simply closes for this page view */
    }
    window.dispatchEvent(new CustomEvent("hhgoa:consent", { detail: value }));
    setVisible(false);
  }

  if (!visible) return null;
  return (
    <div
      role="region"
      aria-label="Cookie consent"
      className="fixed inset-x-0 bottom-0 z-40 px-4 pb-4 sm:px-6"
    >
      <div className="neu mx-auto flex max-w-4xl flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-ink">
          We store one setting to remember this choice. If you accept, we also count page views in your browser only;
          nothing is sent anywhere. Details in the{" "}
          <Link href="/privacy-policy" className="font-semibold text-accent underline underline-offset-4">
            privacy policy
          </Link>
          .
        </p>
        <div className="flex shrink-0 gap-3">
          <button type="button" className="neu-button focus-ring text-sm" onClick={() => choose("essential")}>
            Essential only
          </button>
          <button type="button" className="neu-button focus-ring text-sm text-accent" onClick={() => choose("accepted")}>
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
