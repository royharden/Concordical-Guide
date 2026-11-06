// Synthetic reference catalog, not a production versification authority.
export const catalog: Record<string, Record<string, number[]>> = { bible: { genesis: [31,25], john: [51,25] }, bom: { '1-nephi': [20,24] } };
export type Anchor = {work:string; book:string; start:[number,number]; end:[number,number]};
export type Post = {id:string; author:string; text:string; state:'draft'|'public'; anchors:Anchor[]};
export type State = {version:1; following:string[]; blocked:string[]; posts:Post[]};
const point = (p:[number,number]) => p[0]*1000+p[1];
export function validAnchor(a:Anchor):boolean { const books=Object.hasOwn(catalog,a?.work)?catalog[a.work]:undefined; const chapters=books && Object.hasOwn(books,a?.book)?books[a.book]:undefined; return !!chapters && Array.isArray(a.start) && Array.isArray(a.end) && [a.start,a.end].every(p=>p.length===2 && Number.isInteger(p[0]) && Number.isInteger(p[1]) && p[0]>0 && p[0]<=chapters.length && p[1]>0 && p[1]<=chapters[p[0]-1]) && point(a.start)<=point(a.end); }
export function normalize(anchors:Anchor[]):Anchor[] { if(!Array.isArray(anchors)||!anchors.length||anchors.some(a=>!validAnchor(a))) throw Error('Choose at least one valid, ordered passage from the demo catalog.'); const unique=new Map<string,Anchor>(); for(const a of anchors) { const x:Anchor={work:a.work,book:a.book,start:[...a.start],end:[...a.end]}; unique.set(JSON.stringify(x),x); } return [...unique.values()].sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))); }
export function overlaps(a:Anchor,b:Anchor):boolean { return validAnchor(a)&&validAnchor(b)&&a.work===b.work&&a.book===b.book&&point(a.start)<=point(b.end)&&point(b.start)<=point(a.end); }
export function visible(s:State, context?:Anchor):Post[] { return s.posts.filter(p=>p.state==='public'&&s.following.includes(p.author)&&!s.blocked.includes(p.author)&&(!context||p.anchors.some(a=>overlaps(a,context)))); }
export function validateState(v:unknown):State {
 const s=v as State;
 if(!s||s.version!==1||!Array.isArray(s.following)||!Array.isArray(s.blocked)||!Array.isArray(s.posts)||s.posts.length>5000) throw Error('Invalid demo save.');
 const names=(xs:unknown[])=>{if(xs.length>1000||!xs.every(x=>typeof x==='string'&&/^[a-zA-Z0-9-]{1,80}$/.test(x))) throw Error('Invalid author list.'); return [...new Set(xs as string[])].sort();};
 const ids=new Set<string>(); const posts=s.posts.map(p=>{
  if(!p||typeof p.id!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(p.id)||ids.has(p.id)||typeof p.author!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(p.author)||typeof p.text!=='string'||!p.text.trim()||p.text.length>2000||!['draft','public'].includes(p.state)||!Array.isArray(p.anchors)||p.anchors.length>100) throw Error('Invalid post in demo save.');
  ids.add(p.id); return {id:p.id,author:p.author,text:p.text,state:p.state,anchors:normalize(p.anchors)};
 }); return {version:1,following:names(s.following),blocked:names(s.blocked),posts};
}
export type Backup = {format:'cg-social-lab'; version:1; data:State};
export type ImportPreview = {incoming:State; baseline:string; added:number; identical:number; conflicts:number; drafts:number; published:number};
export function exportBackup(state:State):Backup {return {format:'cg-social-lab',version:1,data:validateState(state)}}
export function previewImport(value:unknown,current:State):ImportPreview {
 const candidate=value as Partial<Backup>; let data:unknown;
 if(candidate?.format==='cg-social-lab'){if(candidate.version!==1) throw Error('Unsupported backup version.');data=candidate.data;}
 else if(candidate && !('format' in candidate) && candidate.version===1) data=value; // Legacy raw state.
 else throw Error('Unrecognized backup format.');
 const incoming=validateState(data), existing=validateState(current), byId=new Map(existing.posts.map(p=>[p.id,p])); let added=0,identical=0,conflicts=0;
 for(const p of incoming.posts){const old=byId.get(p.id);if(!old)added++;else if(JSON.stringify(old)===JSON.stringify(p))identical++;else conflicts++;}
 return {incoming,baseline:JSON.stringify(existing),added,identical,conflicts,drafts:incoming.posts.filter(p=>p.state==='draft').length,published:incoming.posts.filter(p=>p.state==='public').length};
}
export function applyImport(preview:ImportPreview,current:State,mode:'merge'|'replace',persisted:State=current):State {
 const existing=validateState(current);if(JSON.stringify(validateState(persisted))!==preview.baseline||JSON.stringify(existing)!==preview.baseline) throw Error('Local data changed since preview. Select the file again.');
 const incoming=validateState(preview.incoming);if(mode==='replace')return incoming;
 if(mode!=='merge') throw Error('Invalid import choice.');
 const ids=new Set(existing.posts.map(p=>p.id));return validateState({version:1,following:[...existing.following,...incoming.following],blocked:[...existing.blocked,...incoming.blocked],posts:[...existing.posts,...incoming.posts.filter(p=>!ids.has(p.id))]});
}
export function label(a:Anchor):string { return `${a.work} / ${a.book} ${a.start[0]}:${a.start[1]}–${a.end[0]}:${a.end[1]}`; }
export function link(a:Anchor):string {return `#passage=${encodeURIComponent(`${a.work}/${a.book}/${a.start.join(':')}-${a.end.join(':')}`)}`;}

export function writeState(storage:Pick<Storage,'getItem'|'setItem'>,key:string,expected:string|null,next:State):string {
 if(storage.getItem(key)!==expected) throw Error('Local data changed in another tab. Reload before saving.');
 const raw=JSON.stringify(validateState(next));storage.setItem(key,raw);return raw;
}
