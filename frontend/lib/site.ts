export const SITE = {
  name: "HHGOA Fraud Investigator",
  shortName: "HHGOA",
  description:
    "Agentic fraud investigation on TigerGraph: GraphRAG evidence via MCP, calibrated uncertainty, and logged next-best actions for the Hacker House Goa challenge.",
  url: (process.env.NEXT_PUBLIC_SITE_URL || "https://localhost:3000").replace(/\/$/, ""),
};
