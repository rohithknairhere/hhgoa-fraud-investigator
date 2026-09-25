"""Render the demo video from the live dashboard.

Playwright drives the installed Edge browser to capture the real dashboard (including clicking
Execute Next Best Action), a few HTML slides explain the architecture, Windows text-to-speech reads
the narration, and ffmpeg joins everything into <repo>/demo/hhgoa_demo.mp4.

    python -m hhgoa.build_video     (run from backend/, with the dashboard running on localhost:3000)
"""

from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image
from playwright.sync_api import sync_playwright

from hhgoa.paths import REPO

OUT = REPO / "demo"
WORK = OUT / "build"
BASE = "http://localhost:3000"
W, H = 1280, 720

CSS = """
body{margin:0;width:1280px;height:720px;background:#e0e5ec;font-family:'Segoe UI',Arial,sans-serif;color:#1e293b;overflow:hidden}
.wrap{padding:48px 64px}
.card{background:#e0e5ec;border-radius:26px;box-shadow:-8px -8px 16px #fff,8px 8px 16px #a3b1c6;padding:22px 26px}
h1{font-size:50px;margin:0 0 10px;font-weight:900}
h2{font-size:36px;margin:0 0 18px;font-weight:800}
.eyebrow{font-size:15px;letter-spacing:2px;text-transform:uppercase;color:#334155;font-weight:700;margin-bottom:8px}
p,li{font-size:21px;line-height:1.45}
.grid{display:grid;gap:18px}.two{grid-template-columns:1fr 1fr}
.big{font-size:40px;font-weight:900;font-family:Consolas,monospace}
.tag{display:inline-block;border-radius:999px;padding:6px 14px;font-weight:700;font-size:17px;margin:3px;color:#3730a3;box-shadow:inset 2px 2px 4px #a3b1c6,inset -2px -2px 4px #fff}
"""


def slide(body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='wrap'>{body}</div></body></html>"


def fit(src: Path, dst: Path) -> None:
    """Place a screenshot of any size on a 1280x720 canvas."""
    im = Image.open(src).convert("RGB")
    scale = min(W / im.width, H / im.height, 1.0)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), (224, 229, 236))
    canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    canvas.save(dst)


def summary_numbers() -> dict:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((REPO / "cases").glob("HHG-*.json"))]
    mon = json.loads((REPO / "monitoring" / "summary.json").read_text(encoding="utf-8"))
    ring = json.loads(next((REPO / "monitoring").glob("MON-RING-*.json")).read_text(encoding="utf-8"))
    return {
        "fraud": sum(c["case"]["verdict"] == "fraud" for c in cases),
        "legit": sum(c["case"]["verdict"] == "legitimate" for c in cases),
        "unc": sum(c["case"]["verdict"] == "uncertain" for c in cases),
        "changed": sum(c["next_best_actions"]["what_changed"] != "nothing" for c in cases),
        "sar": sum(c["sar"]["file"] for c in cases),
        "graph": sum(c["case"]["written_to_graph"] for c in cases),
        "tokens": sum(c["tokens"] for c in cases),
        "ring_cards": len(ring["card_ids"]),
        "bursts": mon["bursts"],
    }


def segments(n: dict) -> list[tuple[str, object, str]]:
    return [
        ("html", slide("""<div style='height:600px;display:flex;flex-direction:column;justify-content:center'>
<div class='eyebrow'>TigerGraph | Hacker House Goa</div><h1>HHGOA Fraud Investigator</h1>
<p style='font-size:27px;max-width:950px'>An agent that investigates card fraud alerts on TigerGraph, knows when it needs more evidence, and recommends next best actions under the bank's fraud policy, with the approval each action needs.</p>
<div><span class='tag'>TigerGraph Savanna</span><span class='tag'>TigerGraph MCP</span><span class='tag'>GSQL + graph algorithms</span><span class='tag'>GraphRAG with vector search</span><span class='tag'>LangGraph</span><span class='tag'>Gemini</span></div></div>"""),
         "This is our fraud investigation agent for the TigerGraph Hacker House Goa challenge. It investigates each alert on a TigerGraph graph, "
         "decides whether it has enough evidence to act, and recommends next best actions under the bank's fraud policy, including who has to approve them."),
        ("html", slide("""<h2>How it fits together</h2><div class='grid two'>
<div class='card'><div class='eyebrow'>Graph on TigerGraph Savanna</div><p>590,742 transactions, 14,317 cards, 9,700 device profiles, 5,565 closed cases.</p>
<p>Knowledge chunks for the policy, the patterns and closed case narratives, each with a vector.</p><p>Every finished case is written back as an InvestigationCase vertex.</p></div>
<div class='card'><div class='eyebrow'>Agent</div><p>LangGraph workflow: trigger, investigate, assess, initial action, gather evidence, final action, explain, write back.</p>
<p>Graph access only through the official TigerGraph MCP server, limited to installed queries and case writes.</p><p>Gemini writes summaries and reports from vector-retrieved policy text. Decisions stay with the policy engine.</p></div></div>"""),
         "Here is the architecture. All the data lives in one graph on TigerGraph Savanna: transactions, cards, device profiles, billing regions and the bank's closed cases. "
         "The fraud policy, the pattern descriptions and the closed case narratives are stored as vectors in the same graph. "
         "The agent is a LangGraph workflow. It only reaches the graph through the official TigerGraph MCP server, limited to installed queries and writing cases back. "
         "Gemini writes the case summaries and reports from text retrieved by vector search, while the decisions stay with the policy engine."),
        ("page", ("/", None, None),
         f"This is the analyst dashboard. The agent found {n['fraud']} fraud cases, {n['legit']} legitimate and {n['unc']} it marks as uncertain. "
         f"{n['changed']} recommendations changed after more evidence came in, {n['sar']} cases need a suspicious activity report, and all {n['graph']} cases were written back to TigerGraph."),
        ("page", ("/", "ul[aria-label='Benchmark cases']", "viewport"),
         "Each card is one of the twenty benchmark cases, showing the trigger, the verdict, the fraud probability, the exposure and the next best action."),
        ("page", ("/cases/HHG-006", "header", None),
         "Case six started with a customer saying they never made a four hundred and eighty two dollar purchase. The graph shows four online purchases in thirty minutes, "
         "each just under five hundred dollars. None of the five documented patterns fits, so the agent marks it undocumented and describes it in its own words."),
        ("page", ("/cases/HHG-006", "#progression", None),
         "The case progression shows every step. The agent made nine graph and retrieval calls through MCP, retrieved matching closed cases like C C 3748, "
         "asked the customer to confirm, and recorded the assumed reply before changing its recommendation."),
        ("page", ("/cases/HHG-006", "#action-terminal", "click"),
         "This is the action terminal. When the analyst presses execute, the agent runs only the actions it is allowed to run on its own, like opening the case and escalating. "
         "Blocking the card goes to a team lead, and filing the report goes to a fraud manager, exactly as the policy says."),
        ("page", ("/cases/HHG-006", "#sar", None),
         "Because the pattern is undocumented and the exposure is over a thousand dollars, the policy requires a suspicious activity report. "
         "The narrative is written by the language model from the graph evidence and the retrieved policy text, and any identifier it did not see is rejected."),
        ("page", ("/cases/HHG-019", "#nba", None),
         "Case nineteen shows the agent handling uncertainty. The evidence leaned toward fraud at point seven three, but under rule one that is not enough to block, "
         "so the first recommendation is to verify with the customer. After the assumed denial the probability rises to point nine five and the actions change to a block, a case and a report."),
        ("page", ("/cases/HHG-001", "header", None),
         "Not every alert is fraud. Case one had a risk score of point six one, but the card uses that billing region regularly and repeats the same purchase. "
         "With independent signals on the legitimate side, the agent stops early and closes the alert without bothering the customer."),
        ("page", ("/cases/HHG-011", "#progression", None),
         "Case eleven is genuinely ambiguous. The agent assumes no reply within a day, so it monitors the card, declines pending authorizations, "
         "and escalates to an analyst with the verdict recorded as uncertain."),
        ("page", ("/cases/HHG-014", "#graph-context", None),
         "Case fourteen came from an analyst asking about an unusual device. The sub-graph links the flagged card to the device and to twenty four other cards that used it behind an anonymous proxy, "
         "so the agent monitors every connected card and files a report."),
        ("html", slide(f"""<h2>Watching beyond the twenty cases</h2><div class='grid two'>
<div class='card'><div class='eyebrow'>Graph algorithm</div><p class='big'>{n['ring_cards']} cards</p><p>Connected components over cards and proxied device profiles in November and December find one ring around a single Samsung phone profile, the device behind HHG-014.</p></div>
<div class='card'><div class='eyebrow'>Threshold bursts</div><p class='big'>{n['bursts']} cards</p><p>Three or more purchases between $450 and $500 inside an hour from a new device. One is HHG-006; the other is a card outside the benchmark.</p></div></div>"""),
         f"The agent also watches the exam period on its own. A connected components query in GSQL, run over cards and proxied device profiles, finds a ring of {n['ring_cards']} cards around one phone. "
         f"A second scan finds {n['bursts']} cards with bursts just under five hundred dollars, including one that is not in the benchmark. These alerts are saved separately."),
        ("html", slide(f"""<div style='height:600px;display:flex;flex-direction:column;justify-content:center'>
<h1>Evidence first, then words</h1><p style='font-size:25px;max-width:1050px'>Every claim cites a graph query, a policy rule or an assumed customer reply. Every action carries its rule and approval route. Twenty answer files are in the repository's cases folder, and all twenty cases are stored in TigerGraph as case memory.</p>
<p style='font-size:22px'>{n['tokens']:,} Gemini tokens across the twenty cases.</p></div>"""),
         "To sum up: every claim in a case file points to a graph query, a policy rule or an assumed customer reply, every action carries its rule and approval route, "
         "and every case is stored in TigerGraph so the next investigation can learn from it. Thanks for watching."),
    ]


def tts(text: str, wav: Path) -> float:
    txt = wav.with_suffix(".txt")
    txt.write_text(text, encoding="utf-8")
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate = 0; "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak([IO.File]::ReadAllText('{txt}')); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def capture(page, spec, raw: Path) -> None:
    path, selector, action = spec
    page.goto(BASE + path, wait_until="networkidle")
    if selector:
        loc = page.locator(selector).first
        loc.scroll_into_view_if_needed()
        if action == "click":
            page.get_by_role("button", name="Execute Next Best Action").click()
            page.wait_for_timeout(400)
        if action == "viewport":
            page.evaluate("document.querySelector(\"ul[aria-label='Benchmark cases']\").scrollIntoView()")
            page.evaluate("window.scrollBy(0, -90)")
            page.wait_for_timeout(300)
            page.screenshot(path=str(raw))
        else:
            loc.screenshot(path=str(raw))
    else:
        page.screenshot(path=str(raw))


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    segs = segments(summary_numbers())
    parts = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
        ctx.add_init_script("try { localStorage.setItem('hhgoa-cookie-consent', 'essential'); } catch (e) {}")
        page = ctx.new_page()
        for i, (kind, spec, narration) in enumerate(segs, start=1):
            raw, png, wav, mp4 = (WORK / f"v{i:02d}{ext}" for ext in ("_raw.png", ".png", ".wav", ".mp4"))
            if kind == "html":
                page.set_content(spec)
                page.screenshot(path=str(raw))
            else:
                capture(page, spec, raw)
            fit(raw, png)
            dur = tts(narration, wav) + 0.8
            subprocess.run([ff, "-y", "-loop", "1", "-i", str(png), "-i", str(wav), "-c:v", "libx264", "-tune", "stillimage",
                            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-t", f"{dur:.2f}",
                            str(mp4)], check=True, capture_output=True)
            parts.append(mp4)
            print(f"segment {i}: {dur:.1f}s")
        browser.close()
    lst = WORK / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    out = OUT / "hhgoa_demo.mp4"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True, capture_output=True)
    print("video:", out)


if __name__ == "__main__":
    main()
