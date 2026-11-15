"""Record a scripted CaseNote demo as sharp screenshots + a timestamped step log.

Runs the real app in Google Chrome (headless) via Playwright. The spoken
question is fed through Chrome's fake microphone, so the real Argmax
transcription path runs. Nothing is faked in the app itself.

  .venv/bin/python tools/record_demo.py video/take1 [--countdown 25]
"""

import argparse
import asyncio
import json
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = "http://localhost:8765"
Q_WAV = ROOT / "video/question_zh.wav"
Q_SPEAK_SECONDS = 0.4 + 3.92 + 0.6  # padded clip: 0.4 s lead, 3.92 s speech


def wifi_state() -> str:
    try:
        out = subprocess.run(["networksetup", "-getairportpower", "en0"], capture_output=True, text=True).stdout.strip()
    except Exception:
        out = "unknown"
    ping = subprocess.run(["ping", "-c", "1", "-t", "2", "1.1.1.1"], capture_output=True).returncode == 0
    return f"{out}; internet reachable: {ping}"


async def main(out: Path, countdown: int):
    frames = out / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for i in range(countdown, 0, -1):
        print(f"Recording starts in {i:2d} s  (turn WiFi off now if this is the final take)", flush=True)
        await asyncio.sleep(1)
    log = {"wifi_at_start": wifi_state(), "steps": [], "frames": []}
    print("WiFi:", log["wifi_at_start"], flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True, args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-audio-capture={Q_WAV}", "--autoplay-policy=no-user-gesture-required"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        await ctx.grant_permissions(["microphone"], origin=URL)
        page = await ctx.new_page()
        t0 = time.monotonic()
        running = True

        def mark(name):
            t = round(time.monotonic() - t0, 2)
            log["steps"].append({"t": t, "step": name})
            print(f"[{t:7.2f}s] {name}", flush=True)

        async def capture():
            n = 0
            while running:
                t = time.monotonic() - t0
                path = frames / f"{n:05d}.jpg"
                try:
                    await page.screenshot(path=str(path), type="jpeg", quality=88)
                    log["frames"].append({"t": round(t, 3), "file": path.name})
                    n += 1
                except Exception:
                    await asyncio.sleep(0.05)

        await page.request.post(URL + "/api/reset")
        await page.goto(URL)
        await page.wait_for_timeout(800)
        cap = asyncio.create_task(capture())
        mark("empty")
        log["online_in_browser"] = await page.evaluate("navigator.onLine")
        await page.wait_for_timeout(3000)

        mark("docs_start")
        await page.click("#demo")
        await page.wait_for_function("document.querySelectorAll('.finding').length >= 2", timeout=240000)
        mark("findings")
        await page.wait_for_timeout(3500)

        await page.locator(".finding").nth(1).click()
        mark("sheet")
        await page.wait_for_timeout(4500)
        await page.keyboard.press("Escape")
        mark("sheet_close")
        await page.wait_for_timeout(800)

        # your path: scroll it into view and read down through the stages
        await page.evaluate("window.scrollTo({top: document.querySelector('#path').getBoundingClientRect().top + window.scrollY - 90, behavior:'smooth'})")
        mark("path")
        await page.wait_for_timeout(2500)
        for _ in range(3):
            await page.evaluate("window.scrollBy({top:120, behavior:'smooth'})")
            await page.wait_for_timeout(1800)
        mark("path_end")
        await page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
        await page.wait_for_timeout(1200)

        n_answers = await page.locator(".msg.a").count()
        await page.click("#mic")
        await page.wait_for_selector("#mic.rec", timeout=15000)
        mark("rec_start")
        await page.wait_for_timeout(int(Q_SPEAK_SECONDS * 1000))
        await page.click("#mic")
        await page.wait_for_selector("#mic:not(.rec)", timeout=15000)
        mark("rec_stop")
        await page.wait_for_function(
            f"document.querySelectorAll('.msg.a').length > {n_answers} && !document.querySelector('.msg.pending')", timeout=240000)
        mark("answer")
        await page.wait_for_timeout(7000)

        await page.evaluate("document.querySelector('#timeline').scrollIntoView({behavior:'smooth', block:'center'})")
        mark("deadlines")
        await page.wait_for_timeout(2500)
        await page.hover(".tl-foot .textbtn")
        await page.wait_for_timeout(2500)

        await page.evaluate("document.querySelector('#crec').scrollIntoView({behavior:'smooth', block:'start'})")
        await page.wait_for_timeout(1200)
        await page.click("#csample")
        mark("meeting_start")
        await page.wait_for_function("document.querySelector('#cbody .line')", timeout=240000)
        mark("meeting_done")
        await page.evaluate("document.querySelector('#cbody').scrollIntoView({behavior:'smooth', block:'center'})")
        await page.wait_for_timeout(5500)

        await page.evaluate("document.querySelector('#packet').scrollIntoView({behavior:'smooth', block:'center'})")
        await page.wait_for_timeout(1000)
        async with ctx.expect_page(timeout=240000) as popup:
            await page.click("#packet")
            mark("packet_start")
        pdf_page = await popup.value
        mark("packet_done")
        await page.wait_for_timeout(2000)
        running = False
        await cap
        await pdf_page.close()

        # save the packet the app produced, for the end of the video
        r = await page.request.post(URL + "/api/packet", multipart={"return_date": await page.input_value("#rd")})
        (out / "packet.pdf").write_bytes(await r.body())
        await browser.close()

    log["wifi_at_end"] = wifi_state()
    (out / "log.json").write_text(json.dumps(log, indent=1))
    print("WiFi:", log["wifi_at_end"], flush=True)
    print(f"DONE. {len(log['frames'])} frames in {out}. You can turn WiFi back on.", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--countdown", type=int, default=0)
    a = ap.parse_args()
    asyncio.run(main(ROOT / a.out, a.countdown))
