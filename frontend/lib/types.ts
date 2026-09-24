export type PolicyAction =
  | "ALLOW_TRANSACTION"
  | "DECLINE_TRANSACTION"
  | "MONITOR_CARD"
  | "MONITOR_CONNECTED_CARDS"
  | "WARN_CUSTOMER"
  | "VERIFY_WITH_CUSTOMER"
  | "STEP_UP_AUTH"
  | "BLOCK_CARD"
  | "BLOCK_ALL_CARDS"
  | "GENERATE_REPORT"
  | "CREATE_CASE"
  | "FILE_REPORT"
  | "ESCALATE_TO_ANALYST"
  | "CLOSE_NO_FRAUD";

export type Route = "auto" | "L1" | "L2";

export interface RecommendedAction {
  action: PolicyAction;
  route: Route;
  reason: string;
}

export interface Evidence {
  claim: string;
  source: "graph" | "document" | "customer" | "external";
  ref: string;
  entity_ids: string[];
}

export interface CaseRecord {
  status: "open" | "closed_fraud" | "closed_legitimate" | "escalated";
  verdict: "fraud" | "legitimate" | "uncertain";
  fraud_probability: number;
  pattern: string;
  pattern_description: string;
  affected_txn_ids: string[];
  first_suspicious_txn_id: string;
  connected_card_ids: string[];
  connected_device_profiles: string[];
  exposure_usd: number;
  evidence: Evidence[];
  similar_prior_cases: string[];
  summary: string;
  written_to_graph: boolean;
  graph_case_id: string;
}

export interface Answer {
  case_id: string;
  case: CaseRecord;
  evidence_requests: { type: string; asked_after_step: number; assumed_response: string }[];
  next_best_actions: { initial: RecommendedAction[]; final: RecommendedAction[]; what_changed: string };
  sar: {
    file: boolean;
    reason: string;
    narrative: string;
    subjects: string[];
    total_amount_usd: number;
    activity_dates: string[];
  };
  stop_reason: string;
  tool_calls: number;
  tokens: number;
  latency_s: number;
}

export interface CasePackEntry {
  case_id: string;
  opened_at: string;
  trigger_type: "risk_score" | "customer_report" | "analyst_request";
  trigger_text: string;
  flagged_txn_id: string;
  card_id: string;
  customer_id: string;
  risk_score: number | null;
}

export interface CaseView {
  pack: CasePackEntry;
  answer: Answer;
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  role: "focal" | "context" | "neighbour" | "memory";
  flagged: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}
