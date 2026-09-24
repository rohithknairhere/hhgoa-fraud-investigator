import Script from "next/script";

/**
 * Mock analytics injection. Queues page views in-memory on `window.hhgoaAnalytics` and only
 * records once the visitor has accepted cookies. Nothing leaves the browser.
 */
export function Analytics() {
  const id = process.env.NEXT_PUBLIC_ANALYTICS_ID || "hhgoa-demo";
  const snippet = `
(function (w) {
  var q = (w.hhgoaAnalytics = w.hhgoaAnalytics || { id: ${JSON.stringify(id)}, events: [] });
  function consented() {
    try { return w.localStorage.getItem("hhgoa-cookie-consent") === "accepted"; } catch (e) { return false; }
  }
  q.track = function (name, props) {
    if (!consented()) return;
    q.events.push({ name: name, props: props || {}, path: w.location.pathname, ts: Date.now() });
  };
  q.track("page_view");
  w.addEventListener("hhgoa:consent", function (e) { if (e.detail === "accepted") q.track("page_view"); });
})(window);`;
  return (
    <Script id="mock-analytics" strategy="afterInteractive">
      {snippet}
    </Script>
  );
}
