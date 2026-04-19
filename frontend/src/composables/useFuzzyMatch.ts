/**
 * Lightweight fuzzy matcher: returns a score for `query` matched against
 * `target` (higher is better), or null if no match. Prefix matches score highest,
 * contiguous substring matches second, subsequence matches third.
 */
export function fuzzyScore(query: string, target: string): number | null {
  if (!query) return 0;
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  if (t === q) return 1000;
  if (t.startsWith(q)) return 900 - (t.length - q.length);
  const idx = t.indexOf(q);
  if (idx === 0) return 800;
  if (idx > 0) return 700 - idx;

  // Subsequence match: every char of q appears in t in order.
  let qi = 0;
  let lastMatchIdx = -1;
  let gap = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      if (lastMatchIdx >= 0) gap += ti - lastMatchIdx - 1;
      lastMatchIdx = ti;
      qi++;
    }
  }
  if (qi < q.length) return null;
  return Math.max(0, 500 - gap * 5 - (t.length - q.length));
}

export function fuzzyFilter<T>(
  query: string,
  items: T[],
  getKey: (item: T) => string,
): T[] {
  if (!query) return items;
  return items
    .map((item) => ({ item, score: fuzzyScore(query, getKey(item)) }))
    .filter((entry): entry is { item: T; score: number } => entry.score !== null)
    .sort((a, b) => b.score - a.score)
    .map((entry) => entry.item);
}
