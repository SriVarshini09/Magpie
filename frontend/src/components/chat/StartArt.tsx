// The start page's blueprint art: the hero panel (sky, grid, our drone) and the line drawings on the sample cards.
// Every drawing is illustrative and every number on it is measured, never typed in:
// - The drone is our own 5-inch quad (models/quadcopter.ts + models/detail), rendered once to /start/ (PNG, WebP) in a
//   blueprint line style. 220 mm is QUAD's motor-to-motor diagonal; in the three-quarter views that diagonal lies
//   flat on screen, so the dimension line spans the two motor centres exactly.
// - The arm is the SO-101 from /so101 (URDF + meshes), posed shoulder 0.5 rad back, elbow 0.6, wrist 0.8.
//   247 mm is that pose's height, from the meshes' bounding box (-2.4 to 244.6 mm).
// - The e-paper display is a sketch of esp32-weather-epd's 7.5 in, 800 × 480 px panel (the README's
//   "Waveshare 7.5in e-paper (v2)"), with the boards its README lists. No millimetres: none are in this repo.
// Anchor points below are the renderer's projected pixels for those 3D points (scratch render, Nov 20 2026).
// The images are static files: three.js never loads for this page.
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type P = [number, number];
const LINE = "var(--b2c-blueprint-line)";

/** A dimension line with arrowheads and its label in a gap, upright whatever the angle. */
function Dim({ a, b, label, size = 10, color = LINE }: { a: P; b: P; label: string; size?: number; color?: string }) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len = Math.hypot(dx, dy) || 1;
  const u: P = [dx / len, dy / len];
  const n: P = [-u[1], u[0]];
  const mid: P = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const gap = Math.min(len - size * 2, label.length * size * 0.6 + size * 0.8);
  const g1: P = [mid[0] - (u[0] * gap) / 2, mid[1] - (u[1] * gap) / 2];
  const g2: P = [mid[0] + (u[0] * gap) / 2, mid[1] + (u[1] * gap) / 2];
  let angle = (Math.atan2(dy, dx) * 180) / Math.PI;
  if (angle > 90) angle -= 180;
  if (angle <= -90) angle += 180;
  const ah = size * 0.62;
  const aw = size * 0.2;
  const arrow = (tip: P, dir: number) => {
    const bx = tip[0] + u[0] * ah * dir;
    const by = tip[1] + u[1] * ah * dir;
    return `M${tip[0]},${tip[1]} L${bx + n[0] * aw},${by + n[1] * aw} L${bx - n[0] * aw},${by - n[1] * aw} Z`;
  };
  return (
    <g>
      <path d={`M${a[0]},${a[1]} L${g1[0]},${g1[1]} M${g2[0]},${g2[1]} L${b[0]},${b[1]}`} stroke={color} strokeWidth={1} vectorEffect="non-scaling-stroke" fill="none" />
      <path d={`${arrow(a, 1)} ${arrow(b, -1)}`} fill={color} />
      <text x={mid[0]} y={mid[1]} transform={`rotate(${angle} ${mid[0]} ${mid[1]})`} textAnchor="middle" dominantBaseline="central" fontSize={size} fill={color} className="font-sans" style={{ fontVariantNumeric: "tabular-nums" }}>
        {label}
      </text>
    </g>
  );
}

/** Extension lines: thin, from the drawing out to the dimension line. */
function Ext({ lines, color = LINE }: { lines: Array<[number, number, number, number]>; color?: string }) {
  return (
    <path
      d={lines.map(([x1, y1, x2, y2]) => `M${x1},${y1} L${x2},${y2}`).join(" ")}
      stroke={color}
      strokeOpacity={0.55}
      strokeWidth={1}
      vectorEffect="non-scaling-stroke"
      fill="none"
    />
  );
}

function ViewLabel({ x, y, children, color = LINE }: { x: number; y: number; children: ReactNode; color?: string }) {
  return (
    <text x={x} y={y} fontSize={7.5} letterSpacing={1.2} fill={color} fillOpacity={0.75} className="font-mono">
      {children}
    </text>
  );
}

/** A registration mark: a circle with a cross through it. */
export function Crosshair({ className, size = 22 }: { className?: string; size?: number }) {
  return (
    <svg viewBox="0 0 22 22" width={size} height={size} aria-hidden className={cn("pointer-events-none text-blueprint-line/40", className)}>
      <circle cx="11" cy="11" r="5.5" fill="none" stroke="currentColor" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <path d="M11 0V22M0 11H22" stroke="currentColor" strokeWidth="1" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const svgProps = { viewBox: "0 0 360 190", preserveAspectRatio: "xMidYMid meet", "aria-hidden": true } as const;

function Separator() {
  return <path d="M258,6 L258,184" stroke={LINE} strokeOpacity={0.35} strokeWidth={1} vectorEffect="non-scaling-stroke" />;
}

/** Our 5-inch quad: three-quarter view (scale 0.5 of a 500 × 380 render), top and front views. */
export function DroneDrawing({ className }: { className?: string }) {
  // Motor centres in the main view: (94, 213.2) and (397.8, 213.2) at 0.7244 mm per pixel = 220 mm.
  const l = 47;
  const r = 198.9;
  return (
    <svg {...svgProps} className={className}>
      <image href="/start/card-drone-main.webp" x={0} y={0} width={250} height={190} />
      <Ext lines={[[l, 114, l, 186], [r, 114, r, 186]]} />
      <Dim a={[l, 181]} b={[r, 181]} label="220 mm" />
      <Separator />
      <image href="/start/card-drone-top.png" x={266} y={4} width={88} height={88} />
      <ViewLabel x={266} y={103}>TOP</ViewLabel>
      <image href="/start/card-drone-front.png" x={266} y={122} width={88} height={48.4} />
      <ViewLabel x={266} y={183}>FRONT</ViewLabel>
    </svg>
  );
}

/** The SO-101 in a reaching pose: three-quarter view (scale 0.464 of a 500 × 380 render), top and front views. */
export function ArmDrawing({ className }: { className?: string }) {
  // Highest and lowest vertices of the posed arm project to (147.9, 10.8) and (148.1, 366.6) in the main render.
  const top = 4 + 10.8 * 0.464;
  const bottom = 4 + 366.6 * 0.464;
  return (
    <svg {...svgProps} className={className}>
      <image href="/start/card-arm-main.webp" x={18} y={4} width={232} height={176.3} />
      <Ext lines={[[3, top, 82, top], [3, bottom, 82, bottom]]} />
      <Dim a={[8, top]} b={[8, bottom]} label="247 mm" />
      <Separator />
      <image href="/start/card-arm-top.png" x={266} y={4} width={88} height={88} />
      <ViewLabel x={266} y={101}>TOP</ViewLabel>
      <image href="/start/card-arm-front.png" x={266} y={100} width={88} height={78} preserveAspectRatio="xMidYMid meet" />
      <ViewLabel x={266} y={183}>FRONT</ViewLabel>
    </svg>
  );
}

/** esp32-weather-epd: the 7.5 in, 800 × 480 px panel with a weather layout sketched in, and the boards behind it. */
export function EpaperDrawing({ className }: { className?: string }) {
  // Active area 5:3 (800 × 480 px). The bezel and ribbon are drawn to look like a raw panel, not to scale.
  const ax = 40;
  const ay = 27;
  const aw = 196;
  const ah = 117.6;
  const thin = { stroke: LINE, strokeWidth: 1, vectorEffect: "non-scaling-stroke" as const, fill: "none" };
  const soft = { ...thin, strokeOpacity: 0.7 };
  const bar = (x: number, y: number, w: number, h = 3.2) => <rect x={x} y={y} width={w} height={h} rx={h / 2} fill={LINE} fillOpacity={0.28} />;
  const days = [0, 1, 2, 3, 4];
  return (
    <svg {...svgProps} className={className}>
      {/* A frame around the panel, four corner screws, the active area */}
      <rect x={ax - 9} y={ay - 9} width={aw + 18} height={ah + 18} rx={4} {...thin} fill="#fff" fillOpacity={0.9} />
      <rect x={ax - 5} y={ay - 5} width={aw + 10} height={ah + 10} rx={2} {...soft} strokeOpacity={0.4} />
      {[
        [ax - 4.5, ay - 4.5],
        [ax + aw + 4.5, ay - 4.5],
        [ax - 4.5, ay + ah + 4.5],
        [ax + aw + 4.5, ay + ah + 4.5],
      ].map(([x, y]) => (
        <circle key={`${x}:${y}`} cx={x} cy={y} r={2} {...soft} />
      ))}
      <rect x={ax} y={ay} width={aw} height={ah} {...soft} fill="#fff" />
      {/* Current conditions: sun behind a cloud, then the reading and a few detail rows */}
      <g {...soft}>
        <circle cx={ax + 22} cy={ay + 20} r={8} />
        {[0, 45, 90, 135, 180, 225, 270, 315].map((d) => {
          const t = (d * Math.PI) / 180;
          return <path key={d} d={`M${ax + 22 + Math.cos(t) * 11},${ay + 20 + Math.sin(t) * 11} L${ax + 22 + Math.cos(t) * 14},${ay + 20 + Math.sin(t) * 14}`} />;
        })}
        <path d={`M${ax + 18},${ay + 38} h24 a6,6 0 0 0 0,-12 a8,8 0 0 0 -15,-2 a6,6 0 0 0 -9,14 z`} fill="#fff" />
      </g>
      {bar(ax + 52, ay + 12, 34, 9)}
      {bar(ax + 52, ay + 26, 22)}
      {[0, 1, 2, 3].map((i) => (
        <g key={i}>
          <rect x={ax + 9} y={ay + 52 + i * 15} width={7} height={7} rx={1.5} {...soft} />
          {bar(ax + 20, ay + 54 + i * 15, 26 + ((i * 7) % 12))}
        </g>
      ))}
      {/* Five-day forecast */}
      {days.map((i) => {
        const x = ax + 98 + i * 19.5;
        return (
          <g key={i}>
            {bar(x, ay + 9, 10, 2.6)}
            {i % 2 ? <path d={`M${x - 1},${ay + 24} h12 a3.5,3.5 0 0 0 0,-7 a5,5 0 0 0 -9,-1 a3.5,3.5 0 0 0 -3,8 z`} {...soft} /> : <circle cx={x + 5} cy={ay + 20} r={4} {...soft} />}
            {bar(x, ay + 30, 12, 2.6)}
          </g>
        );
      })}
      {/* Outlook chart: temperature line over rain bars */}
      <path d={`M${ax + 96},${ay + 104} H${ax + aw - 8} M${ax + 96},${ay + 104} V${ay + 48}`} {...soft} />
      {Array.from({ length: 16 }, (_, i) => {
        const h = [2, 4, 7, 9, 6, 3, 1, 0, 0, 2, 5, 8, 6, 3, 1, 0][i];
        return h ? <rect key={i} x={ax + 99 + i * 5.6} y={ay + 104 - h * 2} width={3.4} height={h * 2} fill={LINE} fillOpacity={0.2} /> : null;
      })}
      <path
        d={`M${ax + 98},${ay + 82} C${ax + 112},${ay + 64} ${ax + 126},${ay + 60} ${ax + 140},${ay + 70} S${ax + 166},${ay + 92} ${ax + 178},${ay + 80} S${ax + 182},${ay + 60} ${ax + aw - 10},${ay + 66}`}
        {...thin}
      />
      {/* Dimensions: the active area in pixels */}
      <Ext lines={[[ax, ay - 11, ax, ay - 22], [ax + aw, ay - 11, ax + aw, ay - 22], [ax - 11, ay, ax - 34, ay], [ax - 11, ay + ah, ax - 34, ay + ah]]} />
      <Dim a={[ax, ay - 18]} b={[ax + aw, ay - 18]} label="800 px" />
      <Dim a={[ax - 29, ay]} b={[ax - 29, ay + ah]} label="480 px" />
      <Separator />
      {/* Side: the framed panel, its ribbon folded back to the DESPI-C02, and the FireBeetle behind */}
      <g {...thin}>
        <rect x={272} y={8} width={5} height={78} rx={1} />
        <path d="M277,78 q6,0 6,-6 v-4" />
        <rect x={283} y={52} width={8} height={20} rx={1} />
        <rect x={300} y={16} width={8} height={54} rx={1} />
        <rect x={308} y={22} width={3} height={7} />
        <path d="M291,62 h9" strokeDasharray="2 2" />
      </g>
      <ViewLabel x={266} y={101}>SIDE</ViewLabel>
      {/* The boards the README lists, as a block diagram */}
      <g {...thin}>
        <rect x={266} y={112} width={54} height={17} rx={2} />
        <rect x={266} y={136} width={54} height={14} rx={2} />
        <rect x={325} y={113} width={31} height={15} rx={2} />
        <path d="M293,129 V136 M320,120.5 H325" />
      </g>
      <text x={293} y={123.5} textAnchor="middle" fontSize={7.5} fill={LINE} className="font-sans">ESP32-E</text>
      <text x={293} y={145.5} textAnchor="middle" fontSize={7.5} fill={LINE} className="font-sans">DESPI-C02</text>
      <text x={340.5} y={123} textAnchor="middle" fontSize={6.5} fill={LINE} className="font-sans">BME280</text>
      <ViewLabel x={266} y={168}>BOARDS</ViewLabel>
    </svg>
  );
}

const FADE = "linear-gradient(90deg, transparent 0%, rgb(0 0 0 / 0.14) 12%, rgb(0 0 0 / 0.36) 22%, #000 36%)";

/**
 * The hero's artwork: a blueprint sky (clouds drawn in code, rasterised to /start/sky.webp), a white grid, our
 * drone with its 220 mm dimension, and top and front views in white lines. Decorative: hidden from screen readers.
 */
export function HeroArt({ className }: { className?: string }) {
  const white = "rgb(255 255 255 / 0.92)";
  // Motor centres in the 880 × 500 hero render: (160.1, 295) and (705.1, 295) at 0.4038 mm per pixel = 220 mm.
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none overflow-hidden rounded-[3px] bg-[#2157cf]", className)}
      // The left edge fades into the paper so the headline over it stays dark on light.
      style={{ maskImage: FADE, WebkitMaskImage: FADE }}
    >
      <div className="absolute inset-0 bg-[url(/start/sky.webp)] bg-cover bg-bottom" />
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgb(255 255 255 / 0.16) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.16) 1px, transparent 1px), linear-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.07) 1px, transparent 1px)",
          backgroundSize: "140px 140px, 140px 140px, 28px 28px, 28px 28px",
          backgroundPosition: "-1px -1px",
        }}
      />
      <div className="absolute top-[4%] left-[32%] w-[46%]" style={{ aspectRatio: "880 / 500" }}>
        <svg viewBox="0 0 880 500" className="absolute inset-0 size-full overflow-visible">
          <circle cx={432} cy={262} r={300} fill="none" stroke="rgb(255 255 255 / 0.35)" strokeWidth={1} strokeDasharray="6 8" vectorEffect="non-scaling-stroke" />
          <path d="M432,-60 V585 M100,262 H770" stroke="rgb(255 255 255 / 0.22)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        </svg>
        <img src="/start/hero-drone.webp" alt="" width={880} height={500} decoding="async" className="absolute inset-0 size-full" />
        <svg viewBox="0 0 880 500" className="absolute inset-0 size-full overflow-visible">
          <Ext lines={[[160.1, 250, 160.1, -6], [705.1, 250, 705.1, -6]]} color={white} />
          <Dim a={[160.1, 6]} b={[705.1, 6]} label="220 mm" size={24} color={white} />
        </svg>
      </div>
      {/* Top and front views, framed like a drawing sheet's side column, kept above the cloud bank */}
      <div className="absolute top-[7%] right-[3%] w-[14%] min-w-[104px] border-l border-white/35 pl-[1.6%]">
        <img src="/start/hero-drone-top.png" alt="" width={300} height={300} decoding="async" className="w-full" />
        <p className="font-mono text-[10px] tracking-[0.14em] text-white/80">TOP</p>
        <div className="my-[9%] border-t border-white/35" />
        <img src="/start/hero-drone-front.png" alt="" width={300} height={140} decoding="async" className="w-full" />
        <p className="font-mono text-[10px] tracking-[0.14em] text-white/80">FRONT</p>
      </div>
      <Crosshair className="absolute top-3 right-3 text-white/60" size={22} />
    </div>
  );
}
