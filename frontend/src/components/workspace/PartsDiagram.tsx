// The 2D board diagram (PLAN §13.7): a wiring-style diagram in the same slot as the 3D view, with the same
// hover, click → part panel, two-way highlight and colour modes. Edges are the compatibility rules:
// green pass · amber needs your check · red fail. Clicking an edge opens its part on the Why tab.
// With no designed layout the lines are laid out around a centre project node (the fallback for every type).
import "@xyflow/react/dist/style.css";

import { Background, BackgroundVariant, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { BatteryMedium, Box, Cable, Camera, CircuitBoard, Cog, Cpu, Monitor, Package, Plug, Radio, Thermometer, Wrench, Zap, type LucideIcon } from "lucide-react";
import { useMemo } from "react";

import { ActionIcon } from "@/components/panel/ActionBadge";
import { money } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import { isPending, paintFor, type StageData, type StageLine } from "@/lib/stage";
import type { Check, CheckResult, PartCategory, ViewData } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = { Cpu, Monitor, Cable, Thermometer, BatteryMedium, Box, Camera, Radio, Plug, Zap, Cog, Wrench, CircuitBoard, Package };
const CATEGORY_ICON: Record<PartCategory, LucideIcon> = {
  board: Cpu,
  motor: Cog,
  esc_driver: CircuitBoard,
  battery: BatteryMedium,
  power: Plug,
  sensor: Thermometer,
  camera: Camera,
  radio: Radio,
  cable: Cable,
  mechanical: Cog,
  printed: Box,
  tool: Wrench,
};

type PartNodeData = { lineId: string | null; label: string; icon: string; data: StageData; centre?: boolean; sub?: string };
type PartNode = Node<PartNodeData, "part">;

function PartNodeCard({ data: d }: NodeProps<PartNode>) {
  const line: StageLine | undefined = d.lineId ? d.data.lines.get(d.lineId) : undefined;
  const mode = useAppStore((s) => s.colourMode);
  const hovered = useAppStore((s) => d.lineId !== null && s.hoveredLineId === d.lineId);
  const selected = useAppStore((s) => d.lineId !== null && s.selectedLineId === d.lineId);
  const dimmed = useAppStore((s) => s.selectedLineId !== null && s.selectedLineId !== d.lineId);
  const paint = paintFor(line, mode, d.data);
  const pending = line ? isPending(line.status) : false;
  const Icon = ICONS[d.icon] ?? (line?.category ? CATEGORY_ICON[line.category] : Box);
  const edge = pending ? "--b2c-mat-unknown" : (paint.token ?? (line ? "--b2c-pass" : "--b2c-stage-border"));
  return (
    <div
      className={cn(
        "flex size-full items-center gap-3 rounded-lg border bg-stage-surface px-3 text-left transition-[border-color,opacity,box-shadow] duration-150",
        selected ? "border-brand ring-2 ring-brand/50" : hovered ? "border-brand" : "border-stage-border",
        dimmed && "opacity-45",
        d.centre && "border-stage-muted",
        pending && "border-dashed",
      )}
      style={{ borderLeftWidth: 4, borderLeftColor: selected || hovered ? undefined : `var(${edge})` }}
    >
      {(["l", "r"] as const).flatMap((side) =>
        (["source", "target"] as const).map((type) => (
          <Handle key={`${type}-${side}`} id={`${type}-${side}`} type={type} position={side === "l" ? Position.Left : Position.Right} isConnectable={false} className="!size-1 !border-0 !bg-transparent" />
        )),
      )}
      <Icon className="size-5 shrink-0 text-stage-muted" strokeWidth={1.75} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="truncate text-small font-medium text-stage-text">{d.label}</p>
        <p className="flex items-center gap-1.5 truncate text-caption text-stage-muted">
          {d.sub ? (
            d.sub
          ) : line?.storeName ? (
            <>
              {line.level ? <ActionIcon level={line.level} /> : null}
              <span className="truncate">{line.storeName}</span>
              <span className="tabular font-mono text-stage-text">{money(line.price)}</span>
            </>
          ) : pending ? (
            "searching…"
          ) : line?.status === "owned" ? (
            "you own it"
          ) : line ? (
            (line.status === "not_found" ? "not found in your stores" : "nothing to buy")
          ) : (
            "not in this parts list"
          )}
        </p>
        {line && (line.status === "warning" || line.status === "needs_human" || line.openAssumption) ? <p className="truncate text-caption text-warn">{line.openAssumption ? "Assumed: confirm it" : "Needs your check"}</p> : null}
      </div>
    </div>
  );
}

const nodeTypes = { part: PartNodeCard };

const RESULT_TOKEN: Record<CheckResult | "unknown", string> = {
  pass: "--b2c-pass",
  warn: "--b2c-warn",
  needs_human: "--b2c-warn",
  fail: "--b2c-fail",
  unknown: "--b2c-stage-border",
};
const RESULT_WORD: Record<CheckResult | "unknown", string> = { pass: "pass", warn: "check", needs_human: "check", fail: "fail", unknown: "" };

/** "R12" matches the check "R12 CONNECTOR_MATCH". The worst result wins. */
function resultFor(ruleIds: string[], checks: Check[]): CheckResult | "unknown" {
  const hits = checks.filter((c) => ruleIds.some((id) => c.rule_id === id || c.rule_id.startsWith(`${id} `)));
  if (hits.some((c) => c.result === "fail")) return "fail";
  if (hits.some((c) => c.result === "warn" || c.result === "needs_human")) return "warn";
  return hits.length ? "pass" : "unknown";
}

type Built = { nodes: PartNode[]; edges: Edge[]; lineOfNode: Map<string, string | null> };

function build(view: ViewData, data: StageData, checks: Check[], title: string): Built {
  const lineOfNode = new Map<string, string | null>();
  let nodes: PartNode[];
  let rawEdges: Array<{ from: string; to: string; label: string; rule_ids: string[] }>;

  if (view.diagram?.nodes.length) {
    nodes = view.diagram.nodes.map((n) => ({
      id: n.id,
      type: "part",
      position: { x: n.x, y: n.y },
      width: n.w,
      height: n.h,
      data: { lineId: n.bom_line_id ?? null, label: n.label, icon: n.icon, data },
    }));
    rawEdges = view.edges ?? [];
  } else {
    // Auto layout: the project in the centre, its parts in a column on each side, one edge per part.
    const tray = new Set(view.tray);
    const lines = [...data.lines.values()].filter((l) => !tray.has(l.id) && l.lineKind !== "tool" && l.status !== "removed");
    const left = lines.filter((_, i) => i % 2 === 0);
    const right = lines.filter((_, i) => i % 2 === 1);
    const rows = Math.max(left.length, right.length, 1);
    const H = 64;
    const GAP = 18;
    const total = rows * H + (rows - 1) * GAP;
    const col = (items: StageLine[], x: number): PartNode[] => {
      const h = items.length * H + (items.length - 1) * GAP;
      return items.map((l, i) => ({
        id: l.id,
        type: "part" as const,
        position: { x, y: (total - h) / 2 + i * (H + GAP) },
        width: 230,
        height: H,
        data: { lineId: l.id, label: l.name, icon: "", data },
      }));
    };
    nodes = [
      ...col(left, 0),
      { id: "__project", type: "part", position: { x: 340, y: total / 2 - 42 }, width: 220, height: 84, data: { lineId: null, label: title, icon: "Package", data, centre: true, sub: `${lines.length} parts` } },
      ...col(right, 670),
    ];
    rawEdges = lines.map((l) => {
      const mine = checks.filter((c) => c.bom_line_ids.includes(l.id));
      return { from: l.id, to: "__project", label: mine.length ? mine.map((c) => c.rule_id.split(" ")[0]).join(" · ") : "", rule_ids: mine.map((c) => c.rule_id) };
    });
  }
  for (const n of nodes) lineOfNode.set(n.id, n.data.lineId);
  const xOf = new Map(nodes.map((n) => [n.id, n.position.x]));

  const edges: Edge[] = rawEdges.map((e, i) => {
    const result = resultFor(e.rule_ids, checks);
    const colour = `var(${RESULT_TOKEN[result]})`;
    const ltr = (xOf.get(e.from) ?? 0) <= (xOf.get(e.to) ?? 0);
    const fromLine = lineOfNode.get(e.from);
    const pending = [fromLine, lineOfNode.get(e.to)].some((id) => {
      const l = id ? data.lines.get(id) : undefined;
      return l ? isPending(l.status) : false;
    });
    const word = RESULT_WORD[result];
    const rules = e.rule_ids.map((r) => r.split(" ")[0]).join(", ");
    const label = view.diagram?.nodes.length ? [e.label, rules && `${rules}${word ? ` ${word}` : ""}`].filter(Boolean).join(" · ") : e.label && word ? `${e.label} ${word}` : e.label;
    return {
      id: `e${i}-${e.from}-${e.to}`,
      source: e.from,
      target: e.to,
      sourceHandle: ltr ? "source-r" : "source-l",
      targetHandle: ltr ? "target-l" : "target-r",
      type: "default",
      // Above the node cards, so a label between two close nodes is never clipped.
      zIndex: 5,
      animated: pending,
      label: label || undefined,
      style: { stroke: colour, strokeWidth: 2 },
      labelStyle: { fill: "var(--b2c-stage-text)", fontSize: 12, fontFamily: "var(--b2c-font-sans)" },
      labelBgStyle: { fill: "var(--b2c-stage-surface)", stroke: colour, strokeWidth: 1 },
      labelBgPadding: [8, 4] as [number, number],
      labelBgBorderRadius: 6,
      ariaLabel: `Rule ${rules || "link"}: ${e.label}${word ? `, ${word}` : ""}`,
    };
  });
  return { nodes, edges, lineOfNode };
}

export function PartsDiagram({ view, data, checks, title }: { view: ViewData; data: StageData; checks: Check[]; title: string }) {
  const select = useAppStore((s) => s.select);
  const hover = useAppStore((s) => s.hover);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const built = useMemo(() => build(view, data, checks, title), [view, data, checks, title]);

  return (
    <ReactFlow
      nodes={built.nodes}
      edges={built.edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.14, maxZoom: 1.1 }}
      minZoom={0.4}
      maxZoom={1.6}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      zoomOnScroll={false}
      preventScrolling={false}
      proOptions={{ hideAttribution: false }}
      onNodeClick={(_, node) => node.data.lineId && select(node.data.lineId, node.id)}
      onNodeMouseEnter={(_, node) => node.data.lineId && hover(node.data.lineId)}
      onNodeMouseLeave={() => hover(null)}
      onEdgeClick={(_, edge) => {
        // An edge is a rule: open the part it protects (the source, or else the target) on the Why tab.
        const lineId = built.lineOfNode.get(edge.source) ?? built.lineOfNode.get(edge.target);
        if (lineId) select(lineId, null, "why");
      }}
      onPaneClick={() => clearSelection()}
      aria-label="Board diagram. Lines between parts are the compatibility rules."
      style={{ background: "transparent" }}
    >
      <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--b2c-stage-border)" />
    </ReactFlow>
  );
}
