import React, {useEffect, useRef, useState} from 'react';
import {latestRequest} from './latestRequest';
import {Passage} from './domain';
import {SourceToken} from './SourceToken';
import {HebrewState, startHebrewRequest} from './hebrewRequest';
type Entry = {number:string; language:string; lemma:string|null; transliteration:string|null; pronunciation:string|null; definition:string};
export function WordStudy({isBible,passage,edition}:{isBible:boolean;passage:Passage;edition:'kjv'|'webp'}) {
  const [term,setTerm]=useState(''); const [entries,setEntries]=useState<Entry[]>([]); const [message,setMessage]=useState('');
  const request = useRef(latestRequest());
  const [hebrew,setHebrew]=useState<HebrewState|null>(null);
  const [retry,setRetry]=useState(0);
  const key=`${edition}:${passage.book}:${passage.chapter}:${passage.verse}`;
  useEffect(()=>{
    if(!isBible)return;
    const query=new URLSearchParams({edition,book:passage.book,chapter:String(passage.chapter),verse:String(passage.verse)});
    return startHebrewRequest(`/api/hebrew-passage?${query}`,key,setHebrew);
  },[key,isBible,retry]);
  async function lookup(value:string) {
    const isCurrent = request.current.begin();
    if (!value.trim()) {setEntries([]);setMessage('Enter a Strong’s number, lemma, transliteration, or English gloss.');return;}
    try {const response=await fetch(`/api/word-study?q=${encodeURIComponent(value.trim())}`); if(!response.ok) throw Error(); const result:Entry[]=await response.json(); if(!isCurrent())return; setEntries(result);setMessage(result.length ? `Showing up to 30 results for “${value.trim()}”.` : 'No entries found.');}
    catch {if(!isCurrent())return;setEntries([]);setMessage('Word-study data is unavailable.');}
  }
  return <section className="word-study" aria-label="Word study"><h3>Word study</h3>
    <p>{isBible ? 'Hebrew and Aramaic source words are available for a verified KJV subset. English-word alignment is not available.' : 'Original-language Bible word study applies to the Old and New Testaments. Manual dictionary lookup remains available here.'}</p>
    {isBible && <div className="hebrew-verse"><h4>Hebrew and Aramaic source words</h4>{hebrew?.key!==key ? <p>Loading original-language source…</p> : hebrew.error ? <p role="alert">Original-language data could not be loaded. <button onClick={()=>{setHebrew(null);setRetry(retry+1)}}>Retry</button></p> : !hebrew.available ? <p>Original-language source words are unavailable for this passage and edition.</p> : <><p>OSHB {hebrew.source_parts?.length ? hebrew.source_parts.map(part=>part.osis).join(' + ') : hebrew.osis?.split('!')[0]}{hebrew.osis?.includes('!') && `, source-word span ${hebrew.osis.split('!')[1]}`} · verified KJV passage mapping. Source tokens, not English-word alignment. {!!hebrew.source_segments?.length && 'These are verse-body words; source heading material is shown separately.'} {hebrew.osis?.includes('!') && 'This is a partial source verse; the suffix identifies its source span.'}</p>{hebrew.adjudication_id && <p>{hebrew.source_parts?.length ? 'Locally adjudicated reference: the source map lists only the first part; both source parts were reviewed against the verse.' : 'Locally adjudicated reference: a source note conflicts with the source map; this mapping was reviewed against the source texts.'} Source words are not English-word alignment.</p>}{hebrew.source_parts?.length ? hebrew.source_parts.map(part=><section key={part.osis} aria-label={`Source words ${part.osis}`}><p>Source words: OSHB {part.osis}</p><div dir="rtl">{part.tokens.map(token=><SourceToken key={token.token_id} token={token} lookup={id=>{setTerm(id);void lookup(id)}} />)}</div></section>) : <div dir="rtl">{hebrew.tokens.map(token=><SourceToken key={token.token_id} token={token} lookup={id=>{setTerm(id);void lookup(id)}} />)}</div>}{hebrew.source_segments?.filter(segment=>segment.role==='source_superscription_excerpt').map(segment=><details key={segment.osis}><summary>Source superscription excerpt (not verse text)</summary><p>OSHB {segment.osis}: a portion of the source heading, shown separately from the verse body. Source words are not English-word alignment.</p><div dir="rtl">{segment.tokens.map(token=><SourceToken key={token.token_id} token={token} lookup={id=>{setTerm(id);void lookup(id)}} />)}</div></details>)}<p>Original work of the <a href="https://github.com/openscriptures/morphhb" target="_blank" rel="noreferrer">Open Scriptures Hebrew Bible</a>. CC BY 4.0 annotations; WLC base public domain. Adapted to the main source reading; alternate readings in notes, punctuation and non-word segments are not displayed. Language labels follow source morphology. Dictionary lookup omits documented lemma prefixes; suffix variants stay unlinked.</p></>}</div>}
    <form onSubmit={e=>{e.preventDefault();void lookup(term)}}><label>Strong’s number, lemma, transliteration, or gloss<input maxLength={80} value={term} onChange={e=>setTerm(e.target.value)} placeholder="e.g. H7225 or love" /></label><button type="submit">Look up word</button></form>
    <p role="status">{message}</p>
    {entries.map(entry=><article key={entry.number}><h4>{entry.number} · {entry.language}</h4><p><bdi dir="auto" lang={entry.language==='hebrew'?'he':'el'}>{entry.lemma}</bdi> {entry.transliteration && `(${entry.transliteration})`}</p><p>{entry.definition}</p></article>)}
    <p>Definitions list possible meanings, not proof of meaning in a particular passage. Source: <a href="https://github.com/mormon-documentation-project/strongs" target="_blank" rel="noreferrer">Strong’s JSON</a>, derived from OpenScriptures and Strong’s 1890 work; Unlicense.</p>
  </section>;
}
