export type Passage = { book: string; chapter: number; verse: number };
export type Book = { id: string; title: string; volume: string; volume_slug: string; chapters: number };
export type Verse = { verse: number; reference: string; text: string };
export type Message = { kind: 'hello' | 'passage'; sender: string; passage?: Passage };

export function samePassage(a: Passage, b: Passage): boolean {
  return a.book === b.book && a.chapter === b.chapter && a.verse === b.verse;
}
export function receive(current: Passage, message: Message, self: string): Passage | null {
  if (message.kind !== 'passage' || message.sender === self || !message.passage) return null;
  const p = message.passage;
  if (typeof p.book !== 'string' || !Number.isInteger(p.chapter) || p.chapter < 1 || !Number.isInteger(p.verse) || p.verse < 1 || samePassage(current, p)) return null;
  return p;
}
export function verseAvailable(verses: Verse[], verse: number): boolean {
  return verses.some(v => v.verse === verse);
}
export function popupStatus(opened: boolean): string {
  return opened ? 'Comparison window opened.' : 'The browser blocked the comparison window. Allow popups and try again.';
}
