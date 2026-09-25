Built for #HackerHouseGoa with @TigerGraphDB: an agent that investigates card fraud alerts and knows when to ask before it acts.

It pulls evidence from TigerGraph through the official TigerGraph MCP server, retrieves the fraud policy and past cases with vector search in the same graph, and recommends next best actions with the approval each one needs, before and after asking the customer. Every case is written back to the graph as memory for the next one.

Along the way it found two fraud patterns the documentation doesn't name: bursts of purchases priced just under $500, and one proxied phone used across 28 cardholders' cards.

Blog + demo: <link>
