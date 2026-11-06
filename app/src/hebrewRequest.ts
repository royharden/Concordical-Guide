export type HebrewToken = {token_id:string; text:string; lemma:string|null; morphology:string|null};
export type HebrewSourceSegment = {role:string;osis:string;tokens:HebrewToken[]};
export type HebrewSourcePart = {osis:string;tokens:HebrewToken[]};
export type HebrewState = {key:string;available:boolean;osis?:string;tokens:HebrewToken[];source_segments?:HebrewSourceSegment[];source_parts?:HebrewSourcePart[];adjudication_id?:string;error?:boolean};

// Cleanup invalidates this selection even if the fetch or JSON body ignores abort.
export function startHebrewRequest(url:string, key:string, publish:(value:HebrewState)=>void, fetcher:typeof fetch=fetch) {
  const controller = new AbortController();
  let current = true;
  fetcher(url,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error();return r.json()})
    .then(data=>{if(current)publish({...data,key})}).catch(error=>{if(current && error?.name!=='AbortError')publish({key,available:false,tokens:[],error:true})});
  return ()=>{current=false;controller.abort();};
}
