import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "HHGOA Fraud Desk: fraud cases investigated on TigerGraph";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  const pill = (text: string) => (
    <div
      style={{
        display: "flex",
        padding: "14px 26px",
        borderRadius: 999,
        background: "#eaf1f1",
        boxShadow: "-6px -6px 12px #ffffff, 6px 6px 12px #c3d2d3",
        fontSize: 28,
        fontWeight: 700,
        color: "#00666b",
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
          background: "#eaf1f1",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            padding: 60,
            borderRadius: 48,
            background: "#003339",
            boxShadow: "-14px -14px 28px #ffffff, 14px 14px 28px #c3d2d3",
          }}
        >
          <div style={{ fontSize: 30, fontWeight: 700, color: "#73ffff", letterSpacing: 2 }}>HACKER HOUSE GOA</div>
          <div style={{ fontSize: 76, fontWeight: 900, color: "#ffffff", marginTop: 12 }}>HHGOA Fraud Desk</div>
          <div style={{ fontSize: 34, color: "#f7f7f8", marginTop: 16 }}>Twenty card fraud alerts, investigated on TigerGraph</div>
        </div>
        <div style={{ display: "flex", gap: 24, marginTop: 40 }}>
          {pill("TigerGraph")}
          {pill("MCP")}
          {pill("GraphRAG")}
          {pill("LangGraph")}
        </div>
      </div>
    ),
    size,
  );
}
