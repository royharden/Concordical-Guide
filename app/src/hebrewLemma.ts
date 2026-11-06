// OSHB prefixes are retained in the source display; only a wholly numeric
// terminal identifier can be offered as a candidate legacy Strong's lookup.
export function candidateHebrewId(lemma:string|null):string|null {
  const match=lemma?.match(/^(?:[a-z]+\/)*([0-9]+)$/);
  return match ? `H${match[1]}` : null;
}
