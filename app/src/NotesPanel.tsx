import React,{useEffect,useRef,useState} from 'react';
import type {Book,Passage} from './domain';
import {anchor,mergeNotes,MAX_BACKUP_BYTES,NOTE_KEY,Note,parseNotes,serializeNotes} from './notes';

export function Notes({passage,books}:{passage:Passage;books:Book[]}){
  const [notes,setNotes]=useState<Note[]>([]); const [ready,setReady]=useState(false); const [status,setStatus]=useState('');
  const [backup,setBackup]=useState('');
  const [backupUrl,setBackupUrl]=useState('');
  const [busy,setBusy]=useState(false); const busyRef=useRef(false);
  const [text,setText]=useState(''); const [draft,setDraft]=useState<ReturnType<typeof anchor>|null>(null); const [editing,setEditing]=useState<string|null>(null);
  const original=useRef<string|null>(null);
  useEffect(()=>()=>{if(backupUrl)URL.revokeObjectURL(backupUrl);},[backupUrl]);
  useEffect(()=>{try{const raw=localStorage.getItem(NOTE_KEY);original.current=raw;setNotes(raw?parseNotes(JSON.parse(raw)):[]);setReady(true);}catch{setStatus('Notes storage could not be read. Your existing data was not changed.');}},[]);
  useEffect(()=>{const changed=(e:StorageEvent)=>{if(e.key===NOTE_KEY || e.key===null){setBackup('');setBackupUrl('');setStatus('Notes changed in another window. Copy any draft before reloading.');}};window.addEventListener('storage',changed);return ()=>window.removeEventListener('storage',changed);},[]);
  async function persist(next:Note[],reserved=false){if(busyRef.current && !reserved)return false;if(!reserved){busyRef.current=true;setBusy(true);}try{if(!navigator.locks)throw Error('Lock unavailable');return await navigator.locks.request('cg-notes-write-v1',()=>{if(localStorage.getItem(NOTE_KEY)!==original.current){setStatus('Notes changed in another window. Your draft is intact; copy it before reloading.');return false;}const raw=serializeNotes(next);localStorage.setItem(NOTE_KEY,raw);original.current=raw;setNotes(next);setBackup('');setBackupUrl('');return true;});}catch{setStatus('Could not save: check the passage range, storage space, and browser lock support. Your draft remains here.');return false;}finally{if(!reserved){busyRef.current=false;setBusy(false);}}}
  const label=(a:{book:string;chapter:number;start:number;end:number})=>`${books.find(b=>b.id===a.book)?.title || a.book} ${a.chapter}:${a.start}${a.end!==a.start?`–${a.end}`:''}`;
  async function save(e:React.FormEvent){e.preventDefault();if(!draft || !text.trim() || !ready)return;
    const note:Note={...draft,id:editing || crypto.randomUUID(),text,updated:new Date().toISOString()};
    const next=editing?notes.map(n=>n.id===editing?note:n):[...notes,note];
    if(await persist(next)){setText('');setDraft(null);setEditing(null);setStatus('Note saved on this device.');}}
  function edit(n:Note){if(draft && !window.confirm('Discard the current draft and edit this note?'))return;setEditing(n.id);setDraft({book:n.book,chapter:n.chapter,start:n.start,end:n.end});setText(n.text);setStatus('Editing note.');}
  async function remove(id:string){if(!window.confirm('Delete this note?'))return;if(await persist(notes.filter(n=>n.id!==id))){if(editing===id){setEditing(null);setDraft(null);setText('');}setStatus('Note deleted.');}}
  async function exportNotes(){if(busyRef.current)return;busyRef.current=true;setBusy(true);try{if(!navigator.locks)throw Error('Lock unavailable');const raw=await navigator.locks.request('cg-notes-write-v1',()=>{const stored=localStorage.getItem(NOTE_KEY);return serializeNotes(stored?parseNotes(JSON.parse(stored)):[]);});setBackup(raw);setBackupUrl(URL.createObjectURL(new Blob([raw],{type:'application/json'})));setStatus('Backup ready. Download JSON or copy the backup text below.');}catch{setStatus('Notes cannot be exported because storage or browser locks are unavailable, or stored data is invalid or too large.');}finally{busyRef.current=false;setBusy(false);}}
  async function importNotes(e:React.ChangeEvent<HTMLInputElement>){const f=e.target.files?.[0];e.target.value='';if(!f || busyRef.current)return;busyRef.current=true;setBusy(true);try{if(f.size>MAX_BACKUP_BYTES)throw Error();const incoming=parseNotes(JSON.parse(await f.text()));const merged=mergeNotes(notes,incoming);if(await persist(merged.notes,true))setStatus(`Imported ${merged.added}; ${merged.skipped} identical and ${merged.conflicts} conflicting IDs skipped. Keep the backup to recover conflicts.`);}catch{setStatus('Import rejected: invalid or unsupported notes file. Existing notes were not changed.');}finally{busyRef.current=false;setBusy(false);}}
  const current=notes.filter(n=>n.book===passage.book && n.chapter===passage.chapter && n.start<=passage.verse && n.end>=passage.verse);
  return <section className="notes"><h3>Quick notes</h3><p>Saved only in this browser. Export a backup to keep your notes.</p>
    <form onSubmit={save}><label>Note for {draft?label(draft):label(anchor(passage))}<textarea disabled={busy} maxLength={50000} value={text} onChange={e=>{if(!draft && e.target.value)setDraft(anchor(passage));setText(e.target.value);}} placeholder="Write a thought about this passage" /></label>
      {draft && <label>Through verse<input disabled={busy} type="number" min={draft.start} max={9999} value={draft.end} onChange={e=>setDraft({...draft,end:Number(e.target.value)})}/></label>}
      <button type="submit" disabled={busy || !ready || !text.trim() || !draft || !Number.isInteger(draft.end) || draft.end<draft.start || draft.end>=10000}>Save note</button>
      {draft && <button type="button" disabled={busy} onClick={()=>{setDraft(null);setText('');setEditing(null);}}>Cancel draft</button>}</form>
    <div className="note-actions"><button onClick={exportNotes} disabled={!ready || busy}>Export notes</button><label>Import notes<input type="file" accept="application/json,.json" disabled={!ready || busy} onChange={importNotes}/></label></div>
    {backup && <div><a href={backupUrl} download="cg-notes.json">Download JSON</a><label>Backup text (private)<textarea readOnly value={backup} onFocus={e=>e.currentTarget.select()}/></label><button type="button" onClick={()=>{setBackup('');setBackupUrl('');}}>Hide backup text</button></div>}
    {status && <p role="status">{status}</p>}{current.map(n=><article key={n.id}><strong>{label(n)}</strong><p className="note-text">{n.text}</p><button disabled={busy} onClick={()=>edit(n)}>Edit</button><button disabled={busy} onClick={()=>remove(n.id)}>Delete</button></article>)}
  </section>;
}
