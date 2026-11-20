# 3D "split into parts" view: research for Build-to-Cart

Checked on Fri 20 Nov 2026 between about 05:00 and 06:30 UTC. Stars, last push and license come from the GitHub API. Versions and peer dependencies come from the npm registry. Model and Space status comes from the Hugging Face API. Pages were opened with a fetcher; where a site blocked it, the entry says so.

Legend: ★ = GitHub stars; "push" = last push date; **[unverified]** = I could not confirm it from a primary source; **NC / SA / no-redistribution** flags are in bold.

Everything here was read-only. Nothing was installed, cloned, run, downloaded or signed up for.

---

## TL;DR: the 12 things to use tomorrow

| # | Use | URL | License | What it adds | Min |
|---|---|---|---|---|---|
| 1 | **Pinned, known-good versions**: `react@19.3.1 react-dom@19.3.1 three@0.186.1 @react-three/fiber@9.8.2 @react-three/drei@10.7.9 @react-three/postprocessing@3.2.2 postprocessing@6.39.6` | npmjs.com/package/@react-three/fiber | MIT / Zlib | No peer-dependency surprises. Fiber 9.8.2 requires React `>=19 <19.4`. postprocessing 6.39.6 requires three `<0.188`. Nearly the same set ships in codepawl's r3f "Learn Arduino in 3D" build, which used @react-three/postprocessing 3.2.1, postprocessing 6.39.5 and n8ao 2.0.1. | 5 |
| 2 | **Offline studio lighting**: three's built-in `RoomEnvironment` through `PMREMGenerator` (no file at all), and optionally Poly Haven `studio_small_03_1k.hdr` (1.69 MB) through `<Environment files="/hdri/studio_small_03_1k.hdr" />` | polyhaven.com/a/studio_small_03 | three.js MIT; HDRI **CC0** | Fixes the CDN-preset problem. drei's `preset="studio"` *is* `studio_small_03_1k.hdr`, fetched from raw.githack.com, so self-hosting it gives the same look offline. | 10 |
| 3 | **drei `CameraControls`** with `fitToBox(mesh, true)` for click-to-focus and `setLookAt(..., true)` for scripted moves | drei.docs.pmnd.rs/controls/camera-controls | MIT | Smooth, damped "fly to part" and an intro camera move with no animation library | 20 |
| 4 | **drei `Outlines` + emissive tint** for hover; **drei `Edges`** for the grey "not found yet" state | drei.docs.pmnd.rs/abstractions/outlines | MIT | A per-mesh hover outline (inverted hull, `screenspace` for constant width on a projector) and crisp CAD edges. `Edges` is built on drei `Line`, so line widths above 1 px work on Windows, where `lineBasicMaterial` is stuck at 1 px. | 20 |
| 5 | **drei `<Bvh firstHitOnly>` + `<ContactShadows>`** | drei.docs.pmnd.rs/performances/bvh | MIT (three-mesh-bvh) | Instant hover picking over about 400k STL triangles, plus a soft "product on a table" shadow | 5 |
| 6 | **maath `easing.damp` / `damp3` / `dampC`** | github.com/pmndrs/maath | MIT | Frame-rate-independent easing for the explode slider, ghost opacity and colour-mode changes, with no spring library needed | 10 |
| 7 | **`@react-three/postprocessing`: `N8AO` + `SMAA`** (plus `Outline` inside `<Selection>` only if `Outlines` looks bad on the STLs) | react-postprocessing.docs.pmnd.rs | MIT; n8ao CC0-1.0 (GitHub) / ISC (npm) | Ambient occlusion makes the stacked printed parts read as separate solids. This is the single biggest "looks expensive" switch. | 20 |
| 8 | **KitSmith SO-101 r3f viewer** as the reference implementation (`viewer/src/island/Viewer.tsx`) | github.com/Guillaume-Georges/so101-assembly-guide | MIT | The same robot in r3f. It ghosts future parts at 0.12 opacity, puts `Outlines` and a tint on the current part, draws edges at 25°, smooths STL facets with `toCreasedNormals`, uses a local `MeshoptDecoder` and lights with `RoomEnvironment`. Read it; don't fork it. | 20 (read) |
| 9 | **`exploded-view` skill from Moh4696/open-3d-skills** (`assets/explode.js`: `Exploder`, `Labels`, `Xray`, `Section`, `Picker`) | github.com/Moh4696/open-3d-skills/tree/main/skills/exploded-view | MIT | Staged explode in mechanic's order, two-column screen-edge labels with leader lines that never overlap, x-ray shells and a section cut. Port the ideas to r3f. | 45 |
| 10 | **Claude Code skills: `CloudAI-X/threejs-skills` + Anthropic `frontend-design`** | github.com/CloudAI-X/threejs-skills · github.com/anthropics/claude-plugins-official | MIT · Apache-2.0 | Agents write r186 / Fiber 9.8 / drei 10.7 code instead of stale APIs, and the panels get a real design direction. Both are plain Markdown, with no scripts or hooks. | 5 |
| 11 | **Adafruit_CAD_Parts** (ESP32 Feather HUZZAH32, BME280 breakout, 500 mAh LiPo, 2.9" E-Ink FeatherWing) → **3dviewer.net** (processes files in the browser, exports GLB) | github.com/adafruit/Adafruit_CAD_Parts · 3dviewer.net | **MIT** (parts) · MIT (viewer) | The only clean-license electronics models found. Label them "stand-in" because they are not FireBeetle or Waveshare parts. | 40 |
| 12 | **`@xyflow/react` 13** for the ESP32 board diagram, plus a **CSS-3D "exploded stack"** (four layered divs with `rotateX(55deg) rotateZ(-45deg) translateZ(n * explode)`) | npmjs.com/package/@xyflow/react | MIT | Both demos share one gesture: the same explode slider takes the arm apart and fans out the e-paper / board / sensor / battery layers. No new dependency. | 45 |

**Ranked just outside the 12:** the glTF-Transform pipeline (section 6, optional: localhost STL loads fast enough). TRELLIS.2 on Hugging Face (MIT, free ZeroGPU Space running), only as disclosed pre-event prep and only if the Adafruit stand-ins look wrong. codepawl's "Learn Arduino in 3D" (MIT, same r3f stack) as the pattern for building the ESP32 boards in code from real dimensions, with parts flying from a tray into place.

**Avoid tomorrow:** drei `preset=` HDRIs (CDN), Draco-compressed GLBs (the decoder comes from gstatic), drei `<Text>` without a local `font` (loads Google Fonts), Theatre.js (AGPL studio, Fiber 8 only, no push since Aug 2024), `framer-motion-3d` (deprecated on npm), xeokit / chili3d (**AGPL**), Z-Anatomy assets (**SA + some NC**), and installing more than about 4 skills.

---

## 1. Claude Code / Agent Skills

### 1.1 Anthropic official

| Item | URL | ★ / push | License | What it contains | Trust read |
|---|---|---|---|---|---|
| `anthropics/skills` | github.com/anthropics/skills | 197,794 / 2026-11-16 | Per-skill `LICENSE.txt`, Apache-2.0 (README says the skills, document skills included, are Apache 2.0; the repo root has no SPDX license) | `frontend-design`, `canvas-design`, `algorithmic-art`, `theme-factory`, `web-artifacts-builder`, `webapp-testing`, `skill-creator`, docx/pdf/pptx/xlsx, and more | `frontend-design` is pure instructions (palette, type, layout, restraint; it names AI-default looks to avoid). `web-artifacts-builder` runs `scripts/init-artifact.sh`, ships a `shadcn-components.tar.gz` and targets **React 18 + Parcel for claude.ai artifacts**, so it is wrong for our Vite / React 19 app. `webapp-testing` (Playwright) tells the agent "DO NOT read the source until you try running the script first", which is black-box script execution; it is official but worth knowing. |
| `frontend-design` plugin | github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design | 47,741 / 2026-11-20 | Apache-2.0 | The same `frontend-design` SKILL.md, packaged alone | Cleanest way to get only this skill |
| `shadcn` skill (official, shadcn/ui) | github.com/shadcn-ui/ui/tree/main/skills/shadcn | 128,602 / 2026-11-19 | MIT | CLI-driven component add/search/fix, rules for Radix and Base UI | **Runs commands on load.** The frontmatter pre-approves `Bash(npx shadcn@latest *)`, and the body has a dynamic-context line `` !`npx shadcn@latest info --json` ``, so each load fetches and runs the latest CLI from npm. That is useful for a shadcn team, but it is remote code at `@latest`. |

Install `frontend-design` in Claude Code: `/plugin marketplace add anthropics/claude-plugins-official` (skip this if the marketplace is already listed), then `/plugin install frontend-design@claude-plugins-official`. The broader set: `/plugin marketplace add anthropics/skills` → `/plugin install example-skills@anthropic-agent-skills`. That pulls in the script-running skills too, so prefer the single plugin.

### 1.2 3D, three.js and r3f skills (every SKILL.md listed below was opened)

| Repo | ★ / created / push | License | What it is | Relevance to our r3f part viewer | Safety read |
|---|---|---|---|---|---|
| **CloudAI-X/threejs-skills** | 4,299 / ? / 2026-10-19 | MIT | 13 skills (fundamentals, geometry, materials, lighting, textures, animation, loaders, shaders, postprocessing, interaction, performance, **react-three-fiber**, **asset-pipeline**). They target three r186, Fiber 9.8, drei 10.7 and gltf-transform 4.5, and each has a "Common Mistakes" list. | **High.** It correctly notes that drei `useGLTF` pulls Draco from gstatic, covers `Bounds` / `CameraControls` / `Lightformer`, and gives gltf-transform commands. | Markdown only, no scripts and no hooks. The only commands are `npx @gltf-transform/cli ...` examples. **Best pick.** |
| **Moh4696/open-3d-skills** | 436 / 2026-10-31 / 2026-11-09 | MIT | 8 skills. **`exploded-view`** (staged explode, x-ray, section, two-column leader labels, picker) plus `threejs-scene`, `scroll-film`, `site-check`, `frame-capture`, `alpha-cutout`, `cursor-rig`, `motion-assets` | **High for `exploded-view` alone.** It is vanilla three r169 with an import map, so tell the agent to port it to r3f and not add a CDN import map. | Other skills need `pip install` (opencv, playwright) and image-to-video models. The repo has `install.sh`. Install only the one skill. |
| **EnzeD/r3f-skills** | 138 / ? / 2026-08-31 | **none** (no LICENSE file) | 11 r3f skills, reviewed 2026-08-31 against Fiber 9.7.0 / drei 10.7.8. Good on version discipline; it says drei presets "depend on external hosting". | Medium-high | Skills are Markdown. The repo has eval and browser-check scripts that the skills don't call. **No license, so use it locally and don't commit it to the public repo.** |
| **Impertio-Studio/Three.js-Claude-Skill-Package** (old link `OpenAEC-Foundation/...` redirects) | 31 / 2026-03-20 / 2026-07-08 | MIT | 24 "deterministic" skills (core, errors, r3f, IFC, physics, model optimizer) | Low-medium | No scripts. **Its `model-optimizer` skill recommends `flatten` + `join`, which merges our parts into one mesh and breaks per-part picking.** |
| **emalorenzo/three-agent-skills** | 75 / 2026-01-16 / 2026-01-28 | **none** at repo level (SKILL.md frontmatter says MIT) | `r3f-best-practices`, `three-best-practices` (cites the Utsubo "100 tips") | Low-medium, stale | Ships opaque `.zip` copies of the skills. Its example import map loads three 0.182 from jsDelivr (offline trap). |
| **scottstts/Threejs-Awesome-Graphics-Agent-Skills** | 1,016 / 2026-06-19 / 2026-10-22 | MIT | 24 advanced graphics skills (aerial perspective, bloom with material restoration, exposure, parallax occlusion, precipitation...), mostly WebGPU/TSL | Low (overkill for 5.5 h) | 426 script files in an example gallery and a `bin/` CLI. Skills are short Markdown. |
| **lhlGitHub/threejs-architecture-effects** | 744 / 2026-09-22 / 2026-09-22 | MIT | "Self-assembling" Chinese-pavilion construction animations; Vite/React/Three starter | Idea only. Its rule "assembly plan: foundations → frame → … → ornament" is the right order for our progressive reveal (base → shoulder → upper arm → … → jaw). | `scripts/scaffold.mjs` copies a starter and "refuses an existing destination". States "No API keys". |
| **AirsupHQ/machine-skill** | 721 / 2026-10-12 / 2026-10-13 | MIT | One line becomes a single-HTML interactive machine sim plus a film. Its lab kit API takes `explode: [dx,dy,dz]`, `xray: 'shell'`, `cut: {...}` and `lab.label(obj, 'HP turbine', {value})`, with "one hero readout, one slider". | Pattern reference (good API vocabulary) | Output loads **three 0.170 from jsDelivr**, which breaks offline. Has record/shot scripts. |
| **viettranx/3dviz-pro-max** | 1,440 / 2026-09-10 / 2026-09-11 | MIT | Generic "3D scene worth exploring" (Three.js or Blender) with capture scripts | Low | Runs `python3 scripts/capture.py`. 2,112 files, one push. |
| **zeative/motion-educator** | 76 / 2026-11-14 / 2026-11-17 | MIT | Film engine for teardown-style *videos* (GSAP, shader stage) | Low. It makes films, not an interactive viewer. | Tells the agent to "build to the finished film without asking about any step". Optional voice generation "with an API key". |
| **cesartevisual/threejs-skills** | 25 / 2026-09-10 / 2026-09-10 | MIT | 24 skills of about 22–24 lines each | Low (thin) | Clean, but little content |
| **skinnye/3d-web-pack** | 10 / 2026-06-14 / 2026-06-14 | MIT | Next.js "award-style" scaffold, 4 skills + 6 agents | Low (Next.js, scroll sites) | Runs `npx create-next-app@latest` and installs `@studio-freight/lenis` (renamed upstream) |
| **freshtechbro/claudedesignskills** | 1,412 / ? / **2025-11-20** | MIT | 22 skills across 27 plugins (three, r3f, babylon, GSAP...) | Low (a year stale) | 1,027 files, Python generator scripts and `.zip` bundles |
| **lizh54331/threejs-exploded-view** | 0 / ? / 2026-11-17 | MIT | Chinese-language "photo → exploded page" skill | Idea only (labels avoid overlap; parts list linked to highlight) | Ships `.bat` launcher and test scripts; 0 stars |
| **wheresryan22/anatomy** | 28,274 / 2026-10-08 / 2026-10-18 | MIT | Isometric **SVG** machine figures with exploded views (11 assemblies with staggered springs), a React kit (`kit/react/draw.tsx`) and an audit that proves no part passes through another | Medium, **for the ESP32 2D demo only**. A stunning alternative to boxes-and-arrows, but a "Figure" is 40–80 parts and needs audit rounds, so treat it as a stretch goal. | "No API keys and nothing to npm install" (Node built-ins only). Runs local build/capture/audit scripts with headless Chrome. Tells the agent to "build it without asking" about size. |

**Skills directly on exploded views:** Moh4696 `exploded-view`, AirsupHQ `machine` and wheresryan22 `anatomy` are the three worth reading. Only the first maps cleanly onto an r3f component.

### 1.3 Design-polish skills

Several star counts here (119k, 114k, 98k, 58k within months of creation) look inflated. These verdicts come from the files, not the stars.

| Repo | ★ / created / push | License | What it does | Relevance | Safety read |
|---|---|---|---|---|---|
| **Anthropic `frontend-design`** | see 1.1 | Apache-2.0 | Design-lead brief: token plan (4–6 hex palette, type, layout) → self-review against AI defaults → build → critique with screenshots | **High** for the panel, offer cards and cart | Instructions only |
| **Leonxlnx/taste-skill** | 119,003 / 2026-02-19 / 2026-11-08 | MIT | "tasteskill 2.5.1": company *websites* at "figma.com and x.ai" level; checker and finish gate in a real browser | Low-medium (marketing sites, not app UI) | **Frontmatter registers a `Stop` hook** that runs `scripts/gate.mjs` (timeout 600 s) every time the agent stops. Needs Node 22 + Chrome. 1,663 files, 157 scripts, `install.sh`. |
| **pbakaus/impeccable** | 113,612 / 2025-11-16 / 2026-11-19 | Apache-2.0 | Design vocabulary commands (`polish`, `bolder`, `critique`, `audit`) and a slop detector CLI | Medium (a good end-of-day `/impeccable critique`) | `allowed-tools: Bash(npx impeccable *)` (pre-approved npm code). An **optional hook auto-runs the detector after every UI file edit** (`/impeccable hooks on`). Setup is `npx impeccable install`. 4,943 files. |
| **Nutlope/hallmark** | 58,170 / 2026-04-27 / 2026-11-11 | MIT | "Design skill for websites and new pages"; themes, `sloplint.mjs`, gates | Medium for a landing or pitch page; not for the 3D view | Runs local `node scripts/sloplint.mjs`. Optional `install-hook.mjs` adds an edit-time check. "No follow-up questions": it infers missing choices. |
| **AThevon/genjutsu** | 822 / 2026-03-28 / 2026-11-16 | MIT (GitHub shows NOASSERTION because `LICENSE` appends a third-party MIT notice for vendored `ui-ux-pro-max`) | 20 creative-coding skills: Canvas, CSS motion, Compose/SwiftUI, design systems | Low | **The recommended install pulls from a custom domain** (`npx skills add https://genjutsu.athevon.dev -g`), not GitHub, so what you get may differ from the repo |
| **tt-a1i/archify** (diagrams) | 98,124 / 2026-04-15 / 2026-11-20 | Apache-2.0 | Validated architecture, dataflow and sequence diagrams as **standalone HTML** | Low for the in-app ESP32 board (React Flow integrates better). OK for a pitch slide showing the data flow. | Runs `node bin/archify.mjs finalize`, which **includes an update check** (network). 488 scripts. |
| op7418/* | skipped as instructed | **AGPL-3.0** | | | |

### 1.4 codepawl (and what "67.js" is)

The user's words, "codepawl 67.js hflivrary assets", read best as **codepawl's 67.js engine and its Hugging Face asset library**. The GitHub org `codepawl` was created Mar 2026 and describes itself as a 3D studio in Vietnam.

- **67.js is real.** It is codepawl's 3D engine, **renamed Crucible**. `github.com/codepawl/67.js` and `anxuanng/67.js` both redirect to `codepawl/crucible`. npm `@codepawlhq/67js@0.19.0` is deprecated ("Renamed to @codepawlhq/crucible"), and `@codepawlhq/crucible@0.21.0` was published 2026-11-14. An unrelated older description of 67.js as a "code explainer library" (everydev.ai) is stale.
- **codepawl/crucible**: 823★, created 2026-10-08, push 2026-11-20, MIT. It is its **own WebGL2 engine with a path tracer and an MCP server, not a three.js wrapper**. The agent guide (`crucible.codepawl.com/llms.txt`) mentions no React or r3f integration, picking or outline. A `three-compat` addon is "not on npm yet". It is pre-1.0 with a new minor "about once a week" that can change the API. One author made about 5,200 of roughly 5,240 commits, and 168 issues are open. The README tells you to paste a prompt into your agent: "Read https://crucible.codepawl.com/llms.txt first and follow it". That is remote instructions aimed at agents. **Verdict: a distraction tomorrow.** It cannot host urdf-loader, drei or our r3f scene, and it would replace the renderer on the day.
- **codepawl/vinyl-67js**: 0★, MIT. Three record players "drawn with 67js" (live at vinyl.codepawl.com). It confirms 67js is the engine; the built library folder isn't in the repo.
- **codepawl/creator-generalist**: 336★, created 2026-11-06, push 2026-11-19, MIT. 5 plugins (3d-generalist, 2d-generalist, game-generalist, watch-video, design-sound) with about 20 skills: `3d-generalist`, `3dg`, `visualize-in-3d`, `use-3d-software`, `model-characters`, `rig-characters`, `sculpt-models`, `animate-characters`, `make-pixel-splats`, `build-house-from-plan`, `build-minecraft-model-from-image`, plus 2D, video and sound skills.
  - Install: `claude plugin marketplace add codepawl/creator-generalist` → `claude plugin install 3d-generalist@creator-generalist`. `INSTALL.md` is written "for an AI agent" and then asks it to run `check_vox_toolchain.py` and offer to install Blender, FFmpeg, Node and Python.
  - Relevance: `visualize-in-3d` has a "how a thing works → lesson app" shape and a "one object cut open or exploded" shape. It is built around Blender, films and Crucible, and it writes plan files and a lessons file, so it would take over the session. **Low for tomorrow.**
  - Safety: the SKILL.md files I read (`3d-generalist`, `3dg`, `visualize-in-3d`, `use-3d-software`) contain no rule-override text. `visualize-in-3d` asks before downloads ("get the user's OK first"), except "if the user approved downloads ahead or is away" it takes open-licensed files on its own. Elsewhere in the repo: `fetch_objaverse.py`, `fetch_images.py` and `fetch_assets.py` fetch remote assets. `design-sound` reads `ELEVENLABS_API_KEY` and uses fal (paid APIs). `learning.md` records user corrections "without asking first", which is benign memory-keeping.
- **codepawl/3d-builds**: 1★, MIT. Source, prompts and design notes for about 28 pieces, "most built by Claude Opus 5.5". Two are relevant:
  - `works/2026-10-23-arduino-breadboard` ("Learn Arduino in 3D"). An **r3f app using our exact stack** (three 0.186.1, Fiber 9.8.2, drei 10.7.9, postprocessing 3.2.1 + n8ao 2.0.1, React 19.3.1, Vite 8). The board and parts are **built in code from documented dimensions** (no external model, so no license issue). Parts are "carried from a tray into the exact holes", which is our off-model tray in reverse, and current flow sits behind an off-by-default "Show current" toggle.
  - `works/2026-10-11-machine-anatomy`. SVG, not three. "The exploded view moves each assembly along its real removal axis", with an audit that "no part passes through another", plus a numbered legend, a live readout and a trace strip that narrates events.
- **codepawl/asset-gate**: 3★, created 2026-11-12, MIT. An MCP server that searches about 75.6k free assets (17 GLB packs that codepawl re-hosts on Hugging Face, plus Poly Haven, ambientCG and others) and returns licence and credit lines.
  - No keys needed.
  - Hosted mode (`claude mcp add --transport http free-3d-assets https://assets.codepawl.com/mcp`) sends your queries to a third party. Local mode (`npx -y github:codepawl/asset-gate`) runs **unpinned code from GitHub HEAD**. Its `generate_asset` tool queues TRELLIS.2 jobs that run on "the owner's PC".
  - The licence claims I spot-checked match the upstream source (ABO is CC BY 4.0 per Amazon's page), but the packs are mirrors made by a two-week-old org.
  - It has no ESP32, e-paper or BME280-class electronics that I could see. **Verdict: don't run it.** Its plain HTTP search (`/api/search?q=`) is fine to browse; take assets from the origin (Poly Haven, Adafruit) and keep their licence text.
- codepawl/viz3d: archived (moved into creator-generalist); skipped.

### 1.5 Text aimed at AI agents found during research (treated as data; none was followed)

- `threejs.org/docs/llms.txt` has "Instructions for Large Language Models" (use import maps; WebGLRenderer by default; TSL for custom shaders). Benign.
- Crucible README: "Read https://crucible.codepawl.com/llms.txt first and follow it." `INSTALL.md` in creator-generalist: "This file is for an AI agent."
- shadcn skill: `` !`npx shadcn@latest info --json` `` runs on load. taste-skill: `Stop` hook. impeccable: auto-run hook. archify: update check. webapp-testing: "DO NOT read the source until you try running the script."
- `pmndrs/examples` has an `AGENTS.md` (repo triage rules for contributors) and a vendored shadcn skill. Benign.
- human-atlas exposes "WebMCP tools" for browser agents. Benign.
- **None told the agent to ignore user or system rules.**

### 1.6 Install these (ranked, for 4 people on Claude Code)

Commit the chosen skill folders to the repo's `.claude/skills/` so the whole team gets the same pinned copy. The licenses below allow it. Review the diff before committing.

1. **CloudAI-X/threejs-skills** (MIT). Copy `skills/threejs-react-three-fiber`, `threejs-interaction`, `threejs-lighting`, `threejs-postprocessing`, `threejs-loaders`, `threejs-performance` and `threejs-asset-pipeline` into `.claude/skills/`. Equivalent: `npx skills add cloudai-x/threejs-skills` (vercel-labs/skills CLI, MIT, v1.9.0).
2. **Anthropic frontend-design** (Apache-2.0): `/plugin install frontend-design@claude-plugins-official`. This one is per-user; each person runs it.
3. **Moh4696 `exploded-view`** only (MIT): `npx skills add Moh4696/open-3d-skills --skill exploded-view`, or copy `skills/exploded-view/` into `.claude/skills/`. In the prompt: "port Exploder, Labels, Xray, Section to r3f components; no CDN import map".
4. **shadcn** (MIT, official) only if the team adds components through the CLI: `npx skills add shadcn-ui/ui --skill shadcn` **[unverified exact form; `github.com/shadcn/ui` redirects to `shadcn-ui/ui`, and pmndrs/examples' `skills-lock.json` records it as source `shadcn/ui`, path `skills/shadcn/SKILL.md`]**. Accept that it runs `npx shadcn@latest` (it needs network; do this tonight, not on venue Wi-Fi).
5. *(Optional, for the ESP32 2D person only)* **wheresryan22/anatomy** (MIT): `npx skills add wheresryan22/anatomy -g -a claude-code`. Only if React Flow plus the CSS stack is done by 14:30.

### 1.7 Don't install (reasons)

- **taste-skill**: a 600 s Stop hook on every stop, and aimed at marketing sites.
- **impeccable**: a hook on every UI edit plus a pre-approved `npx`. Fine after the event; too much churn on the day.
- **creator-generalist**: Blender and film oriented, remote fetch scripts, paid-API keys for sound.
- **Crucible plugin / MCP**: replaces the renderer; pre-1.0.
- **asset-gate**: unpinned remote code or a third-party host.
- **genjutsu**: installs from a custom domain.
- **archify**: standalone HTML and an update check.
- **emalorenzo**: no license, zips, CDN import map, stale.
- **freshtechbro**: a year stale, scripts and zips.
- **EnzeD**: no license, so it can't be committed. Local use is OK.
- **Impertio**: its optimizer advice merges parts.
- **scottstts**, **3dviz-pro-max**, **motion-educator**, **skinnye**, **cesartevisual**, **lhlGitHub**, **lizh54331**: off-target, thin, film-only or unvetted.
- **web-artifacts-builder**: React 18, artifact-only, scripts and a tarball.
- **op7418/***: AGPL.

---

## 2. "Split into parts" / exploded-view implementations

| Project | URL | ★ / push | License | What it gives us | Library or inspiration? | Min | Risk |
|---|---|---|---|---|---|---|---|
| **urdf-loader** (gkjohnson/urdf-loaders) | github.com/gkjohnson/urdf-loaders | 822 / 2026-10-31 | Apache-2.0 | Our loader. `loadMeshCb` swaps STL for GLB, `setJointValue`, `packages` map. Live example: gkjohnson.github.io/urdf-loaders/javascript/example/bundle/index.html | **Library (already chosen)** | n/a | three.js propagates `visible` down the kinematic chain, so hiding a link hides every child link (see the anatomy note in 3). Flatten the visuals first. |
| **KitSmith SO-101 assembly guide** | github.com/Guillaume-Georges/so101-assembly-guide (site: kitsmith.dev/so101/; HF Space `KitSmith/so101-assembly-guide` is an iframe wrapper) | 1 / 2026-09-27 | MIT (code and data) | **The same robot in r3f**: one GLB per part + `placements.json`, ghosted future parts, outlined current part, screws backing out along their axis on explode, camera framed when every part has loaded ("Bounds would fit before world matrices update"), `frameloop` on demand + `invalidate()` | **Reference code** (copying under MIT is allowed with the notice) | 20 to read | It's an Astro island with its own data model. Lift techniques, not the file. |
| **MakerWorks SO-101 exploded view** | makerworkslab.in/ajayummadi/projects/lerobot-so-101/ (HF Space `ummadiajay/so101-3d-exploded-view`, Apache-2.0 card, but it's an iframe) | 0 (Space) | Space card Apache-2.0; page code not published | "Seven stages, one arm": numbered stages (Base … Moving jaw); hovering a part, its marker or its name highlights the stage; Assembled / Exploded / Auto-rotate | Inspiration | 0 | No source |
| **Moh4696 `exploded-view` skill** | github.com/Moh4696/open-3d-skills | 436 / 2026-11-09 | MIT | `Exploder` (staged: stage *n* starts when *n−1* is half done), `Labels` (two screen-edge columns, keep anchor order, push apart, leader lines), `Xray` (shells to 14% opacity, no depth write), `Section` (clips shells only, double-sided), `Picker`, `autoDistance` (camera pulls back as it explodes) | **Pattern + small code to port** | 45 | Vanilla three r169 |
| **three-cad-viewer** | github.com/bernhard-42/three-cad-viewer · live: bernhard-42.github.io/three-cad-viewer/example.html (loads) | 397 / 2026-11-18 | MIT (npm 5.1.3) | Tree navigation, **explode (`x`)**, transparent (`t`), **clipping with stencil caps (`C`)**, shift-click isolate, zebra and studio modes, measure | Inspiration (it is a library, but with its own UI and `Shapes` data format, not r3f) | 0 | Replaces our scene if used |
| **Online3DViewer / 3dviewer.net** | github.com/kovacsv/Online3DViewer | 3,774 / 2026-06-24 | MIT (STEP import via occt-import-js, **LGPL-2.1**) | Model tree; imports STEP/IGES/STL; **exports GLB**; "the entire process happens in your browser" | **Tool** (STEP → GLB converter); inspiration for the tree | 10 per model | Large STEP files can be slow **[unverified]** |
| **xeokit-sdk** | github.com/xeokit/xeokit-sdk · xeokit.io | 966 / 2026-11-18 | **AGPL-3.0** (commercial license from Creoox) | X-ray, highlight, selection, colorize, section planes, tree views | **Inspiration only.** AGPL would force our whole app to AGPL. | 0 | License |
| **chili3d** | github.com/xiangechen/chili3d | 5,013 / 2026-11-18 | **AGPL-3.0** | Browser CAD app; explode compound objects | Inspiration only | 0 | License |
| **ThatOpen engine_components** | github.com/ThatOpen/engine_components | 749 / 2026-11-08 | MIT | BIM (IFC) components for three.js; clipper, highlighter and hider **[unverified: docs not opened]** | Inspiration | 0 | IFC-centric |
| **Smithsonian Voyager** | github.com/Smithsonian/dpo-voyager · smithsonian.github.io/dpo-voyager/explorer/overview/ | 210 / 2026-11-19 | Apache-2.0 | "Fully customizable 3D annotations", guided tours, measurement and cutting tools, a reader for articles; `<voyager-explorer>` web component with an "offline use" page | Inspiration (heavy as a library) | 0 | Its docs load fonts from jsDelivr and the script from 3d-api.si.edu |
| **AirsupHQ machine-skill kit** | github.com/AirsupHQ/machine-skill | 721 / 2026-10-13 | MIT | Explode vectors per part ("outer shells furthest, core in place"), `xray: 'shell'` (glass with fine edges), cutaway with solid section faces, labels with live values | Pattern | 0 | CDN three |
| **getactuators / actuatorlist PR #130 "3D explode kit"** | github.com/Miyamura80/getactuators/pull/130 (repo now `Miyamura80/actuatorlist`) | 0 / 2026-11-19 | MIT | `ExplodeScene` with a scrub bar and part stepper; selection glows the part and dims the rest | Pattern **[unverified: from search snippet, PR not opened]** | 0 | Small repo |
| three.js examples | threejs.org/examples/#webgl_clipping_stencil · #webgl_postprocessing_outline (files exist in mrdoob/three.js, 118,986★) | push 2026-11-20 | MIT | Section caps with the stencil buffer; OutlinePass reference | Reference | 0 | n/a |
| pmndrs examples | github.com/pmndrs/examples (135★, push 2026-10-22, MIT): `faucets-select-highlight`, `selective-outlines`, `bounds-and-makedefault`, `html-annotations`, `wireframes`, `edgesgeometry`, `shoe-configurator` | n/a | MIT | Working r3f code for each behaviour we need (details in 7) | **Copyable patterns** | 10 each | n/a |
| Small exploded-view repos | Spoon221/exploded-niva-concept (MIT, 0★), AlexZhangji/turbine-explorer (MIT, 5★), Luchocrat/explode-scroll-demo (**no license**), shivaylamba/explode-anything (**no license**) | 2026 | as listed | Scroll-driven explode examples | Inspiration (don't copy the unlicensed ones) | 0 | n/a |
| CodePen | codepen.io/jh3y/pen/ZEOzNbm ("3D Book with Exploded View"), codepen.io/jh3y/pen/QWELPQg ("Cube – Exploded View"), codepen.io/ryan_labar/pen/vLNBYw ("Exploded view GSAP") | n/a | CodePen: "Public pens are automatically MIT licensed" (blog.codepen.io/documentation/licensing/) | **CSS 3D** exploded layers driven by a GUI slider: the trick for the ESP32 layered stack | Inspiration; rewrite, don't paste | 0 | **[unverified: CodePen returned 403 to automated fetch; titles from search results]** |
| Codrops "Exploding 3D Objects with Three.js" (Yuriy Artyukh, 2019) | tympanus.net/codrops/2019/03/26/exploding-3d-objects-with-three-js/ | n/a | n/a | Per-triangle shader explosion (style, not part-based) | Inspiration | 0 | **[unverified: 403 to fetch]** |

No three.js or r3f exploded-view pen turned up on CodePen, and none turned up on CodeSandbox or StackBlitz either. The pmndrs examples and the repos above are better sources.

**How to do it on the SO-101 (load-bearing details):**

- The URDF has **17 visual meshes on 7 links** (11 printed parts + **6 STS3215 servos**: 5 × `sts3215_03a_v1`, 1 × `no_horn`). There are 13 unique STLs, about 16.1 MB in total (≈ 320k triangles; ≈ 400k rendered).
- Colours come from the URDF: printed parts `rgba(1.0, 0.82, 0.12)` (yellow), servos `0.1` grey.
- Once the URDF has loaded:
  - Give each visual mesh its own cloned material (a shared material changes every part at once; nqwrc and Moh4696 both hit this).
  - `parts.attach(mesh)` it into one flat group, which keeps world transforms and stops `visible` propagating.
  - Store `home = position.clone()` and a direction. Use a hand-set vector per link; the fallback is `normalize(center - assemblyCenter)`.
  - Each frame: `easing.damp3(mesh.position, home + dir * dist * stageT(i), 0.25, dt)`.
- Don't convert the servos to `InstancedMesh`. Per-part highlight needs separate meshes.
- Keep `frameloop="demand"` and call `invalidate()` while anything is damping.

---

## 3. Anatomy-style viewers: patterns worth copying

| Source | URL | ★ / push | License | Notes |
|---|---|---|---|---|
| **ashemag/human-atlas** | github.com/ashemag/human-atlas · demo human-atlas-seven.vercel.app (**HTTP 503 on two tries during this check**) | 4,606 / 2026-09-06 | Code MIT; data BodyParts3D 4.0 **CC BY 4.0** | React + three + shadcn. 2,234 selectable meshes, 15 systems, search, isolate, and **"move from assembled anatomy to a spaced inventory of every visible piece"**. Per-structure GPU textures drive visibility and selection. |
| **nqwrc/3d-anatomy** | github.com/nqwrc/3d-anatomy (demo nqwrc.github.io/3d-anatomy, not opened) | 6 / 2026-09-21 | Code NOASSERTION; data **CC BY-NC-SA 4.0** (inner ear **NC-SA**, kidney **NC**) | Key lessons: 868 nested structures were **detached to the root so hiding a parent stops hiding unrelated children**; materials stay shared until one mesh changes, then that one is cloned and restored |
| Z-Anatomy | github.com/LluisV/Z-Anatomy (417★, push 2024-12-25, Unity) · github.com/Z-Anatomy/Models-of-human-anatomy (313★) | | **CC BY-SA 4.0**; some components **NC** | Asset licenses are unusable for us. The site z-anatomy.com showed only "Loading". |
| slorksmo/Human-Atlas | github.com/slorksmo/Human-Atlas | 17 / 2026-11-18 | MIT code, CC BY data **[unverified: README not opened]** | 3,400+ structures, RTL support |
| ArianArsenal/anatomy-explorer | github.com/ArianArsenal/anatomy-explorer | 2 / 2026-10-30 | **none** | State module: layers, selection, isolation, highlights, slice, explode **[from search snippet]** |
| Zygote Body (proprietary) | zygotebody.com | n/a | n/a | Opacity slider "to reveal layers"; Ctrl/Cmd-click to "quickly hide"; "Unhide All"; Shift-click to pin multiple; search; "Zoom to" |
| BioDigital Human Studio (proprietary) | biodigital.com/product/human-studio | n/a | n/a | "hide, fade, or emphasize structures"; labels "with sequential, circular, or floating layouts"; multi-step tours; quizzes |

**Patterns to copy (no assets), mapped to our viewer:**

1. **Select → panel; isolate → ghost the rest.** Click selects and opens the offers panel. An "Isolate" button or double-click sets every other part to ghost (`opacity 0.1`, `depthWrite false`, desaturated). Esc restores. *(BioDigital fade, human-atlas isolate, KitSmith ghosting.)*
2. **Quick hide + "Unhide all."** Ctrl-click hides a part, and an always-visible chip reads "2 hidden · Unhide all". *(Zygote)*
3. **Multi-select pins.** Shift-click adds parts to a selection, so "cart these 3". *(Zygote)*
4. **Layers / "peel".** Toggle chips for Printed parts / Servos / Electronics / Fasteners, plus one opacity slider that fades the printed shells to show the servo skeleton. *(Zygote opacity slider, human-atlas systems, Moh4696 x-ray shells)*
5. **Search with fly-to.** A shadcn `Command` palette (⌘K) over part names: picking one flies the camera with `fitToBox` and pulses the part. *(Zygote, human-atlas)*
6. **Part tree / list with eye icons and two-way hover.** Hover the row and the mesh lights; hover the mesh and the row lights and scrolls into view. *(three-cad-viewer tree, Zygote hierarchy)*
7. **Labels with leader lines**, either in two columns at the screen edges or "floating". Hide labels while the camera moves, and on narrow screens show only the hovered part's name. *(BioDigital label layouts, Moh4696 Labels)*
8. **Inventory / knolling.** One button flies every part into a tidy grid on the floor, each with its best price. This is *the* Build-to-Cart hook: the robot "becomes" the cart. *(human-atlas spaced inventory)*
9. **Guided steps / tour.** "Step 1 of 7: Base" walks through in assembly order, highlighting the current part and ghosting the future ones. *(KitSmith, BioDigital tours, Voyager tours, MakerWorks seven stages)*
10. **Section cut** for the printed shells only, keeping the servos whole inside. *(Voyager cutting tool, three-cad-viewer clip, three.js stencil example)*
11. **Flatten the hierarchy** before isolating or hiding, and **clone materials per part**. *(nqwrc)*

---

## 4. Visual polish libraries for r3f

Fiber 9 needs React 19, and every entry here was checked against Fiber 9.8.2 / React 19.3.1 peers.

| Library | URL | ★ / push | License | Adds visually | Min | React 19 / Fiber 9 | Gotchas |
|---|---|---|---|---|---|---|---|
| **@react-three/fiber 9.8.2** | github.com/pmndrs/react-three-fiber | 33,841 / 2026-10-21 | MIT | n/a | n/a | peer `react >=19 <19.4` | Don't take React 19.4 when it ships |
| **@react-three/drei 10.7.9** | github.com/pmndrs/drei | 10,179 / 2026-11-17 | MIT | `Bounds`, `CameraControls`, `ContactShadows`, `AccumulativeShadows` + `RandomizedLight`, `Html`, `Edges`, `Outlines`, `Wireframe`, `Environment` + `Lightformer`, `Float`, `PresentationControls`, `Bvh`, `Select`, `useCursor` (all have doc pages) | 5–20 each | peer `react ^19`, `fiber ^9` | **CDN traps:** `Environment preset` → raw.githack.com; `useGLTF` Draco → gstatic 1.5.5 (pass `useGLTF(url, false)` or use meshopt); `MatcapTexture` / `NormalTexture` → jsDelivr; `Text` → Google Fonts (pass `font="/fonts/x.woff"`). `Bounds` can fit before matrices update (KitSmith note). `Outlines` takes `thickness`, `screenspace`, `angle` (crease), `color`. |
| **camera-controls 3.1.2** (inside drei `CameraControls`) | github.com/yomotsu/camera-controls | 2,453 / 2026-10-21 | MIT | `fitToBox(box3OrMesh, true, {paddingTop…})`, `setLookAt(px,py,pz, tx,ty,tz, true)`, `smoothTime` 0.25 | 15 | via drei | drei 10.5+ moved to camera-controls v3 |
| **@react-three/postprocessing 3.2.2** | github.com/pmndrs/react-postprocessing | 1,672 / 2026-10-21 | MIT | `N8AO` (in `passes/`), `SMAA`, `Bloom`/`SelectiveBloom`, `Outline` with `<Selection>`/`<Select>` (3.2.0 added `exclude`), `ToneMapping`, `Vignette` | 20 | peer `react ^19`, `fiber >=9.7`, `postprocessing ^6.36` | `Outline` **requires `<EffectComposer autoClear={false}>`**. 3.2.1 fixed N8AO's camera/scene; 3.1.3 fixed N8AO after a DPR change. Clamp `dpr={[1,1.5]}` on integrated GPUs at projector 1080p. |
| postprocessing 6.39.6 | github.com/pmndrs/postprocessing | 2,986 / 2026-11-01 | Zlib | n/a | n/a | peer `three >=0.168 <0.188` | Pin three |
| n8ao 2.1.0 | github.com/N8python/n8ao | 519 / 2026-11-15 | CC0-1.0 (GitHub) / ISC (npm) | Screen-space AO, cleaner than SSAO | (in the row above) | via react-postprocessing | Use `halfRes` on weak GPUs |
| **three-mesh-bvh 0.9.18** (drei `<Bvh>`) | github.com/gkjohnson/three-mesh-bvh | 3,579 / 2026-11-19 | MIT | Fast raycasting; `firstHitOnly` | 2 | peer `three >=0.159` | Wrap only the robot group |
| **maath 0.10.8** | github.com/pmndrs/maath (now `pmndrs/math`) | 1,345 / 2026-11-16 | MIT | `easing.damp`, `damp3`, `dampC`, `dampE` | 10 | n/a | Call `invalidate()` while damping in demand mode |
| @react-spring/three 10.1.2 | github.com/pmndrs/react-spring | 29,319 / 2026-11-01 | MIT | Springy pop when a part is "found" | 15 | peer `react ^19`, `fiber >=6` | One more mental model; maath covers most of it |
| motion 14.14.0 | github.com/motiondivision/motion | 35,380 / 2026-11-19 | MIT | 2D UI only | n/a | n/a | **`framer-motion-3d` is deprecated on npm** (peer Fiber 8.2.2) |
| Theatre.js 0.7.2 | github.com/theatre-js/theatre | 13,069 / **2024-08-14** | core Apache-2.0, **studio AGPL-3.0** | Keyframed camera moves | n/a | `@theatre/r3f` peer **Fiber ^8.13.6** | **Don't use** |
| GSAP 3.15.1 | github.com/greensock/GSAP | 30,962 / 2026-11-04 | "Standard no-charge license" (Webflow); not OSI | Timelines | 20 | n/a | Free for commercial use; bans tools that compete with Webflow's animation builder. Unneeded given `CameraControls` transitions. |
| leva 0.10.1 | github.com/pmndrs/leva | 6,277 / 2025-11-09 | MIT | Live tuning of AO, outline and explode distance | 10 | peer `react ^18 \|\| ^19` | Issue #552: controls inside `<Canvas>` don't render under StrictMode; call `useControls` outside the Canvas; hide in demo |
| r3f-perf 7.2.3 | github.com/utsuboco/r3f-perf | 782 / **2024-12-20** | MIT | FPS / draw-call overlay | 2 | peer `fiber >=8` | Bundles `roboto.woff` locally (offline-safe). Issue #67: GPU sensor fails in StrictMode. Alternative: drei `<StatsGl>` (stats-gl 4.2.3 MIT). |
| three-custom-shader-material 6.4.0 | github.com/FarazzShaikh/THREE-CustomShaderMaterial | 1,371 / 2025-10-12 | MIT | Patch `MeshStandardMaterial` with `csm_DiffuseColor`, `csm_Emissive`, `csm_FragColor`, so a **Y-sweep dissolve** (noise threshold + glowing edge) drives the reveal | 45 | peer `fiber >=8` | Bump mapping removed in 6.4.0 |
| troika-three-text 0.53.1 (drei `Text`) | github.com/protectwise/troika | 1,991 / 2026-11-02 | MIT | SDF 3D text | 10 | n/a | Default font from the **Google Fonts CDN**; unicode fallback from jsDelivr |
| zustand 5.1.0 | github.com/pmndrs/zustand | 58,959 / 2026-11-06 | MIT | Shared `hovered / selected / isolated / colourMode / explode` store for canvas, list and panel | 10 | peer `react >=18` | Select slices to avoid re-rendering the Canvas |
| three-gpu-pathtracer 0.0.28 | github.com/gkjohnson/three-gpu-pathtracer | 2,060 / 2026-11-20 | MIT | Path-traced "hero still" | n/a | peer `three >=0.187` | Skip tomorrow |
| three-edge-projection | github.com/gkjohnson/three-edge-projection | 361 / 2026-10-29 | MIT | Technical line drawings | n/a | **not on npm** | Skip |

**Wireframe → solid reveal, three ways:**
- (a) `Edges` (grey, `threshold={25}`) with fill opacity 0.05, which damps to a solid status colour with a 150 ms emissive flash. 20 min, zero risk.
- (b) drei `Wireframe` (shader, `fill`/`stroke`/`thickness`, works on loaded GLTF meshes as the pmndrs `wireframes` car example shows). 20 min.
- (c) CSM dissolve sweep. 45 min.

**Labels, three ways:**
- (1) drei `Html` at an anchor with `center` and `occlude`. Simple, but 17 overlapping labels get messy.
- (2) **Two-column screen-edge labels with SVG leader lines** (Moh4696): project anchors each frame and write to the DOM through refs, not React state. Best for projectors.
- (3) drei `QuadraticBezierLine` leader + `Html` at its end.

**Projector notes:**
- `lineBasicMaterial` is 1 px on Windows/ANGLE; use `Edges`/`Line` with `linewidth={2–3}`.
- Use `Outlines screenspace`.
- Labels at least 18 px.
- Pick a colour-blind-safe status palette (blue / orange / grey / red), each with an icon.

---

## 5. 3D assets with clear licenses

### 5.1 Lighting (self-hosted, offline)

| Asset | URL | License | Size | Note |
|---|---|---|---|---|
| **RoomEnvironment** (procedural) | three/examples/jsm/environments/RoomEnvironment.js | MIT | 0 | `pmrem.fromScene(new RoomEnvironment(), 0.04).texture` → `scene.environment`. KitSmith and Moh4696 both use it. |
| **studio_small_03** | polyhaven.com/a/studio_small_03 | **CC0** | 1k HDR 1.69 MB (1k EXR 1.47 MB; 2k HDR 6.67 MB) | The file behind drei `preset="studio"` |
| studio_small_09 | polyhaven.com/a/studio_small_09 | CC0 | 1k HDR 1.62 MB | Author Sergej Majboroda |
| brown_photostudio_02 | polyhaven.com/a/brown_photostudio_02 | CC0 | 1k HDR 1.65 MB | Warmer |
| photo_studio_01 | polyhaven.com/a/photo_studio_01 | CC0 | 1k HDR 1.60 MB | |
| studio_small_08 | polyhaven.com/a/studio_small_08 | CC0 | 1k HDR 1.51 MB | |
| drei `Lightformer` inside `<Environment>` | drei.docs.pmnd.rs/staging/lightformer | MIT | 0 | Custom softboxes baked into reflections (WebGL is fine; the CloudAI-X skill notes black reflections on the WebGPU fallback) |

Poly Haven license page: "You can use our assets for any purpose", with no credit needed and redistribution allowed. Its site ToS bans scraping, so download the files manually. The `polyhaven.com` site code is AGPL, which doesn't matter for the assets. `pmndrs/drei-assets` (the CDN source) has **no license file**; get the HDRs from Poly Haven instead.

### 5.2 Materials

**ambientCG**: "All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License" (docs.ambientcg.com/license/). Credit is not required; the file can live in the repo. For a printed-PLA look, plain `meshStandardMaterial` with `roughness 0.6` + AO is enough, and textures aren't needed.

### 5.3 The SO-101 itself

`github.com/TheRobotStudio/SO-ARM100` (8,177★, push 2026-10-06, **Apache-2.0**). `Simulation/SO101/so101_new_calib.urdf` with 13 STLs in `assets/`. The README says the meshes use relative paths, not `package://`. Apache-2.0 means keeping the LICENSE and stating that the meshes were converted. A mirror exists at `huggingface.co/datasets/lerobot/robot-urdfs` (`so101/`, Apache-2.0 for SO-101).

### 5.4 Electronics for the ESP32 demo

| Source | URL | ★ / push | License | Contents | Verdict |
|---|---|---|---|---|---|
| **Adafruit_CAD_Parts** | github.com/adafruit/Adafruit_CAD_Parts | 1,546 / 2026-11-05 | **MIT** (LICENSE checked) | `3405 ESP32 Feather HUZZAH` (STEP 2.8 MB, STL 3.0 MB, f3d), `2652 Adafruit BME280` (STEP/STL), `1578 500mAh battery` (STEP/f3d), `4778 2.9 inch E-Ink Featherwing`, `6366 2.13in Tri-Color eInk`, `4196 1.54in eink display`, `5323 Feather ESP32-S3`, `5400 ESP32 Feather V2`, micro servos | **Use.** These are stand-ins for FireBeetle / Waveshare; label them as such. |
| Espressif KiCad libraries | github.com/espressif/kicad-libraries | 1,439 / 2026-11-16 | **CC-BY-SA 4.0** + KiCad design exception | `ESP32-WROOM-32E.STEP/.wrl` (the module on the FireBeetle 2 ESP32-E) | **SA flag.** Committing the model file (or a GLB made from it) makes that file CC-BY-SA 4.0 with attribution. Our code is unaffected. |
| KiCad official 3D library | kicad.org/libraries/license/ | n/a | **CC-BY-SA 4.0** + exception that covers designs and "generated files" | Generic packages (headers, JST, USB-C) | **SA flag** for redistributing the model files; the exception covers your designs, not re-hosting the library |
| Fritzing parts | github.com/fritzing/fritzing-parts | 629 / 2026-08-12 | **CC BY-SA 3.0** ("publish your works under the same license") | Breadboard and schematic SVGs | **SA flag** for any SVG you use in the 2D diagram; credit "created with Fritzing" |
| DFRobot FireBeetle 2 ESP32-E | wiki.dfrobot.com/FireBeetle_Board_ESP32_E_SKU_DFR0654 | n/a | **None found** | **[unverified]** No STEP download confirmed | **Don't redistribute**; build it in code from the dimension drawing instead (the codepawl Arduino pattern) |
| Waveshare e-Paper | github.com/waveshareteam/e-Paper | 1,755 / 2026-10-27 | **none** | Drivers; 3D drawings live on their wiki | **No license: don't redistribute** |
| Sketchfab | "ESP32 HikeBuddy" (sketchfab.com/3d-models/esp32-hikebuddy-4069f62a5cc84da8bccbfa1ace8c41c7), "ESP Module – DUMMY" | n/a | CC BY per search listing **[unverified: pages not opened]** | 274k-tri custom board; the "dummy" is a re-upload of a GrabCAD model | **Avoid.** Downloading needs an account, HikeBuddy is a custom board, and the dummy's provenance (GrabCAD terms) is doubtful. |

**Fastest honest route for the ESP32 demo:** draw the boards in code as r3f primitives from datasheet dimensions (`RoundedBox` PCB, a dark slab for the module shield, a grey e-paper panel with a `CanvasTexture` showing the weather UI, a foil pouch for the LiPo). That is 45–60 min, has no license questions, and matches the 2D diagram exactly. Use Adafruit MIT parts only where a real-looking model matters.

### 5.5 Hugging Face image-to-3D (for parts with no model)

Research only: no images uploaded, no Space run.

| Model | Model URL | License (model) | Outputs | Free Space (status at check) | Speed / format | Fit for small electronics |
|---|---|---|---|---|---|---|
| **TRELLIS.2-4B** (Microsoft) | huggingface.co/microsoft/TRELLIS.2-4B | **MIT** | Unrestricted (MIT) | `microsoft/TRELLIS.2`: **RUNNING** (ZeroGPU A10G) | Card: ~3 s @512³, 17 s @1024³, 60 s @1536³ on H100; GLB with PBR (WebP textures); local use needs ≥24 GB NVIDIA, "tested only on Linux" | Best candidate **[unverified quality]**. Expect smeared silkscreen and pins; the card warns of "small holes". |
| TRELLIS (v1, image-large) | huggingface.co/microsoft/TRELLIS-image-large | MIT | MIT | `microsoft/TRELLIS`: **CONFIG_ERROR**; `trellis-community/TRELLIS`: RUNNING | GLB **[unverified]** | Older |
| Hunyuan3D-2 / 2.1 / 2mini | huggingface.co/tencent/Hunyuan3D-2.1 | **Tencent Hunyuan Community License** | Tencent "claims no rights in Outputs"; **outputs may not be used to improve other AI models**; **territory excludes the EU, UK and South Korea**; >1M MAU needs a license; distribution needs a Notice file | `tencent/Hunyuan3D-2`, `-2.1`, `-2mini-Turbo`: RUNNING | Shape + texture, GLB **[unverified]** | **Region flag.** Fine for US-based hackers otherwise. |
| Hunyuan3D-Part (P3-SAM segmentation, X-Part generation) | huggingface.co/tencent/Hunyuan3D-Part | **Not stated on card** | Unknown | `tencent/Hunyuan3D-Part`: RUNNING | Splits a single mesh into parts | Interesting for "split into parts" on single-mesh models; **license unknown, so don't use** |
| Stable Fast 3D | huggingface.co/stabilityai/stable-fast-3d | **Stability AI Community License** (gated) | User owns outputs; **free only under US$1M annual revenue**; commercial use needs registration; "Powered by Stability AI" required; no training foundation models on outputs | `stabilityai/stable-fast-3d`: RUNNING | Sub-second **[unverified]**; GLB **[unverified]** | Revenue cap and attribution flags |
| SPAR3D | huggingface.co/stabilityai/stable-point-aware-3d | Stability Community | as above | **BUILD_ERROR** | n/a | n/a |
| TripoSR | huggingface.co/stabilityai/TripoSR | MIT | MIT | `stabilityai/TripoSR`: **RUNTIME_ERROR** | Fast, low-res **[unverified]** | Weak on detail **[unverified]** |
| TripoSG (VAST) | huggingface.co/VAST-AI/TripoSG | MIT | MIT | `VAST-AI/TripoSG`: RUNNING | Geometry-focused **[unverified]** | n/a |
| InstantMesh | huggingface.co/TencentARC/InstantMesh | Apache-2.0 | Apache-2.0 **[unverified upstream deps]** | `TencentARC/InstantMesh`: RUNNING | OBJ/GLB **[unverified]** | n/a |
| Step1X-3D | huggingface.co/stepfun-ai/Step1X-3D | Apache-2.0 | n/a | **PAUSED** | n/a | n/a |
| PartCrafter | huggingface.co/wgsxm/PartCrafter | MIT | n/a | no Space found | Part-aware generation | n/a |
| PartPacker (NVIDIA) | huggingface.co/nvidia/PartPacker | **NVIDIA non-commercial** | **NC** | **PAUSED** | n/a | **Don't use** |

Rules for using these:
- Generating before 11:00 counts as **prep and must be disclosed** to the organizers.
- Use your own photos. Vendor product photos are copyrighted.
- ZeroGPU Spaces have per-user daily quotas **[unverified specifics]**.
- Label anything generated as "AI-generated approximation".
- The Adafruit MIT CAD or in-code boards will usually look more correct than generated electronics.

### 5.6 Hugging Face datasets and asset collections

- **Objaverse** (`huggingface.co/datasets/allenai/objaverse`). Dataset license ODC-By 1.0, but **every object keeps its Sketchfab license**: CC-BY 721K, **CC-BY-NC 25K**, **CC-BY-NC-SA 52K**, **CC-BY-SA 16K**, CC0 3.5K.
  - Filter: load the per-object annotations (the `objaverse` Python package's `load_annotations()`) and keep `license` ∈ {CC0, CC-BY}. **[unverified exact field values: check them first]**
  - Carry each object's author and Sketchfab URL into a CREDITS file.
- Objaverse-XL (`allenai/objaverse-xl`): ODC-By, with mixed sources (GitHub, Thingiverse, Sketchfab) and per-source terms.
- **codepawl GLB packs** (`huggingface.co/datasets/codepawl/*`, e.g. `abo-glb` CC-BY-4.0, `simready-glb` CC-BY-4.0, `google-poly-glb` CC-BY-3.0). All were created Oct–Nov 2026. ABO's CC BY 4.0 matches Amazon's own page; the others are **[unverified upstream]**. No ESP32-class electronics seen.
- `lerobot/robot-urdfs`: SO-101 / SO-100 URDFs + STL, Apache-2.0.

---

## 6. Asset pipeline: STL/URDF → fast GLB

**Option A: no pipeline (recommended for tomorrow), 10 min.**
- Keep `urdf-loader` + STL; localhost loads about 16 MB fast.
- After load, smooth STL facets: `mesh.geometry = toCreasedNormals(mesh.geometry, THREE.MathUtils.degToRad(30))` (`three/examples/jsm/utils/BufferGeometryUtils.js`; KitSmith uses this). Flatten the visuals as in section 2.

**Option B: one-time browser export + glTF-Transform, 30–40 min.**

1. Add a dev-only button that calls `new GLTFExporter().parse(flatPartsGroup, save, onError, { binary: true })`. This writes `so101.glb` with names preserved. GLTFExporter ships in three.
2. Then:
```
npx @gltf-transform/cli inspect so101.glb
npx @gltf-transform/cli optimize so101.glb public/models/so101.glb --compress meshopt --flatten false --join false --instance false --palette false --simplify false
```
**Why the flags:** in `@gltf-transform/cli` 4.5.1 source, `optimize` defaults `--flatten true`, `--join true`, `--instance true`, `--palette true` and `--simplify true`. Those would merge parts into one mesh, instance the servos and merge materials, and per-part picking would break.

3. Load with `useGLTF('/models/so101.glb', false /* no Draco */, true /* meshopt, bundled */)`. Meshopt-quantized files carry dequantization on the node, so use world matrices (KitSmith bakes them).

- Alternative: `npx gltfpack -i so101.glb -o so101.glb -cc -kn -km` (gltfpack 1.3.0, MIT). `-kn` / `-km` keep named nodes and materials; by default gltfpack merges meshes and prunes nodes, and it quantizes unless you pass `-noq`.
- Optional: `npx gltfjsx public/models/so101.glb -t` (gltfjsx 6.5.3, MIT; last push 2024-11) generates a typed component with one JSX node per part.
- Per-file alternatives, untested by me: trimesh (MIT, 3,728★) `trimesh.load('x.stl').export('x.glb')`; assimp (BSD-3, 13,334★) `assimp export x.stl x.glb`; Blender CLI (GPL tool; outputs unrestricted) with the STL import operator, then `bpy.ops.export_scene.gltf` **[unverified operator name for your Blender version]**.
- STEP (Adafruit parts) → GLB: open in **3dviewer.net** (local, in-browser) → Export → glb. Then run the same `optimize` line.

**`<model-viewer>` AR: skip tomorrow.**
- `@google/model-viewer` 4.4.0 (Apache-2.0, 8,349★) has peer `three ^0.183.0`, which conflicts with our three 0.186/0.187 (use a separate page or its standalone bundle).
- Draco and KTX2 decoders default to **gstatic**, and the Lottie loader to jsDelivr.
- Android Scene Viewer receives the model's URL through an `intent://arvr.google.com/scene-viewer/...&file=` link, so the phone must reach that URL (not `localhost`, and not offline).
- iOS Quick Look converts to USDZ on the fly (it imports `USDZExporter`) unless you pass `ios-src`.
- Total: about 30 min, and it breaks the offline rule.

---

## 7. Inspiration: what makes each one hooky

| Demo | URL | Hook to steal |
|---|---|---|
| **KitSmith SO-101 guide** | kitsmith.dev/so101/ | The current step's parts lit, the built arm under them, **future parts ghosted**. It's our robot, so every explanation is literal. A searchable error box ("paste an error message") and a BOM with vendor cross-reference. |
| **MakerWorks SO-101 exploded view** | makerworkslab.in/ajayummadi/projects/lerobot-so-101/ | **Seven numbered stages.** Hovering the part, its marker or its name highlights all three, so 3D and the list feel like one object. |
| **codepawl "Learn Arduino in 3D"** | github.com/codepawl/3d-builds/tree/main/works/2026-10-23-arduino-breadboard | Parts **fly from a tray into exact holes**, current flow sits behind a toggle, code lines highlight with state. Same r3f stack. |
| **codepawl "Anatomy of a machine"** | github.com/codepawl/3d-builds/tree/main/works/2026-10-11-machine-anatomy | The explode follows **real removal axes**; numbered legend, live readout, a trace strip of events in plain words |
| **human-atlas** | github.com/ashemag/human-atlas | **Assembled → spaced inventory** of every visible piece (our "kit view" with prices); system presets; search |
| **pmndrs `faucets-select-highlight`** | pmndrs.github.io/examples/faucets-select-highlight (source in pmndrs/examples) | drei `Outlines` + `AccumulativeShadows` + `Environment`: a hover that looks like product photography |
| **pmndrs `selective-outlines`** | pmndrs.github.io/examples/selective-outlines | `<Selection>` + `<Select enabled={hovered}>` + `EffectComposer multisampling={8} autoClear={false}` + `<Outline>` |
| **pmndrs `bounds-and-makedefault`** | pmndrs.github.io/examples/bounds-and-makedefault | Click to zoom into a part, click the background to zoom back out |
| **pmndrs `wireframes`** | pmndrs.github.io/examples/wireframes | drei `Wireframe` on a loaded car GLB, which is our "not found yet" look |
| **pmndrs `html-annotations` / `shoe-configurator`** | pmndrs.github.io/examples/html-annotations · /shoe-configurator | DOM annotations pinned in 3D; click a part to recolour it (our colour modes) |
| **three-cad-viewer** | bernhard-42.github.io/three-cad-viewer/example.html | Single-key modes (x explode, t transparent, C clip): the demo-driver's cheat sheet |
| **Smithsonian Voyager** | smithsonian.github.io/dpo-voyager/explorer/overview/ | Tours plus a reader: a story told through the object |
| **Zygote Body / BioDigital** | zygotebody.com · biodigital.com/product/human-studio | Opacity "peel" slider, Ctrl-click hide, fade vs emphasize, label layouts |
| **jh3y CSS exploded pens** | codepen.io/jh3y/pen/ZEOzNbm · /QWELPQg **[unverified: 403]** | Pure-CSS layered explode, ideal for the ESP32 stack in the 2D demo |
| HF-hosted helpers | Gradio `Model3D` uses **Babylon.js**, not three (`@babylonjs/core` in gradio's `js/model3D/package.json`); static Spaces can host a built three.js page; `jurmy24/urdf-visualizer` (no license, Docker) | Nothing r3f-specific worth pulling in |

---

## Visual hook recipe (one frontend dev owns the 3D view; 11:00–16:30 PT)

Prep before 11:00 is limited to downloading the CC0 HDRI and the Adafruit STEPs, installing the skills and pinning versions. Disclose all of it.

**11:00–11:30: stage and lighting.**
1. Pin versions (TL;DR #1).
2. `<Canvas dpr={[1, 1.5]} frameloop="demand" shadows camera={{ fov: 35 }}>` on a mid-grey `#1d2026` → `#2a2f38` radial background.
3. `RoomEnvironment` PMREM (or `<Environment files="/hdri/studio_small_03_1k.hdr" />`), one key `directionalLight`, and `<ContactShadows opacity={0.45} blur={2.2} />`.
4. `<CameraControls makeDefault smoothTime={0.35} />` from drei.

**11:30–12:15: load, flatten, register parts.**
1. urdf-loader → creased normals → clone materials → `parts.attach()` the 17 visual meshes.
2. Build a `meshName → partId` map (5 + 1 servos share one part ID and quantity).
3. Create a zustand store with `hovered`, `selected`, `isolated`, `hidden[]`, `explode`, `colourMode`, `status{partId}`.
4. Wrap the robot in `<Bvh firstHitOnly>`.

**12:15–13:00: the instantly understandable loop.**
1. Hover: `useCursor`, emissive tint 0.15, `<Outlines screenspace angle={0.5}>` (tune `thickness` by eye on the projector; I did not verify its units in screenspace mode), and the list row highlights and scrolls into view.
2. Click: `controls.fitToBox(mesh, true, { paddingTop: .3, … })` and open the shadcn offers `Sheet`.
3. Click the background or press Esc to reset with `setLookAt(..., true)`.
4. Hovering a list row lights the mesh (two-way).

**13:00–13:45: explode slider.**
1. Staged explode along hand-set per-link vectors (base stays put; gripper travels farthest) with maath `damp3`.
2. The camera pulls back as it explodes (`autoDistance`).
3. Add a "Kit view" button that flies every part into a grid on the floor (knolling) with `Html` price tags. **This is the money shot.**

**13:45–14:30: progressive reveal + colour modes.**
1. Unknown parts: grey `Edges` (`linewidth={2}`) + 5% fill.
2. Searching: a breathing emissive pulse.
3. Found: damp to a solid status colour + a 150 ms flash + a `@react-spring/three` 1.03 scale pop.
4. Reveal in assembly order (base → jaw) as results stream in.
5. Add a colour-mode segmented control (status / store / checkout type) with a legend; damp colours with `easing.dampC`.
6. Add the off-model tray: a DOM strip under the canvas with icon cards (screws, cables, PSU, controller board) that share the same status colours and hover states.

**14:30–15:15: isolate, ghost, labels, post.**
1. Isolate → others at 0.1 opacity with `depthWrite: false`; Ctrl-click hide with an "Unhide all" chip; optional "Shells" opacity slider (peel the printed parts to show the servos).
2. Two-column leader-line labels (Moh4696 pattern), shown only when exploded or isolated.
3. `<EffectComposer><N8AO halfRes aoRadius={0.5} intensity={2} /><SMAA /></EffectComposer>`, then re-check FPS on the Windows laptop at projector resolution.

**15:15–15:45: ESP32 2D diagram (same visual language).**
1. `@xyflow/react` custom nodes shaped like the boards, with pin rows; edges labelled I²C / SPI / power, `animated` on the active bus; the same status palette and two-way highlight with the parts list.
2. A CSS-3D exploded stack (e-paper / FireBeetle / BME280 / LiPo) driven by the **same explode slider** component.
3. Optional: in-code r3f boards (codepawl Arduino pattern) or Adafruit MIT stand-ins.

**15:45–16:15: choreography and the offline test.**
1. A 4-second intro: camera dolly from a ¾-high view (`setLookAt` transition), then parts reveal one by one as offers arrive, then auto-explode to 0.6, then "Kit view" → "Add all to cart".
2. Turn Wi-Fi off and reload. Check there are no network requests in DevTools (no githack, gstatic, Google Fonts or jsDelivr).

**16:15–16:30: freeze.** Tag the build. Record a 60 s backup screen capture of the full flow. Hide leva and perf overlays.
