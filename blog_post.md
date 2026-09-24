# Teaching a Fraud Agent When to Ask: Graph Investigations on the HHGOA IEEE-CIS Dataset

*A TigerGraph × Hacker House Goa submission.*

## What we built

Fraud analysts spend most of their time assembling context: the card's history, the device, who else used that device, the billing region, and what the bank decided the last time it saw something similar. Only then can they decide, and often they still need to ask the customer. We built an agent that does that assembly, knows when its evidence is too thin to act on, and recommends next best actions under the bank's written fraud policy, including who has to approve each one.

It runs on the 20-case HHGOA_IEEE benchmark (590,742 transactions, 144,432 identity records, 5,565 closed cases). For each case it produces an answer file in the challenge format: the internal case record, a suspicious activity report when the policy requires one, and the next best actions before and after additional evidence.

## Architecture

**The graph.** We followed the README's suggested schema and extended it. Customers own cards, cards make transactions, and transactions link to a device profile (DeviceInfo, OS, browser and screen), a purchaser email domain and a billing region. Closed cases link to the transactions and cards they involved, and our own investigation cases link to the transactions they flag, the cards they connect and the closed cases they cite. Card IDs are not a column in the data. We reconstructed them from the customer ID and the card-type order, and the reconstruction matches all 1,933 cards named in the closed cases.

**The queries.** The agent investigates through a small set of named, typed graph queries rather than free-form query text:

- `card_window`: the card's timeline around the alert, for testing sequences and bursts.
- `card_history`: the card's baseline of amounts, channels, device profiles and regions.
- `region_history`: how often the card has used a billing region.
- `device_neighbors`: every other card that used the same device profile, with proxy flags.
- `similar_closed_cases`: case memory retrieval by card, pattern and shared device.

The GSQL versions are in `tigergraph/hhgoa_ieee/`. They're exposed to the agent as MCP tools, so the model never writes query text itself.

**The loop.** A LangGraph workflow runs trigger → investigate → assess → initial next best action → gather more evidence → final next best action → write case memory. Each step appends to the case record, so the answer file shows the full progression.

**Memory.** The closed cases play two roles. They're retrieved per alert and cited in `similar_prior_cases`. They also train a LightGBM classifier on July to October only, using Vesta's unnamed V, C, D and M features. The agent uses its score as one signal and says so in the evidence, rather than pretending to know what V127 means.

## Handling uncertainty

The README warns that the bank's risk score is often wrong in both directions and that half the cases are legitimate. So the risk score never decides anything on its own. The agent's fraud probability starts from the closed-case classifier, then moves with graph evidence:

- **Toward fraud:** a device profile new to the card, an amount far above the card's baseline, card-present use in a region the card has never used, or a documented or undocumented pattern match.
- **Toward legitimate:** a region the card uses regularly, or a charge that repeats the cardholder's own history.

The policy then decides what that probability allows:

- **R1.** A probability built on one weak signal leads to `VERIFY_WITH_CUSTOMER` or `STEP_UP_AUTH`, never a block.
- **3a.** A case is opened whenever evidence is requested or a customer disputes a charge.
- **Stopping rule (6).** When the probability is at or beyond 0.85 or 0.15 on two independent pieces of evidence, the agent stops and acts without asking.
- **Simulated responses.** Customer replies aren't provided, so the agent records its assumption in `evidence_requests`. That assumption follows the evidence: a denial when the anomalies and memory point to fraud, a confirmation when the activity matches the card's own history, and no reply when the evidence is balanced.
- **R4 and R8.** "No reply" matters. The agent then monitors, declines pending authorizations, and escalates when the exposure exceeds $500, marking the verdict `uncertain` instead of guessing.

Every action carries its approval route: `auto`, `L1` for declines and blocks up to $2,500, and `L2` for larger blocks and every report. A case and a report are kept distinct. A report is filed only when fraud is confirmed and either the exposure exceeds $1,000, a shared device links other cards, or the pattern is undocumented.

## Finding what the documentation doesn't name

Reading the closed-case notes surfaced two patterns the five documented typologies don't cover:

- **Just-under-$500 bursts.** Three or four online purchases within an hour, each priced just below a $500 authorization threshold, from devices new to the account (for example CC-3748 and CC-3907). Case HHG-006 matches this exactly: four purchases in thirty minutes totalling $1,906.07.
- **A shared device ring.** One Samsung SM-G935F profile behind an anonymous proxy, used on more than twenty unrelated cardholders' cards in a month (CC-2649 and its siblings). Case HHG-014 is on the same profile.

The agent labels both `undocumented`, describes them in its own words, and applies R9: open a case, file a report, and escalate to an analyst. For the ring it also applies R6: monitor every connected card.

## What we learned

- **Schema work is investigation work.** Rebuilding card IDs and device profiles correctly mattered more than any model, because every connection the agent draws depends on them.
- **The closed cases are the real ground truth.** Using them both as retrievable memory and as training labels, bounded to the months before the benchmark, gave the agent calibrated probabilities without touching the public Kaggle labels.
- **Uncertainty is a first-class outcome.** Writing "no reply, escalate" is a better answer than inventing a denial.

## What we would improve with more time

- Run end to end on TigerGraph Savanna. The schema and queries are written, but our build machine had no instance available during the hackathon, so the agent ran on a local mirror of the same graph and reports `written_to_graph: false` honestly.
- Load the policy, the pattern descriptions, the closed-case narratives and the FinCEN guidance into TigerGraph vector search, and let an LLM write summaries and SAR narratives grounded in the retrieved text.
- Monitor November and December on its own, picking up alerts beyond the 20 cases.
