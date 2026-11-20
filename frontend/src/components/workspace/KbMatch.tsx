// "Why this matched" for knowledge-base rows (PLAN §3.14). Owner: D. The query's index tokens as chips with the
// analyzer that split them, a row's text with its matched tokens marked, and its rank in each half of the hybrid
// search. Marks are React <mark> elements built from character ranges: no HTML is injected.
import { Fragment, useMemo } from "react";

import { SimulatedTag } from "@/components/MockDataBadge";
import type { KbChunk } from "@/lib/types";
import { cn } from "@/lib/utils";

const TOKEN_CHAR = /[\p{L}\p{N}]/u;
const MARK = /\p{Mn}/u;

/** Case- and diacritic-insensitive form of one character (or a term), as the full-text tokenizers fold it. */
function fold(s: string): string {
  return s.normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase().replace(/ς/g, "σ");
}

/**
 * Character ranges [start, end) of `text` where a term occurs as a whole token: no letter or digit right before or
 * after it. That one rule fits both analyzers: SQLite's unicode61 ("5x2" inside "5.5x2.1") and SingleStore's
 * standard tokenizer ("5.5x2.1mm" as one token). Sorted, overlaps merged.
 */
export function matchRanges(text: string, terms: readonly string[]): Array<[number, number]> {
  if (!text || !terms.length) return [];
  let norm = "";
  const from: number[] = [];
  const to: number[] = [];
  let i = 0;
  for (const ch of text) {
    const f = fold(ch);
    for (let k = 0; k < f.length; k++) {
      from.push(i);
      to.push(i + ch.length);
    }
    norm += f;
    i += ch.length;
  }
  const found: Array<[number, number]> = [];
  for (const term of new Set(terms.map(fold).filter(Boolean))) {
    for (let at = norm.indexOf(term); at !== -1; at = norm.indexOf(term, at + 1)) {
      const before = at > 0 ? norm[at - 1] : "";
      const after = norm[at + term.length] ?? "";
      if (TOKEN_CHAR.test(before) || TOKEN_CHAR.test(after)) continue;
      let end = to[at + term.length - 1];
      while (end < text.length && MARK.test(text[end])) end++;
      found.push([from[at], end]);
    }
  }
  found.sort((a, b) => a[0] - b[0] || b[1] - a[1]);
  const merged: Array<[number, number]> = [];
  for (const r of found) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  return merged;
}

/** `text` with every matched term wrapped in a <mark>. */
export function MatchedText({ text, terms }: { text: string; terms: readonly string[] }) {
  const ranges = useMemo(() => matchRanges(text, terms), [text, terms]);
  if (!ranges.length) return <>{text}</>;
  const parts = [];
  let last = 0;
  for (const [s, e] of ranges) {
    if (s > last) parts.push(<Fragment key={`t${last}`}>{text.slice(last, s)}</Fragment>);
    parts.push(
      <mark key={`m${s}`} className="rounded-[2px] bg-brand-tint px-px font-medium text-brand [box-decoration-break:clone]">
        {text.slice(s, e)}
      </mark>,
    );
    last = e;
  }
  if (last < text.length) parts.push(<Fragment key={`t${last}`}>{text.slice(last)}</Fragment>);
  return <>{parts}</>;
}

/** "vector #2 · full-text #1"; null when the row carries neither rank. */
export function rankText(chunk: Pick<KbChunk, "vector_rank" | "fulltext_rank">): string | null {
  const parts: string[] = [];
  if (chunk.vector_rank != null) parts.push(`vector #${chunk.vector_rank}`);
  if (chunk.fulltext_rank != null) parts.push(`full-text #${chunk.fulltext_rank}`);
  return parts.length ? parts.join(" · ") : null;
}

/** Who split the query: SingleStore itself, the local SQLite stand-in, a Python fallback, or the mock. */
export function AnalyzerLabel({ analyzer }: { analyzer?: string | null }) {
  if (!analyzer) return null;
  if (analyzer === "mock") return <SimulatedTag label="Mock analyzer" />;
  const text =
    analyzer === "singlestore"
      ? "SingleStore ANALYZE FULLTEXT"
      : analyzer === "sqlite_fts5"
        ? "SQLite FTS5 · local stand-in for SingleStore ANALYZE FULLTEXT"
        : analyzer.startsWith("python")
          ? `Python tokenizer${analyzer.slice("python".length)}`
          : analyzer;
  return (
    <span className="text-caption text-muted-foreground" title={analyzer}>
      {text}
    </span>
  );
}

/** The query's index tokens as chips. A token that no row shown holds is muted. */
export function QueryTokens({ terms, analyzer, chunks }: { terms: readonly string[]; analyzer?: string | null; chunks: readonly KbChunk[] }) {
  const held = new Set(chunks.flatMap((c) => c.matched_terms ?? []));
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-caption font-medium text-muted-foreground">Query tokens</span>
      {terms.length ? (
        <ul className="flex flex-wrap gap-1" aria-label="Query tokens">
          {terms.map((t) => (
            <li
              key={t}
              title={held.has(t) ? "Found in at least one row below" : "In no row below"}
              className={cn(
                "rounded-sm border px-1.5 py-0.5 font-mono text-caption",
                held.has(t) ? "border-brand/30 bg-brand-tint text-brand" : "border-border bg-surface text-muted-foreground",
              )}
            >
              {t}
            </li>
          ))}
        </ul>
      ) : (
        <span className="text-caption text-muted-foreground">none</span>
      )}
      <span className="ml-auto">
        <AnalyzerLabel analyzer={analyzer} />
      </span>
    </div>
  );
}

/** One line under a row: the query tokens it holds (some may sit in its title or rules, outside the text shown). */
export function MatchedTermsLine({ chunk, className }: { chunk: KbChunk; className?: string }) {
  const terms = chunk.matched_terms ?? [];
  if (!terms.length) {
    if (chunk.vector_rank == null) return null;
    return <p className={cn("text-caption text-muted-foreground", className)}>No query token in this row: it came from the vector half.</p>;
  }
  return (
    <p className={cn("text-caption text-muted-foreground", className)}>
      matched <span className="font-mono text-foreground">{terms.join(" · ")}</span>
    </p>
  );
}
