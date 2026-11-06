import type {Passage} from './domain';
export type Note = { id:string; book:string; chapter:number; start:number; end:number; text:string; updated:string };
export const NOTE_KEY='cg-notes-v1';
export const MAX_BACKUP_BYTES=5_000_000;
const validInt=(n:unknown)=>Number.isInteger(n) && Number(n)>0 && Number(n)<10000;
export function parseNotes(value:unknown):Note[] {
  if(!value || typeof value!=='object' || Array.isArray(value)) throw Error('Invalid notes file');
  const doc=value as {version?:unknown;notes?:unknown};
  if(doc.version!==1 || !Array.isArray(doc.notes) || doc.notes.length>10000) throw Error('Unsupported notes format');
  const ids=new Set<string>();
  return doc.notes.map((n:unknown)=>{
    if(!n || typeof n!=='object' || Array.isArray(n)) throw Error('Invalid note');
    const x=n as Note;
    if(typeof x.id!=='string' || !x.id || x.id.length>100 || ids.has(x.id) || typeof x.book!=='string' || !x.book || x.book.length>120 || !validInt(x.chapter) || !validInt(x.start) || !validInt(x.end) || x.end<x.start || typeof x.text!=='string' || !x.text.trim() || x.text.length>50000 || typeof x.updated!=='string' || !Number.isFinite(Date.parse(x.updated))) throw Error('Invalid note fields');
    ids.add(x.id);return {id:x.id,book:x.book,chapter:x.chapter,start:x.start,end:x.end,text:x.text,updated:x.updated};
  });
}
export function mergeNotes(existing:Note[], incoming:Note[]):{notes:Note[];added:number;skipped:number;conflicts:number} {
  const byId=new Map(existing.map(n=>[n.id,n])); const added=incoming.filter(n=>!byId.has(n.id));
  const conflicts=incoming.filter(n=>byId.has(n.id) && JSON.stringify(byId.get(n.id))!==JSON.stringify(n)).length;
  return {notes:[...existing,...added],added:added.length,skipped:incoming.length-added.length-conflicts,conflicts};
}
export function serializeNotes(notes:Note[]):string {
  const doc={version:1,notes}; parseNotes(doc);
  const raw=JSON.stringify(doc);
  if(new TextEncoder().encode(raw).length>MAX_BACKUP_BYTES) throw Error('Notes exceed backup size limit');
  return raw;
}
export function anchor(p:Passage){return {book:p.book,chapter:p.chapter,start:p.verse,end:p.verse};}
