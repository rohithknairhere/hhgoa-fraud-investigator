export const SITE = {
  name: "HHGOA Fraud Desk",
  shortName: "HHGOA",
  description:
    "Twenty card fraud alerts investigated on TigerGraph: the evidence, the decision before and after asking the customer, who has to approve each action, and the report when one is needed.",
  url: (process.env.NEXT_PUBLIC_SITE_URL || "https://localhost:3000").replace(/\/$/, ""),
};
