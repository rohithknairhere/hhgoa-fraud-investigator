# Building a fraud investigation agent for Hacker House Goa

For the TigerGraph Hacker House Goa challenge we built an agent that works fraud alerts the way an analyst would. It looks up the card's history, checks the device and the billing region, finds other cards that touched the same device, and reads what the bank decided on similar cases in the past. Then it decides whether it knows enough to act. If it doesn't, it asks the customer first.

This post covers what we built, how it fits together, how we used the graph, and what we'd do differently with more time.

## The dataset

The HHGOA_IEEE dataset is the IEEE-CIS fraud data with the fraud flag removed. It has 590,742 card transactions from July to December 2016, 144,432 identity records for online purchases, and 5,565 closed investigations from July to October. The benchmark is 20 alerts from November and December. Some came from the bank's risk model, some from customers saying "I never made this purchase", and one from an analyst.

The README makes two points that shaped everything we did. The risk score is often wrong in both directions, and about half the benchmark cases are legitimate. An agent that blocks everything would do badly, so the interesting part is deciding when not to act.

## How the data became a graph

We started from the schema the README suggests. Customers own cards and cards make transactions. Each transaction links to a device profile, a purchaser email domain and a billing region. A device profile is the combination of device info, operating system, browser and screen size. Closed cases link to the transactions and cards they involved. We added a vertex for our own investigation cases, which links to the transactions it flags, the cards it connects and the closed cases it cites.

One thing tripped us up early. The case pack refers to cards like C12382-K1, but there's no card ID column in the transactions file. After some digging we found the rule: the customer ID plus a number based on the card type, in alphabetical order. That reconstruction matched all 1,933 cards named in the closed cases, which gave us confidence that every connection the agent draws later is real.

The agent talks to the graph through five named queries instead of writing its own:

- card_window returns the card's transactions around the alert
- card_history gives the card's normal amounts, channels, devices and regions
- region_history counts how often the card has been used in a billing region
- device_neighbors finds every other card that used the same device profile, with proxy flags
- similar_closed_cases pulls past cases on the same card, with the same pattern, or sharing a device

The GSQL for all of these is in tigergraph/hhgoa_ieee in the repo. We expose them as MCP tools so a model can call them but can't send arbitrary queries.

## The investigation loop

Each case runs through a LangGraph workflow with a fixed order: trigger, investigate, assess, first recommendation, gather more evidence, final recommendation, and write the case to memory. Each step adds to the case record, so the answer file shows how the case moved along instead of just the ending.

The closed cases do two jobs. First, they're memory. For every alert the agent retrieves similar past cases and cites them. Second, they're labels. We trained a LightGBM classifier on July to October only, using the unnamed Vesta columns (the V, C, D and M features). On October data it separated fraud from legitimate activity better than the bank's own score, with an AUC of 0.905 against 0.866. The agent treats that score as one signal among several, and the evidence says plainly that it comes from unnamed features.

## Handling uncertainty

The agent's fraud probability starts from that classifier and then moves with what the graph shows. A device the card has never used, an amount far above its normal range, or an in-person purchase in a region it has never visited pushes the number up. A region the card uses regularly, or a charge that repeats the customer's own history, pulls it down.

The bank's fraud policy decides what the agent is allowed to do with that number. A few rules mattered most:

- If the case rests on one weak signal, the agent has to verify with the customer before blocking anything (R1).
- A case gets opened whenever the agent asks for evidence or a customer disputes a charge.
- If the probability is above 0.85 or below 0.15 with at least two independent pieces of evidence, it stops and acts without asking anyone.
- If the customer doesn't reply within 24 hours, it monitors the card, declines pending authorizations, and escalates when more than $500 is at stake (R4 and R8).

Customer replies aren't in the dataset, so the agent has to assume one and write that assumption down. It assumes a denial when the anomalies and past cases point to fraud, and a confirmation when the activity matches the card's own history. When the evidence is balanced, it assumes no reply. That last choice leads to an honest "uncertain" verdict instead of a guess.

Every recommended action carries its approval route. The agent can act alone on low-impact steps. A team lead approves declines and blocks up to $2,500. A fraud manager approves bigger blocks and every regulatory report. A report is only filed when fraud is confirmed and either more than $1,000 is involved, a shared device links other cards, or the pattern isn't one of the documented ones.

A good example is HHG-019. It's an online purchase from a new device, and the evidence leans toward fraud at 0.73. That isn't enough to block under R1, so the first recommendation is to open a case, verify with the customer and monitor the card. Once the assumed denial comes back, the probability rises to 0.95 and the recommendation becomes a card block, the case, and a report, because the same device profile shows up on two other cards with likely fraud.

## Two patterns the documentation doesn't cover

The README lists five known fraud patterns and says there are others. Reading through the analyst notes on the closed cases turned up two.

The first is a burst of three or four online purchases within an hour, each priced just under $500, from devices new to the account. It looks like someone deliberately staying under an authorization limit. Case HHG-006 fits exactly: four purchases in thirty minutes, $1,906.07 in total, and the agent finds closed cases CC-3748, CC-3841 and CC-3907 describing the same thing.

The second is a single Samsung SM-G935F profile behind an anonymous proxy that made purchases on more than twenty unrelated customers' cards in the same month. Case HHG-014 came from an analyst asking about that same device.

The agent labels both as undocumented, describes them in its own words, files a report and escalates to an analyst. For the device ring it also puts every connected card under monitoring.

## What we learned

The schema work mattered more than the model. Getting card IDs and device profiles right was what made the connections trustworthy, and a wrong join there would have quietly broken everything built on top.

The closed cases are the only place the truth is written down, and they're useful in more than one way. Retrieving them helps explain a decision, and training on them helps make one.

We also stopped treating "uncertain" as a failure. On a genuinely ambiguous case, saying so and handing it to a person is the right answer.

## What we'd improve with more time

The biggest gap is TigerGraph itself. We wrote the schema and the queries, but we couldn't get an instance running on our build machine in time, so the agent ran on a local copy of the same graph. Every answer file marks the case as not written to the graph rather than pretending it was. Loading everything into Savanna is the first thing we'd do next.

After that, we'd put the fraud policy, the pattern descriptions, the closed case notes and the FinCEN guidance into TigerGraph's vector search. Then a language model could write case summaries and report narratives grounded in that text. Right now those are filled in from templates.

Finally, we'd let the agent watch November and December on its own and pick up alerts beyond the 20 benchmark cases.
