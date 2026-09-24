"""Deterministic HHGOA benchmark dataset.

The 20 benchmark cases are simulated on top of the IEEE-CIS fraud schema
(TransactionID / TransactionDT / TransactionAmt / ProductCD / card1-6 / addr1 /
P_emaildomain / DeviceType / DeviceInfo / isFraud). Each scenario builds a real
sub-graph — the agent never sees scenario labels, only what the graph tools
return — plus a script of what a customer / analyst would answer if the agent
asks for more evidence.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from app.graph.store import GraphStore

DAY = 86_400
HOUR = 3_600
UNLABELED = -1


# ---------------------------------------------------------------------------
# Scenario model
# ---------------------------------------------------------------------------
@dataclass
class Scenario:
    case_id: str
    title: str
    typology: str
    alert_rule: str
    risk_score: float
    builder: Callable[["Builder"], str]
    expected_initial_terminal: bool
    expected_final_action: str
    # request type ("step_up_auth" | "analyst_review") -> evidence items returned
    followups: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    focal_txn_id: str = ""


def ev(category: str, source: str, signal: str, weight: float, description: str) -> dict[str, Any]:
    return {
        "category": category,
        "source": source,
        "signal": signal,
        "weight": weight,
        "strength": 1.0,
        "description": description,
    }


STEP_UP_PASSED = ev(
    "identity_verification", "step_up_auth", "step_up_passed", -2.5,
    "Cardholder completed app-based step-up authentication (biometric) and confirmed the purchase.",
)
STEP_UP_FAILED = ev(
    "identity_verification", "step_up_auth", "step_up_failed", 2.5,
    "Step-up challenge failed; the registered cardholder was reached by phone and denied making the purchase.",
)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------
class Builder:
    def __init__(self, store: GraphStore, rng: random.Random, base_ts: int, shared: dict[str, str]):
        self.store = store
        self.rng = rng
        self.base_ts = base_ts
        self.shared = shared
        self._counters = shared.setdefault("__counters__", {})  # type: ignore[arg-type]

    def _next(self, prefix: str, start: int) -> str:
        n = self._counters.get(prefix, start) + 1
        self._counters[prefix] = n
        return f"{prefix}{n}"

    def customer(self, tenure_days: int, addr1: int | None = None, email: str = "gmail.com",
                 kyc: str = "standard", segment: str = "retail") -> str:
        vid = self._next("CUST-", 30000)
        return self.store.add_vertex(
            "Customer", vid,
            tenure_days=tenure_days,
            addr1=addr1 if addr1 is not None else self.rng.randint(100, 540),
            p_emaildomain=email, kyc_level=kyc, segment=segment,
        )

    def card(self, customer: str, brand: str = "visa", ctype: str = "debit", country: str = "US") -> str:
        vid = self._next("CARD-", 10000)
        self.store.add_vertex(
            "Card", vid, card1=self.rng.randint(1000, 18396), card4=brand, card6=ctype,
            issuer_country=country,
        )
        self.store.add_edge("HOLDS", customer, vid)
        return vid

    def device(self, dtype: str = "desktop", info: str = "Windows") -> str:
        vid = self._next("DEV-", 20000)
        return self.store.add_vertex("Device", vid, device_type=dtype, device_info=info)

    def ip(self, country: str = "US", proxy: bool = False, asn: str = "AS7922") -> str:
        vid = self._next("IP-", 40000)
        return self.store.add_vertex("IP", vid, country=country, is_proxy=proxy, asn=asn)

    def txn(self, card: str, device: str, ip: str, customer: str, amount: float, ts: int,
            product: str = "W", is_fraud: int = UNLABELED, chargeback: bool = False) -> str:
        vid = self._next("T", 3_100_000)
        self.store.add_vertex(
            "Transaction", vid, amount=round(amount, 2), ts=ts, product_cd=product,
            is_fraud=is_fraud, chargeback=chargeback,
        )
        self.store.add_edge("PAID_WITH", vid, card)
        self.store.add_edge("USED_DEVICE", vid, device)
        self.store.add_edge("FROM_IP", vid, ip)
        self.store.add_edge("PLACED_BY", vid, customer)
        self.store.add_edge("USES_DEVICE", customer, device)
        self.store.add_edge("USES_IP", customer, ip)
        return vid

    def history(self, customer: str, card: str, device: str, ip: str, n: int, avg: float,
                span_days: int = 180, gap_days: int = 2, chargebacks: int = 0) -> list[str]:
        """Legitimate (labelled) baseline activity ending `gap_days` before the alert."""
        out = []
        for i in range(n):
            ts = self.base_ts - gap_days * DAY - int((i + 1) * span_days * DAY / (n + 1))
            amt = max(3.0, self.rng.gauss(avg, avg * 0.25))
            cb = i < chargebacks
            out.append(self.txn(card, device, ip, customer, amt, ts, is_fraud=0, chargeback=cb))
        return out

    def case(self, case_id: str, txns: list[str], customer: str, tags: list[str], outcome: str,
             status: str = "closed", summary: str = "", decision: str = "") -> str:
        self.store.add_vertex(
            "Case", case_id, status=status, pattern_tags=tags, outcome=outcome,
            summary=summary, decision=decision, opened_ts=self.base_ts, sar_filed=False,
        )
        for t in txns:
            self.store.add_edge("INVESTIGATES", case_id, t)
        self.store.add_edge("CONCERNS", case_id, customer)
        return case_id


def established(b: Builder, tenure: int = 1200, n: int = 40, avg: float = 85.0, country: str = "US",
                chargebacks: int = 0, dtype: str = "mobile", info: str = "iOS 17") -> dict[str, str]:
    cust = b.customer(tenure)
    card = b.card(cust)
    dev = b.device(dtype, info)
    ip = b.ip(country)
    b.history(cust, card, dev, ip, n, avg, chargebacks=chargebacks)
    return {"cust": cust, "card": card, "dev": dev, "ip": ip}


# ---------------------------------------------------------------------------
# Scenario builders (each returns the focal TransactionID)
# ---------------------------------------------------------------------------
def s01_device_ring(b: Builder) -> str:
    ring_dev = b.device("mobile", "SM-G960U")
    ring_ip = b.ip("RO", proxy=True, asn="AS9009")
    b.shared["ring_device"], b.shared["ring_ip"] = ring_dev, ring_ip
    prior = []
    for i in range(6):
        c = b.customer(b.rng.randint(8, 40), email="protonmail.com", kyc="basic")
        card = b.card(c, "mastercard", "credit")
        fraud = 1 if i < 3 else UNLABELED
        prior.append(b.txn(card, ring_dev, ring_ip, c, b.rng.uniform(600, 1500),
                           int(b.base_ts - (3 - i * 0.4) * DAY), is_fraud=fraud, chargeback=fraud == 1))
    b.case("CASE-H900", prior[:3], b.store.neighbors(prior[0], "Customer")[0],
           ["device_sharing", "new_customer"], "confirmed_fraud",
           summary="Card-not-present ring cycling stolen cards through one Android handset.",
           decision="BLOCK_AND_FILE_SAR")
    cust = b.customer(5, email="protonmail.com", kyc="basic")
    card = b.card(cust, "mastercard", "credit")
    return b.txn(card, ring_dev, ring_ip, cust, 1850.0, b.base_ts)


def s02_card_testing(b: Builder) -> str:
    v = established(b, tenure=400, n=30, avg=60)
    dev = b.device("desktop", "Linux x86_64")
    ip = b.ip("US", proxy=True, asn="AS14061")
    for i in range(14):
        b.txn(v["card"], dev, ip, v["cust"], b.rng.uniform(1, 5), b.base_ts - 360 + i * 25, product="C")
    return b.txn(v["card"], dev, ip, v["cust"], 480.0, b.base_ts)


def s03_account_takeover(b: Builder) -> str:
    v = established(b, tenure=1200, n=40, avg=85)
    dev = b.device("mobile", "iOS 16")
    ip = b.ip("NG", proxy=True, asn="AS37148")
    return b.txn(v["card"], dev, ip, v["cust"], 2400.0, b.base_ts)


def s04_travel(b: Builder) -> str:
    v = established(b, tenure=1500, n=50, avg=140)
    ip = b.ip("PT", proxy=False, asn="AS3243")
    return b.txn(v["card"], v["dev"], ip, v["cust"], 210.0, b.base_ts)


def s05_household(b: Builder) -> str:
    addr = 204
    dev = b.device("desktop", "MacOS")
    ip = b.ip("US")
    a = b.customer(2100, addr1=addr)
    bb = b.customer(1900, addr1=addr)
    ca, cb1, cb2 = b.card(a), b.card(bb), b.card(bb, "amex", "credit")
    b.history(a, ca, dev, ip, 25, 70)
    b.history(bb, cb1, dev, ip, 25, 90)
    return b.txn(cb2, dev, ip, bb, 160.0, b.base_ts)


def s06_structuring(b: Builder) -> str:
    cust = b.customer(45, email="yahoo.com")
    card = b.card(cust, "visa", "debit")
    dev = b.device("desktop", "Windows")
    ip = b.ip("US")
    b.history(cust, card, dev, ip, 6, 120, span_days=40)
    for i in range(6):
        b.txn(card, dev, ip, cust, b.rng.uniform(9200, 9900), int(b.base_ts - (20 - i * 3) * HOUR), product="P2P")
    return b.txn(card, dev, ip, cust, 9650.0, b.base_ts, product="P2P")


def s07_synthetic_identity(b: Builder) -> str:
    addr = 299
    dev = b.device("desktop", "Windows")
    ip = b.ip("US", asn="AS20115")
    for i in range(3):
        c = b.customer(b.rng.randint(12, 40), addr1=addr, email="outlook.com", kyc="basic")
        b.txn(b.card(c, "visa", "credit"), dev, ip if i < 2 else b.ip("US", asn="AS7922"), c, b.rng.uniform(300, 900),
              b.base_ts - b.rng.randint(2, 10) * DAY)
    cust = b.customer(20, addr1=addr, email="outlook.com", kyc="basic")
    return b.txn(b.card(cust, "visa", "credit"), dev, ip, cust, 1400.0, b.base_ts)


def s08_false_positive(b: Builder) -> str:
    v = established(b, tenure=2400, n=60, avg=110)
    return b.txn(v["card"], v["dev"], v["ip"], v["cust"], 230.0, b.base_ts)


def s09_friendly_fraud(b: Builder) -> str:
    v = established(b, tenure=700, n=30, avg=120, chargebacks=3)
    return b.txn(v["card"], v["dev"], v["ip"], v["cust"], 380.0, b.base_ts)


def s10_bulk_business(b: Builder) -> str:
    v = established(b, tenure=1500, n=40, avg=180, dtype="desktop", info="Windows")
    b.store.vertices[v["cust"]]["segment"] = "small_business"
    for i in range(8):
        b.txn(v["card"], v["dev"], v["ip"], v["cust"], 25.0, b.base_ts - 1200 + i * 140, product="H")
    return b.txn(v["card"], v["dev"], v["ip"], v["cust"], 25.0, b.base_ts, product="H")


def s11_ip_cluster(b: Builder) -> str:
    ip = b.ip("VN", proxy=True, asn="AS45899")
    prior = []
    for i in range(8):
        c = b.customer(b.rng.randint(1, 30), email="anonymous.com", kyc="basic")
        d = b.device("mobile", f"Redmi Note {i}")
        prior.append(b.txn(b.card(c, "visa", "credit"), d, ip, c, b.rng.uniform(200, 700),
                           b.base_ts - b.rng.randint(300, 3300), is_fraud=1 if i < 4 else UNLABELED,
                           chargeback=i < 4))
    b.case("CASE-H901", prior[:2], b.store.neighbors(prior[0], "Customer")[0],
           ["ip_cluster", "new_customer"], "confirmed_fraud",
           summary="Money-mule cluster funnelling stolen cards through a residential proxy.",
           decision="BLOCK_AND_FILE_SAR")
    cust = b.customer(3, email="anonymous.com", kyc="basic")
    return b.txn(b.card(cust, "visa", "credit"), b.device("mobile", "Redmi Note 9"), ip, cust, 640.0, b.base_ts)


def s12_new_customer(b: Builder) -> str:
    cust = b.customer(2, email="icloud.com")
    return b.txn(b.card(cust), b.device("mobile", "iOS 17"), b.ip("US"), cust, 890.0, b.base_ts)


def s13_impossible_travel(b: Builder) -> str:
    v = established(b, tenure=800, n=35, avg=95)
    b.txn(v["card"], v["dev"], v["ip"], v["cust"], 60.0, b.base_ts - 40 * 60)
    return b.txn(v["card"], b.device("desktop", "Windows"), b.ip("BR", asn="AS28573"), v["cust"],
                 1250.0, b.base_ts)


def s14_emulator(b: Builder) -> str:
    dev = b.device("mobile", "Android Emulator x86")
    ip = b.ip("US", proxy=True, asn="AS16509")
    for _ in range(4):
        c = b.customer(b.rng.randint(1, 10), email="mail.ru", kyc="basic")
        b.txn(b.card(c, "mastercard", "credit"), dev, ip, c, b.rng.uniform(150, 400),
              b.base_ts - b.rng.randint(600, 7000))
    cust = b.customer(1, email="mail.ru", kyc="basic")
    return b.txn(b.card(cust, "mastercard", "credit"), dev, ip, cust, 520.0, b.base_ts)


def s15_sim_swap(b: Builder) -> str:
    v = established(b, tenure=1500, n=45, avg=100)
    return b.txn(v["card"], b.device("mobile", "SM-A515F"), b.ip("US", asn="AS21928"), v["cust"],
                 500.0, b.base_ts)


def s16_corporate_vpn(b: Builder) -> str:
    v = established(b, tenure=1800, n=40, avg=75, dtype="desktop", info="Windows")
    return b.txn(v["card"], v["dev"], b.ip("US", proxy=True, asn="AS13335"), v["cust"], 95.0, b.base_ts)


def s17_ring_member(b: Builder) -> str:
    cust = b.customer(4, email="protonmail.com", kyc="basic")
    return b.txn(b.card(cust, "mastercard", "credit"), b.shared["ring_device"], b.shared["ring_ip"],
                 cust, 1320.0, b.base_ts)


def s18_refund_abuse(b: Builder) -> str:
    v = established(b, tenure=300, n=25, avg=150, chargebacks=2)
    return b.txn(v["card"], v["dev"], v["ip"], v["cust"], 520.0, b.base_ts)


def s19_dormant(b: Builder) -> str:
    cust = b.customer(900)
    card = b.card(cust)
    dev = b.device("desktop", "Windows")
    ip = b.ip("US")
    b.history(cust, card, dev, ip, 20, 70, span_days=300, gap_days=320)
    return b.txn(card, b.device("mobile", "SM-S911B"), b.ip("US", asn="AS7018"), cust, 300.0, b.base_ts)


def s20_vip(b: Builder) -> str:
    v = established(b, tenure=3000, n=80, avg=400)
    return b.txn(v["card"], v["dev"], v["ip"], v["cust"], 3200.0, b.base_ts)


SCENARIOS: list[Scenario] = [
    Scenario("HHGOA-001", "Shared Android handset cycling new credit cards", "device_ring",
             "DEVICE_MULTI_CARD", 0.82, s01_device_ring, True, "BLOCK_AND_FILE_SAR"),
    Scenario("HHGOA-002", "Micro-charge card testing followed by a $480 purchase", "card_testing",
             "VELOCITY_SMALL_TICKET", 0.88, s02_card_testing, True, "BLOCK_TRANSACTION"),
    Scenario("HHGOA-003", "Long-tenured customer on new device via Nigerian proxy", "account_takeover",
             "ATO_NEW_DEVICE_PROXY", 0.64, s03_account_takeover, False, "BLOCK_TRANSACTION",
             {"step_up_auth": [STEP_UP_FAILED]}),
    Scenario("HHGOA-004", "Card-present-like purchase from a new country (Portugal)", "benign_travel",
             "GEO_NEW_COUNTRY", 0.58, s04_travel, False, "ALLOW_TRANSACTION",
             {"step_up_auth": [STEP_UP_PASSED]}),
    Scenario("HHGOA-005", "Three cards, two customers, one desktop", "household_sharing",
             "DEVICE_MULTI_CARD", 0.61, s05_household, False, "ALLOW_TRANSACTION",
             {"analyst_review": [ev("relationship_validation", "analyst_review", "household_confirmed", -2.2,
                                    "Analyst verified both customers share a billing address and surname; the device is a family computer.")]}),
    Scenario("HHGOA-006", "Seven P2P transfers just under the $10k reporting threshold", "structuring",
             "AML_NEAR_THRESHOLD", 0.79, s06_structuring, True, "BLOCK_AND_FILE_SAR"),
    Scenario("HHGOA-007", "Thin-file customers sharing address, device and IP", "synthetic_identity",
             "IDENTITY_LINKAGE", 0.42, s07_synthetic_identity, False, "BLOCK_AND_FILE_SAR",
             {"analyst_review": [ev("relationship_validation", "analyst_review", "identity_fabricated", 2.6,
                                    "KYC review: SSNs issued after the stated birth years; ID documents share a template.")]}),
    Scenario("HHGOA-008", "Rule hit on a routine purchase by a long-standing customer", "false_positive",
             "AMOUNT_ABOVE_P90", 0.35, s08_false_positive, True, "ALLOW_TRANSACTION"),
    Scenario("HHGOA-009", "Repeat disputer buys again on a known device", "first_party",
             "PRIOR_CHARGEBACKS", 0.55, s09_friendly_fraud, False, "ESCALATE_TO_SENIOR_ANALYST",
             {"analyst_review": [ev("analyst_review", "analyst_review", "dispute_history_mixed", 1.0,
                                    "Two of three prior chargebacks were reversed in the merchant's favour (delivery proven).")],
              "step_up_auth": [ev("identity_verification", "step_up_auth", "step_up_passed_cardholder", -1.0,
                                  "Cardholder passed step-up and confirms placing the order (first-party risk remains).")]}),
    Scenario("HHGOA-010", "Nine $25 gift cards in twenty minutes from a business account", "bulk_purchase",
             "VELOCITY_REPEAT_AMOUNT", 0.66, s10_bulk_business, False, "ALLOW_TRANSACTION",
             {"step_up_auth": [STEP_UP_PASSED]}),
    Scenario("HHGOA-011", "Residential proxy shared by nine cards within an hour", "mule_cluster",
             "IP_MULTI_CARD", 0.80, s11_ip_cluster, True, "BLOCK_AND_FILE_SAR"),
    Scenario("HHGOA-012", "Two-day-old customer, $890 first purchase", "new_customer",
             "NEW_ACCOUNT_HIGH_AMOUNT", 0.60, s12_new_customer, False, "ALLOW_TRANSACTION",
             {"step_up_auth": [STEP_UP_PASSED]}),
    Scenario("HHGOA-013", "Card used in the US and Brazil forty minutes apart", "impossible_travel",
             "GEO_VELOCITY", 0.77, s13_impossible_travel, True, "BLOCK_TRANSACTION"),
    Scenario("HHGOA-014", "Android emulator cycling fresh accounts", "bot_device",
             "EMULATOR_DETECTED", 0.74, s14_emulator, True, "BLOCK_AND_FILE_SAR"),
    Scenario("HHGOA-015", "New handset passes SMS OTP, then a SIM-swap report", "account_takeover",
             "ATO_NEW_DEVICE", 0.66, s15_sim_swap, False, "BLOCK_TRANSACTION",
             {"step_up_auth": [ev("identity_verification", "step_up_auth", "sms_otp_passed", -1.0,
                                  "SMS one-time passcode entered correctly (weak factor: SIM-bound).")],
              "analyst_review": [ev("analyst_review", "telco_check", "sim_swap_detected", 3.0,
                                    "Carrier lookup: SIM swapped 2h before the OTP; OTP delivery was compromised.")]}),
    Scenario("HHGOA-016", "Established customer behind a corporate VPN", "benign_proxy",
             "PROXY_IP", 0.45, s16_corporate_vpn, False, "ALLOW_TRANSACTION",
             {"step_up_auth": [STEP_UP_PASSED]}),
    Scenario("HHGOA-017", "Second new card on the HHGOA-001 ring handset", "device_ring",
             "DEVICE_MULTI_CARD", 0.86, s17_ring_member, True, "BLOCK_AND_FILE_SAR"),
    Scenario("HHGOA-018", "Repeat disputer declines step-up on a large order", "first_party",
             "PRIOR_CHARGEBACKS", 0.60, s18_refund_abuse, False, "BLOCK_TRANSACTION",
             {"step_up_auth": [ev("identity_verification", "step_up_auth", "step_up_declined", 2.0,
                                  "Customer ignored the step-up challenge and opened an issuer dispute the same day.")],
              "analyst_review": [ev("analyst_review", "issuer_feedback", "issuer_chargeback_confirmed", 1.5,
                                    "Issuer confirms a chargeback on this order, the customer's fourth dispute this year.")]}),
    Scenario("HHGOA-019", "Dormant account reactivated on a new phone", "dormant_reactivation",
             "DORMANT_REACTIVATION", 0.68, s19_dormant, False, "BLOCK_TRANSACTION",
             {"step_up_auth": [STEP_UP_FAILED]}),
    Scenario("HHGOA-020", "Long-standing customer makes an 8x purchase", "high_value_legit",
             "AMOUNT_ABOVE_P99", 0.50, s20_vip, False, "ALLOW_TRANSACTION",
             {"step_up_auth": [STEP_UP_PASSED]}),
]


# Closed historical cases for GraphRAG retrieval: (tags, outcome, summary)
HISTORICAL_CASES: list[tuple[list[str], str, str]] = [
    (["device_sharing"], "confirmed_fraud", "Stolen cards tested on a single shared tablet."),
    (["device_sharing", "new_customer"], "confirmed_fraud", "Fresh accounts rotated on one device."),
    (["device_sharing"], "false_positive", "Family members sharing a home PC."),
    (["device_sharing", "synthetic_identity"], "confirmed_fraud", "Synthetic identities built on one laptop."),
    (["ip_cluster"], "confirmed_fraud", "Proxy exit node shared by a mule network."),
    (["ip_cluster", "new_customer"], "confirmed_fraud", "Mule recruits onboarded from the same proxy."),
    (["velocity_burst"], "confirmed_fraud", "BIN attack with sub-$5 authorisations."),
    (["velocity_burst", "account_takeover"], "confirmed_fraud", "Card tested then drained from a new device."),
    (["velocity_burst"], "false_positive", "Office manager bulk-buying gift cards."),
    (["account_takeover"], "confirmed_fraud", "Credential-stuffed account used from a proxy."),
    (["account_takeover", "geo_anomaly"], "confirmed_fraud", "Takeover from overseas after phishing."),
    (["account_takeover"], "false_positive", "Customer bought a new phone before a holiday purchase."),
    (["geo_anomaly"], "false_positive", "Customer travelling in Europe."),
    (["geo_anomaly"], "false_positive", "Customer relocated for work."),
    (["geo_anomaly"], "confirmed_fraud", "Cloned card used abroad."),
    (["impossible_travel", "account_takeover"], "confirmed_fraud", "Card skimmed and used on another continent."),
    (["impossible_travel"], "confirmed_fraud", "Counterfeit card used minutes after a domestic purchase."),
    (["structuring"], "confirmed_fraud", "Repeated sub-threshold P2P transfers (SAR filed)."),
    (["structuring", "new_customer"], "confirmed_fraud", "New account layering funds below CTR limits."),
    (["synthetic_identity"], "confirmed_fraud", "Bust-out after credit-building on fabricated identity."),
    (["synthetic_identity", "new_customer"], "false_positive", "Student housing with unrelated tenants."),
    (["bot_device", "device_sharing"], "confirmed_fraud", "Emulator farm creating accounts."),
    (["bot_device"], "confirmed_fraud", "Scripted checkout from an emulator."),
    (["dormant_reactivation", "account_takeover"], "confirmed_fraud", "Dormant account hijacked after data breach."),
    (["dormant_reactivation"], "false_positive", "Seasonal customer returning."),
    (["first_party"], "confirmed_fraud", "Serial chargebacks on delivered goods."),
    (["first_party"], "false_positive", "Legitimate disputes over defective products."),
    (["first_party", "account_takeover"], "confirmed_fraud", "Customer claimed takeover to dispute purchases."),
    (["first_party"], "false_positive", "Merchant billing errors triggered disputes."),
    (["new_customer"], "false_positive", "New customer's first large electronics order."),
    (["new_customer"], "false_positive", "Welcome-offer purchase by a new customer."),
    (["new_customer"], "false_positive", "Wedding registry order from new account."),
    (["new_customer", "account_takeover"], "confirmed_fraud", "Stolen identity used to open and spend."),
]


@dataclass
class Dataset:
    store: GraphStore
    scenarios: dict[str, Scenario]


def _build_history(store: GraphStore, shared: dict) -> None:
    rng = random.Random(7)
    b = Builder(store, rng, base_ts=9_000_000, shared=shared)
    for i, (tags, outcome, summary) in enumerate(HISTORICAL_CASES, start=1):
        cust = b.customer(rng.randint(5, 2000))
        card = b.card(cust)
        txn = b.txn(card, b.device(), b.ip(), cust, rng.uniform(50, 3000), b.base_ts - i * DAY,
                    is_fraud=1 if outcome == "confirmed_fraud" else 0,
                    chargeback=outcome == "confirmed_fraud")
        decision = "BLOCK_TRANSACTION" if outcome == "confirmed_fraud" else "ALLOW_TRANSACTION"
        b.case(f"CASE-H{i:03d}", [txn], cust, tags, outcome, summary=summary, decision=decision)


def build_dataset() -> Dataset:
    store = GraphStore()
    shared: dict[str, Any] = {}
    _build_history(store, shared)
    scenarios: dict[str, Scenario] = {}
    for idx, sc in enumerate(SCENARIOS):
        rng = random.Random(1000 + idx)
        b = Builder(store, rng, base_ts=15_000_000 + idx * 1_000_000, shared=shared)
        sc.focal_txn_id = sc.builder(b)
        cust = store.neighbors(sc.focal_txn_id, "Customer")[0]
        store.add_vertex("Case", sc.case_id, status="open", pattern_tags=[], outcome="pending",
                         summary=sc.title, decision="", opened_ts=b.base_ts, sar_filed=False)
        store.add_edge("INVESTIGATES", sc.case_id, sc.focal_txn_id)
        store.add_edge("CONCERNS", sc.case_id, cust)
        scenarios[sc.case_id] = sc
    return Dataset(store=store, scenarios=scenarios)
