import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "HHGOA Fraud Investigator: agentic graph investigations on TigerGraph";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Simulated social preview card rendered in the neumorphic style.
export default function OpengraphImage() {
  const pill = (text: string) => (
    <div
      style={{
        display: "flex",
        padding: "14px 26px",
        borderRadius: 999,
        background: "#e0e5ec",
        boxShadow: "-6px -6px 12px #ffffff, 6px 6px 12px #a3b1c6",
        fontSize: 28,
        fontWeight: 700,
        color: "#3730a3",
      }}
    >
      {text}
    </div>
  );
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          background: "#e0e5ec",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            padding: 60,
            borderRadius: 48,
            background: "#e0e5ec",
            boxShadow: "-14px -14px 28px #ffffff, 14px 14px 28px #a3b1c6",
          }}
        >
          <div style={{ fontSize: 30, fontWeight: 700, color: "#334155", letterSpacing: 2 }}>HACKER HOUSE GOA</div>
          <div style={{ fontSize: 76, fontWeight: 900, color: "#1e293b", marginTop: 12 }}>HHGOA Fraud Investigator</div>
          <div style={{ fontSize: 34, color: "#1e293b", marginTop: 16 }}>
            GraphRAG over TigerGraph, MCP tools and uncertainty-aware next best actions
          </div>
          <div style={{ display: "flex", gap: 24, marginTop: 40 }}>
            {pill("TigerGraph")}
            {pill("MCP")}
            {pill("LangGraph")}
          </div>
        </div>
      </div>
    ),
    size,
  );
}
