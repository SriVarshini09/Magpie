// Makes public/og.png (1200x630), the link-preview image, from the product itself: the live 3D stage.
//
//   1. Start the app (any dev server) and open  /views  →  "SO-101 arm"  in a browser.
//   2. node scripts/make-og.mjs            (listens on http://localhost:5199 until one image arrives)
//   3. Paste the snippet this script prints into the browser's console.
//
// The snippet draws one frame of the stage's own canvas onto a 1200x630 canvas with the name and the line from
// index.html, in the page's own fonts and tokens, and posts the PNG here. Nothing leaves the machine.
import { writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "og.png");
const PORT = 5199;

export const SNIPPET = `(async () => {
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const stage = document.querySelector("canvas");
  if (!stage) throw new Error("Open a 3D view first");
  await document.fonts.ready;
  const W = 1200, H = 630;
  const c = Object.assign(document.createElement("canvas"), { width: W, height: H });
  const g = c.getContext("2d");
  g.fillStyle = css("--b2c-stage");
  g.fillRect(0, 0, W, H);
  let glow = g.createRadialGradient(820, 250, 0, 820, 250, 620);
  glow.addColorStop(0, "rgba(255,255,255,0.10)");
  glow.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = glow;
  g.fillRect(0, 0, W, H);
  glow = g.createRadialGradient(600, 700, 0, 600, 700, 560);
  glow.addColorStop(0, "rgba(37,99,235,0.16)");
  glow.addColorStop(1, "rgba(37,99,235,0)");
  g.fillStyle = glow;
  g.fillRect(0, 0, W, H);
  // One fresh frame, read back in the same task (the canvas does not keep its drawing buffer).
  window.__b2cBench && window.__b2cBench(1);
  const side = Math.min(stage.width, stage.height * 1.15);
  const sx = (stage.width - side) / 2, sh = side / 1.15, sy = (stage.height - sh) / 2;
  g.drawImage(stage, sx, sy, side, sh, 470, -6, 740, 740 / 1.15);
  const sans = css("--b2c-font-sans"), mono = css("--b2c-font-mono");
  // The mark from favicon.svg.
  g.save();
  g.translate(72, 150);
  g.scale(2.6, 2.6);
  g.lineWidth = 2; g.lineCap = "round"; g.lineJoin = "round";
  g.strokeStyle = css("--b2c-stage-text");
  g.stroke(new Path2D("M12 2.6 20.1 7.3v9.4L12 21.4 3.9 16.7V7.3z"));
  g.strokeStyle = css("--b2c-light-rim");
  g.stroke(new Path2D("m8.4 12.3 2.5 2.5 4.7-5.3"));
  g.restore();
  g.fillStyle = css("--b2c-stage-text");
  g.font = "600 34px " + sans;
  g.fillText("Build-to-Cart", 150, 193);
  g.font = "650 62px " + sans;
  ["Type it, paste it,", "or snap it."].forEach((t, i) => g.fillText(t, 72, 318 + i * 72));
  g.fillStyle = css("--b2c-stage-muted");
  g.font = "400 27px " + sans;
  ["A parts list where every line says", "where it came from. One cart.", "You approve once."].forEach((t, i) => g.fillText(t, 72, 462 + i * 38));
  g.font = "500 18px " + mono;
  g.fillText("live 3D view of the SO-101 arm", 72, 592);
  const blob = await new Promise((r) => c.toBlob(r, "image/png"));
  await fetch("http://localhost:${PORT}/og", { method: "POST", mode: "no-cors", body: blob });
  return blob.size;
})()`;

if (process.argv.includes("--snippet")) {
  console.log(SNIPPET);
  process.exit(0);
}

const server = createServer((req, res) => {
  if (req.method !== "POST") return res.writeHead(204, { "Access-Control-Allow-Origin": "*" }).end();
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", async () => {
    const png = Buffer.concat(chunks);
    const ok = png.length > 1000 && png.subarray(1, 4).toString() === "PNG";
    if (ok) await writeFile(out, png);
    res.writeHead(ok ? 200 : 400, { "Access-Control-Allow-Origin": "*" }).end();
    console.log(ok ? `Wrote ${out} (${(png.length / 1024).toFixed(0)} KB)` : "That was not a PNG; nothing written.");
    server.close();
  });
});
server.listen(PORT, "127.0.0.1", () => console.log(`Waiting on http://localhost:${PORT}/og. Paste this into the console of a page showing a 3D view:\n\n${SNIPPET}\n`));
