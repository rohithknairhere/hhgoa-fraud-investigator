export type ActionCode =
  | "ALLOW_TRANSACTION"
  | "BLOCK_TRANSACTION"
  | "BLOCK_AND_FILE_SAR"
  | "ESCALATE_TO_SENIOR_ANALYST"
  | "MONITOR_ACCOUNT_AND_REQUEST_STEP_UP_AUTH"
  | "HOLD_AND_REQUEST_ANALYST_REVIEW";

export interface CaseSummary {
  case_id: string;
  title: string;
  typology: string;
  alert_rule: string;
  risk_score: number;
  transaction_id: string;
  status: "open" | "investigated" | "executed";
  initial_action?: ActionCode;
  final_action?: ActionCode;
  p_fraud?: number;
  confidence?: number;
  sar_required?: boolean;
}

export interface NextBestAction {
  action: ActionCode;
  label: string;
  terminal: boolean;
  rationale: string;
  key_drivers: string[];
  evidence_request: string | null;
  phase: "initial" | "updated";
  round: number;
  p_fraud: number;
  confidence: number;
  logged_at: string;
}

export interface EvidenceRecord {
  evidence_id: string;
  label: string;
  source: string;
  tool: string | null;
  mcp_call_id?: string;
  summary: string;
  graph_elements: string[];
  category?: string;
  round?: number;
}

export interface Signal {
  name: string;
  direction: "fraud" | "legitimate";
  contribution: number;
  description: string;
  evidence_ids: string[];
  graph_elements: string[];
}

export interface TraceStep {
  step: number;
  node: string;
  title: string;
  started_at: string;
  duration_ms: number;
  summary: string;
  details: Record<string, unknown>;
}

export interface Assessment {
  p_fraud: number;
  confidence: number;
  round: number;
  components: {
    prior_log_odds: number;
    signal_log_odds: number;
    decisiveness: number;
    evidence_coverage: number;
    signal_conflict: number;
  };
  missing_verifications: string[];
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

export interface InvestigationRecord {
  case_id: string;
  title: string;
  typology: string;
  generated_at: string;
  graph_backend: string;
  planner: string;
  alert: { case_id: string; transaction_id: string; rule: string; risk_score: number; source: string };
  investigation_record: {
    transaction_id: string;
    customer_id: string;
    pattern_tags: string[];
    evidence: EvidenceRecord[];
    signals: Signal[];
    assessments: Assessment[];
    nba_log: NextBestAction[];
    trace: TraceStep[];
    mcp_tool_calls: { call_id: string; tool: string; ok: boolean; latency_ms: number }[];
    graph_context: Record<string, unknown> & { view: { nodes: GraphNode[]; edges: GraphEdge[] } };
  };
  nba_before_additional_evidence: NextBestAction;
  additional_evidence_requested: boolean;
  additional_evidence: { category: string; source: string; description: string; evidence_id: string }[];
  nba_after_additional_evidence: NextBestAction;
  final_decision: {
    action: ActionCode;
    label: string;
    p_fraud: number;
    confidence: number;
    rationale: string;
    justification: Signal[];
    evidence_cited: EvidenceRecord[];
    sar_required: boolean;
  };
  sar: { required: boolean; narrative: string | null; suspicious_amount?: number; filing_type?: string };
  benchmark: { expected_final_action: string; passed: boolean };
}

export interface ExecutionReceipt {
  execution_id: string;
  case_id: string;
  action: ActionCode;
  label: string;
  executed_at: string;
  status: string;
  sar_submitted: boolean;
  idempotent_replay?: boolean;
}
