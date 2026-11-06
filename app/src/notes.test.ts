import {describe,it,expect} from 'vitest';
import {mergeNotes,parseNotes,serializeNotes} from './notes';
const n={id:'a',book:'bcbooks:gen',chapter:1,start:1,end:2,text:'test',updated:'2026-10-29T00:00:00Z'};
describe('private notes',()=>{
  // what_bug_this_catches: malformed imports or duplicate IDs cannot overwrite existing notes.
  it('validates schema and merges without replacing existing IDs',()=>{
    expect(parseNotes({version:1,notes:[n]})).toEqual([n]);
    expect(()=>parseNotes({version:1,notes:[n,n]})).toThrow();
    expect(()=>parseNotes({version:1,notes:[{...n,end:0}]})).toThrow();
    expect(()=>serializeNotes([{...n,end:10000}])).toThrow();
    expect(parseNotes(JSON.parse(serializeNotes([n])))).toEqual([n]);
    expect(()=>serializeNotes(Array.from({length:101},(_,i)=>({...n,id:String(i),text:'x'.repeat(50000)})))).toThrow();
    const result=mergeNotes([n],[{...n,text:'different'},{...n,id:'b'}]);
    expect(result.notes).toEqual([n,{...n,id:'b'}]);expect(result.conflicts).toBe(1);expect(result.skipped).toBe(0);
  });
});
