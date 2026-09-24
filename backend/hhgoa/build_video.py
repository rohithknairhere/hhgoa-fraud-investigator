"""Render the demo video: HTML slides built from cases/*.json -> Edge headless screenshots ->
Windows TTS narration -> ffmpeg MP4 at <repo>/demo/hhgoa_demo.mp4.

    python -m hhgoa.build_video     (run from backend/)
"""

from __future__ import annotations

import html
import json
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg

from hhgoa.paths import CASES_OUT, REPO

OUT = REPO / "demo"
WORK = OUT / "build"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

CSS = """
body{margin:0;width:1280px;height:720px;background:#e0e5ec;font-family:'Segoe UI',Arial,sans-serif;color:#1e293b;overflow:hidden}
.wrap{padding:44px 60px}
.card{background:#e0e5ec;border-radius:26px;box-shadow:-8px -8px 16px #fff,8px 8px 16px #a3b1c6;padding:24px 28px;margin-bottom:18px}
.inset{background:#e0e5ec;border-radius:16px;box-shadow:inset 4px 4px 8px #a3b1c6,inset -4px -4px 8px #fff;padding:12px 16px}
h1{font-size:46px;margin:0 0 8px;font-weight:900}
h2{font-size:34px;margin:0 0 14px;font-weight:800}
.eyebrow{font-size:15px;letter-spacing:2px;text-transform:uppercase;color:#334155;font-weight:700;margin-bottom:6px}
p,li{font-size:21px;line-height:1.45}
.grid{display:grid;gap:18px}
.two{grid-template-columns:1fr 1fr}
.three{grid-template-columns:1fr 1fr 1fr}
.tag{display:inline-block;border-radius:999px;padding:4px 12px;font-weight:700;font-size:15px;margin:2px;box-shadow:inset 2px 2px 4px #a3b1c6,inset -2px -2px 4px #fff}
.fraud{color:#9f1239}.legit{color:#166534}.unc{color:#854d0e}.acc{color:#3730a3}
table{border-collapse:separate;border-spacing:0 4px;width:100%;font-size:12.5px}
td,th{padding:6px 6px;text-align:left}
th{color:#334155;text-transform:uppercase;font-size:12px;letter-spacing:1px}
tr.row td{background:#e0e5ec;box-shadow:0 2px 4px #b8c2d3}
.mono{font-family:Consolas,monospace}
.small{font-size:16px}
"""


def page(body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='wrap'>{body}</div></body></html>"


def esc(x) -> str:
    return html.escape(str(x))


def vclass(v: str) -> str:
    return {"fraud": "fraud", "legitimate": "legit"}.get(v, "unc")


def actions(lst) -> str:
    return " ".join(f"<span class='tag acc'>{esc(a['action'])} <span style='color:#334155'>({esc(a['route'])})</span></span>" for a in lst)


def case_slide(a: dict, title: str) -> str:
    c = a["case"]
    ev = "".join(f"<li class='small'>{esc(e['claim'] if len(e['claim']) < 160 else e['claim'][:157] + '...')} <span class='mono' style='color:#334155'>[{esc(e['source'])}]</span></li>" for e in c["evidence"][:4])
    req = a["evidence_requests"][0]["assumed_response"] if a["evidence_requests"] else "none needed"
    return page(f"""
<div class='eyebrow'>{esc(a['case_id'])} · {esc(title)}</div>
<h2 style='font-size:28px'>{esc(c['summary'].split('. ')[0])}.</h2>
<div class='grid two'>
 <div class='card'><div class='eyebrow'>Evidence from the graph</div><ul style='margin:0;padding-left:20px'>{ev}</ul></div>
 <div>
  <div class='card'><div class='eyebrow'>Verdict</div><p style='margin:0'><b class='{vclass(c['verdict'])}'>{esc(c['verdict'])}</b>, pattern <b>{esc(c['pattern'])}</b>, p(fraud) <b>{c['fraud_probability']:.2f}</b>, exposure <b>${c['exposure_usd']:,.2f}</b>, SAR <b>{'yes' if a['sar']['file'] else 'no'}</b></p></div>
  <div class='card'><div class='eyebrow'>NBA before evidence</div>{actions(a['next_best_actions']['initial'])}
   <div class='eyebrow' style='margin-top:10px'>Assumed response</div><p class='small' style='margin:0'>{esc(req[:160])}</p>
   <div class='eyebrow' style='margin-top:10px'>NBA after evidence</div>{actions(a['next_best_actions']['final'])}</div>
 </div>
</div>""")


def build_slides(cases: dict[str, dict]) -> list[tuple[str, str]]:
    fraud = [a for a in cases.values() if a["case"]["verdict"] == "fraud"]
    legit = [a for a in cases.values() if a["case"]["verdict"] == "legitimate"]
    unc = [a for a in cases.values() if a["case"]["verdict"] == "uncertain"]
    sars = [a for a in cases.values() if a["sar"]["file"]]
    changed = [a for a in cases.values() if a["next_best_actions"]["what_changed"] != "nothing"]
    def row(k, a):
        return (f"<tr class='row'><td class='mono'>{esc(k)}</td><td>{esc(a['case']['pattern'])}</td>"
                f"<td class='{vclass(a['case']['verdict'])}'><b>{esc(a['case']['verdict'])}</b> {a['case']['fraud_probability']:.2f}</td>"
                f"<td>{esc(a['next_best_actions']['initial'][0]['action'] if a['next_best_actions']['initial'] else '')}</td>"
                f"<td>{esc(a['next_best_actions']['final'][0]['action'])}</td></tr>")
    items = sorted(cases.items())
    head = "<tr><th>Case</th><th>Pattern</th><th>Verdict, p</th><th>Initial (first)</th><th>Final (first)</th></tr>"
    rows = (f"<div class='grid two' style='gap:14px'><table>{head}{''.join(row(k, a) for k, a in items[:10])}</table>"
            f"<table>{head}{''.join(row(k, a) for k, a in items[10:])}</table></div>")
    slides = [
        (page("""<div style='height:560px;display:flex;flex-direction:column;justify-content:center'>
<div class='eyebrow'>TigerGraph × Hacker House Goa</div><h1>HHGOA Fraud Investigator</h1>
<p style='font-size:28px;max-width:900px'>An agent that investigates fraud alerts on a transaction graph, knows when it needs more evidence, and recommends policy-compliant next best actions with approval routes.</p>
<div><span class='tag acc'>TigerGraph schema + GSQL</span><span class='tag acc'>MCP tools</span><span class='tag acc'>LangGraph</span><span class='tag acc'>Closed-case memory</span></div></div>"""),
         "This is the H H G O A Fraud Investigator, built for the TigerGraph Hacker House Goa challenge. "
         "It is an agent that investigates fraud alerts on a transaction graph, decides when it needs more evidence, "
         "and recommends next best actions that follow the bank's fraud policy, including who must approve them."),
        (page("""<h2>The data as a graph</h2><div class='grid three'>
<div class='card'><div class='eyebrow'>Transactions</div><h1>590,742</h1><p class='small'>All 393 Vesta columns, risk score, channel, real timestamps</p></div>
<div class='card'><div class='eyebrow'>Identity records</div><h1>144,432</h1><p class='small'>Device profile = DeviceInfo + OS + browser + screen, proxy and New/Found flags</p></div>
<div class='card'><div class='eyebrow'>Closed cases</div><h1>5,565</h1><p class='small'>4,665 confirmed fraud and 900 cleared: the agent's starting memory</p></div></div>
<div class='card'><p style='margin:0'>Vertices: Customer, Card, Transaction, DeviceProfile, EmailDomain, BillingRegion, ClosedCase. Card IDs are rebuilt exactly from the data (customer + card type order, 100% match on all 1,933 cards in the closed cases). GSQL queries: card_window, card_history, device_neighbors, region_history, similar_closed_cases.</p></div>"""),
         "We model the dataset as a graph. Five hundred ninety thousand transactions, a hundred forty four thousand identity records, "
         "and five thousand five hundred closed cases. Cards link to transactions, transactions link to device profiles, email domains and billing regions, "
         "and closed cases link back to the transactions they involved. Card identifiers are reconstructed exactly from the data, matching every card named in the closed cases."),
        (page("""<h2>Architecture</h2><div class='grid two'>
<div class='card'><div class='eyebrow'>Investigation loop (LangGraph)</div><ol style='margin:0'>
<li>Trigger: risk score, customer report or analyst request</li><li>Investigate: graph queries on the card, device, region and prior cases</li>
<li>Assess: fraud probability, pattern, episode, exposure</li><li>Initial next best action with approval route</li>
<li>Gather evidence: customer validation or step-up (simulated, recorded)</li><li>Final next best action, SAR if policy requires</li><li>Write the case to memory</li></ol></div>
<div class='card'><div class='eyebrow'>Tools and memory</div><p class='small'>Typed graph queries exposed as MCP tools; the agent never writes raw GSQL.</p>
<p class='small'>Case memory: similar closed cases retrieved per alert, plus a classifier trained only on the Jul to Oct closed cases using Vesta's unnamed features, cited as such.</p>
<p class='small'>Policy engine: rules R1 to R10, case versus report (3a), stopping rules (6), approval routes auto, L1, L2.</p></div></div>"""),
         "The architecture is a LangGraph loop. A trigger opens the investigation. The agent queries the graph for the card's timeline, the device profile and who else used it, "
         "billing regions, and similar closed cases. It assesses fraud probability and the pattern, logs an initial next best action with its approval route, "
         "gathers more evidence when the policy requires it, then records the final action and writes the case to memory. "
         "Graph access goes through typed tools, and case memory includes a classifier trained only on the bank's closed cases."),
        (page(f"""<h2>Results on the 20 benchmark cases</h2>
<div class='grid three' style='margin-bottom:10px'><div class='inset'><b class='fraud'>{len(fraud)}</b> fraud · <b class='legit'>{len(legit)}</b> legitimate · <b class='unc'>{len(unc)}</b> uncertain</div>
<div class='inset'><b>{len(changed)}</b> cases changed their recommendation after evidence</div><div class='inset'><b>{len(sars)}</b> suspicious activity reports</div></div>
{rows}"""),
         f"Here are all twenty cases. The agent found {len(fraud)} fraud cases, {len(legit)} legitimate and {len(unc)} it honestly marks as uncertain. "
         f"In {len(changed)} cases the recommendation changed after more evidence came in, and {len(sars)} cases need a suspicious activity report. "
         "An agent that blocks everything scores badly here, so most alerts are verified before anything is blocked."),
    ]
    picks = [("HHG-006", "Undocumented: just-under-$500 burst",
              "Case six is a customer report. The graph shows four online purchases in thirty minutes, each just under five hundred dollars, from devices new to the account. "
              "None of the five documented patterns fits, but the agent retrieves closed cases C C 3748 and its siblings, which describe the same shape. "
              "So it calls the pattern undocumented, describes it in its own words, and after the customer's denial recommends blocking the card with team lead approval, "
              "opening a case, filing a report with fraud manager approval, and escalating to an analyst."),
             ("HHG-014", "Undocumented: shared device ring",
              "Case fourteen came from an analyst. Traversing from the transaction to its device profile shows a Samsung phone behind an anonymous proxy used on many other cards the same month, "
              "the same profile the bank's closed cases describe. That is a shared-origin ring, so the agent files a report, monitors every connected card, and escalates."),
             ("HHG-001", "Risk score alone, legitimate",
              "Case one had a risk score of point six one. The card had used billing region four four four ten times in the last ninety days, the amount repeats the cardholder's own history, "
              "and the closed-case classifier scores it near zero. With independent evidence on the legitimate side, the agent stops early and closes the alert without contacting the customer."),
             ("HHG-019", "Verify first, then act",
              "Case nineteen is an online purchase from a new device. The evidence leans toward fraud at point seven three, but under rule one that is not enough to block, so the agent opens a case and verifies with the customer. "
              "With the assumed denial the probability rises to point nine five, and the final actions become block, case, and a report, because the same device profile links two other cards with suspected fraud."),
             ("HHG-011", "Honest uncertainty",
              "Case eleven is a customer dispute where the evidence is balanced. The agent assumes no reply within twenty four hours, so it follows rule four and rule eight: "
              "monitor the card, decline pending authorizations with team lead approval, and escalate to an analyst, with the verdict recorded as uncertain.")]
    for cid, title, narr in picks:
        if cid in cases:
            slides.append((case_slide(cases[cid], title), narr))
    sar_case = next((a for a in cases.values() if a["sar"]["file"]), None)
    if sar_case:
        slides.append((page(f"""<div class='eyebrow'>{esc(sar_case['case_id'])} · Suspicious activity report</div><h2>A report that stands on its own</h2>
<div class='card'><p class='small' style='margin:0'>{esc(sar_case['sar']['narrative'][:1100])}</p></div>
<div class='inset small'>Reason: {esc(sar_case['sar']['reason'])} · Total ${sar_case['sar']['total_amount_usd']:,.2f} · {esc(' to '.join(sar_case['sar']['activity_dates']))}</div>"""),
                       "When the policy calls for a report, the agent writes a narrative covering who, what, when, where, how and why it is suspicious, "
                       "citing the transactions, the devices and the matching closed cases, and it keeps the report consistent with the file report action and its approval route."))
    slides.append((page("""<div style='height:560px;display:flex;flex-direction:column;justify-content:center'>
<h1>Explainable, policy-bound, memory-driven</h1><p style='font-size:24px;max-width:1000px'>Every claim cites a graph query, a document rule or an assumed customer response. Every action carries its policy rule and approval route. Answer files for all 20 cases are in the repository's cases folder.</p>
<p style='font-size:22px'>Next: run on TigerGraph Savanna with vector search over policies and case narratives, and let an LLM write case summaries from the retrieved evidence.</p></div>"""),
                   "Every claim in a case file cites a graph query, a policy rule, or an assumed customer response, and every action carries its rule and approval route. "
                   "The answer files for all twenty cases are in the repository. Next, we would run it on TigerGraph Savanna with vector search over the policy and case narratives. Thanks for watching."))
    return slides


def tts(text: str, wav: Path) -> float:
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate = 0; "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak([IO.File]::ReadAllText('{wav.with_suffix('.txt')}')); $s.Dispose()")
    wav.with_suffix(".txt").write_text(text, encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    cases = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES_OUT.glob("HHG-*.json"))}
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    parts = []
    for i, (body, narration) in enumerate(build_slides(cases), start=1):
        htm, png, wav, mp4 = (WORK / f"s{i:02d}{ext}" for ext in (".html", ".png", ".wav", ".mp4"))
        htm.write_text(body, encoding="utf-8")
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--screenshot={png}",
                        "--window-size=1280,720", htm.as_uri()], check=True, capture_output=True)
        dur = tts(narration, wav) + 0.8
        subprocess.run([ff, "-y", "-loop", "1", "-i", str(png), "-i", str(wav), "-c:v", "libx264", "-tune", "stillimage",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-t", f"{dur:.2f}", "-vf", "scale=1280:720",
                        str(mp4)], check=True, capture_output=True)
        parts.append(mp4)
        print(f"slide {i}: {dur:.1f}s")
    lst = WORK / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    out = OUT / "hhgoa_demo.mp4"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True, capture_output=True)
    print("video:", out)


if __name__ == "__main__":
    main()
