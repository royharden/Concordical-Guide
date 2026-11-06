import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Book, Message, Passage, popupStatus, receive, Verse, verseAvailable} from './domain';
import {Notes} from './NotesPanel';
import {WordStudy} from './WordStudy';
import {FriendsInsights} from './FriendsInsightsPane';
import './style.css';

const initial: Passage = {book:'bcbooks:gen',chapter:1,verse:1};
const windowId = crypto.randomUUID();
const params = new URLSearchParams(location.search);
const popout = params.get('view') === 'comparison';
const session = params.get('session') || sessionStorage.getItem('cg-reader-session') || crypto.randomUUID();
if (!popout) sessionStorage.setItem('cg-reader-session',session);
const editionLabel = (modern:boolean) => modern ? 'World English Bible — Protestant' : 'KJV (LDS source)';

function App() {
  const [books,setBooks] = useState<Book[]>([]);
  const [passage,setPassage] = useState<Passage>(initial);
  const [chapterData,setChapterData] = useState<{book:string;chapter:number;verses:Verse[]} | null>(null);
  const [webData,setWebData] = useState<{book:string;chapter:number;verses:Verse[]} | null>(null);
  const [webError,setWebError] = useState('');
  const [placeholder,setPlaceholder] = useState(popout && params.get('edition') !== 'kjv');
  const [compare,setCompare] = useState(()=>{try{return localStorage.getItem('cg-compare-visible')!=='false';}catch{return true;}});
  const [status,setStatus] = useState('');
  const [wordStudy,setWordStudy] = useState(false);
  const [friendsInsights,setFriendsInsights] = useState(false);
  const [search,setSearch] = useState('');
  const [results,setResults] = useState<Array<{book_id:string;chapter_number:number;verse_number:number;reference:string}>>([]);
  const [error,setError] = useState('');
  const channel = useRef<BroadcastChannel | null>(null);
  const passageRef = useRef(passage);
  const popup = useRef<Window | null>(null);
  const userScrollUntil = useRef(0);
  const scrollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const active = books.find(b=>b.id===passage.book);
  const verses = chapterData?.book===passage.book && chapterData.chapter===passage.chapter ? chapterData.verses : [];
  const webVerses = webData?.book===passage.book && webData.chapter===passage.chapter ? webData.verses : [];
  const isBible = active?.volume_slug === 'ot' || active?.volume_slug === 'nt';
  const verseNumbers = [...new Set([...verses.map(v=>v.verse),...(isBible ? webVerses.map(v=>v.verse) : [])])].sort((a,b)=>a-b);
  passageRef.current = passage;

  useEffect(()=>{ fetch('/api/catalog').then(r=>{if(!r.ok) throw Error('Catalog unavailable'); return r.json()}).then(setBooks).catch(()=>setError('Could not load the local scripture database.')); },[]);
  useEffect(()=>{
    const controller = new AbortController();
    fetch(`/api/chapter?book=${encodeURIComponent(passage.book)}&chapter=${passage.chapter}`,{signal:controller.signal})
      .then(r=>{if(!r.ok) throw Error(); return r.json()}).then(data=>setChapterData({book:passage.book,chapter:passage.chapter,verses:data})).catch(e=>{if(e.name!=='AbortError') setError('Could not load this chapter.');});
    return ()=>controller.abort();
  },[passage.book,passage.chapter]);
  useEffect(()=>{
    if(!isBible) return;
    const controller=new AbortController(); setWebError('');
    fetch(`/api/chapter?edition=webp&book=${encodeURIComponent(passage.book)}&chapter=${passage.chapter}`,{signal:controller.signal})
      .then(r=>{if(!r.ok) throw Error();return r.json()}).then(data=>setWebData({book:passage.book,chapter:passage.chapter,verses:data}))
      .catch(e=>{if(e.name!=='AbortError') setWebError('World English Bible data is unavailable.');});
    return ()=>controller.abort();
  },[passage.book,passage.chapter,isBible]);
  useEffect(()=>{
    const c = new BroadcastChannel(`cg-reader-${session}`); channel.current=c;
    c.onmessage = (event:MessageEvent<Message>)=>{
      const m=event.data;
      if(m?.kind==='hello' && m.sender!==windowId) c.postMessage({kind:'passage',sender:windowId,passage:passageRef.current} satisfies Message);
      const next = m && receive(passageRef.current,m,windowId);
      if(next) { if(scrollTimer.current) clearTimeout(scrollTimer.current);userScrollUntil.current=0; passageRef.current=next; setPassage(next); }
    };
    c.postMessage({kind:'hello',sender:windowId} satisfies Message);
    return ()=>{c.close();channel.current=null;};
  },[]);
  useEffect(()=>{
    const timer = setInterval(()=>{ if(popup.current?.closed){popup.current=null;setStatus('Comparison window closed. You can reopen it.');} },1000);
    return ()=>clearInterval(timer);
  },[]);
  useEffect(()=>{document.querySelectorAll<HTMLElement>(`.verse-list [data-verse="${passage.verse}"]`).forEach(el=>{const pane=el.parentElement;if(!pane)return;const item=el.getBoundingClientRect(),box=pane.getBoundingClientRect();if(item.top<box.top)pane.scrollTop+=item.top-box.top;else if(item.bottom>box.bottom)pane.scrollTop+=item.bottom-box.bottom;});},[passage,verses,webVerses,compare]);
  function navigate(next:Passage){ if(scrollTimer.current) clearTimeout(scrollTimer.current);userScrollUntil.current=0;passageRef.current=next;setPassage(next);channel.current?.postMessage({kind:'passage',sender:windowId,passage:next} satisfies Message); }
  function markUserScroll(){userScrollUntil.current=Date.now()+1000;}
  function onScroll(e:React.UIEvent<HTMLDivElement>){
    if(Date.now()>userScrollUntil.current) return;
    const pane=e.currentTarget;
    if(scrollTimer.current) clearTimeout(scrollTimer.current);
    scrollTimer.current=setTimeout(()=>{
      const top=pane.getBoundingClientRect().top;
      const visible=Array.from(pane.querySelectorAll<HTMLElement>('[data-verse]')).find(el=>el.getBoundingClientRect().bottom>top+5);
      const verse=Number(visible?.dataset.verse);
      if(verse && verse!==passageRef.current.verse) navigate({...passageRef.current,verse});
    },120);
  }
  function openPopup(){
    if(popup.current && !popup.current.closed){popup.current.focus();return;}
    popup.current=window.open(`/?view=comparison&session=${encodeURIComponent(session)}&edition=${placeholder?'kjv':'webp'}`,`cg-${session}`,'popup,width=650,height=850');
    setStatus(popupStatus(Boolean(popup.current)));
  }
  function toggleCompare(){setCompare(current=>{const next=!current;try{localStorage.setItem('cg-compare-visible',String(next));}catch{/* preference is optional */}return next;});}
  async function runSearch(e:React.FormEvent){ e.preventDefault(); try {const r=await fetch(`/api/search?q=${encodeURIComponent(search)}`);if(!r.ok) throw Error();setResults(await r.json());}catch{setError('Search is unavailable.');} }
  function pane(alt:boolean){const shown = isBible && alt ? webVerses : verses; const loaded = isBible && alt ? webData?.book===passage.book && webData.chapter===passage.chapter : chapterData?.book===passage.book && chapterData.chapter===passage.chapter; return <section className="reading" aria-label={isBible ? editionLabel(alt) : 'LDS standard works — local source'}>
    <div className="pane-header"><span>{isBible ? editionLabel(alt) : 'LDS standard works — local source'}</span><span>{active?.title} {passage.chapter}</span></div>
    {isBible && alt && <p className="notice">WEB Protestant · <a href="https://ebible.org/engwebp/" target="_blank" rel="noreferrer">eBible.org</a> · public domain. Matching is by book, chapter and verse number; versification may differ. {webError}</p>}
    {loaded && !verseAvailable(shown,passage.verse) && <p className="notice">Verse {passage.verse} is unavailable in this edition.</p>}
    <div className="verse-list" onScroll={onScroll} onWheel={markUserScroll} onTouchMove={markUserScroll} onPointerDown={markUserScroll} onKeyDown={markUserScroll}>{shown.map(v=><button className={`verse ${passage.verse===v.verse?'selected':''}`} data-verse={v.verse} key={v.verse} onClick={()=>navigate({...passage,verse:v.verse})}><span>{v.verse}</span>{v.text}</button>)}</div>
  </section>}
  return <><header><div><small>PERSONAL STUDY WORKSPACE</small><h1>Concordical Guide</h1></div><div className="badge">Private local preview</div></header>
    <main><aside><h2>Scriptures</h2><label>Book<select value={passage.book} onChange={e=>navigate({book:e.target.value,chapter:1,verse:1})}>{books.map(b=><option key={b.id} value={b.id}>{b.volume} · {b.title}</option>)}</select></label>
      <div className="controls"><label>Chapter<select value={passage.chapter} onChange={e=>navigate({...passage,chapter:Number(e.target.value),verse:1})}>{Array.from({length:active?.chapters||0},(_,i)=><option key={i+1}>{i+1}</option>)}</select></label>
      <label>Verse<select value={passage.verse} onChange={e=>navigate({...passage,verse:Number(e.target.value)})}>{!verseNumbers.includes(passage.verse)&&<option value={passage.verse}>{passage.verse} (unavailable)</option>}{verseNumbers.map(v=><option key={v}>{v}</option>)}</select></label></div>
      <form onSubmit={runSearch}><label>Search text<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search a phrase" /></label><button type="submit">Search</button></form>
      {results.length>0 && <ul>{results.map(r=><li key={r.reference}><button className="link" onClick={()=>navigate({book:r.book_id,chapter:r.chapter_number,verse:r.verse_number})}>{r.reference}</button></li>)}</ul>}
      <div className="resources"><h3>Study helps</h3><a href="https://www.churchofjesuschrist.org/study/scriptures?lang=eng" target="_blank" rel="noreferrer">Church scriptures &amp; study helps ↗</a><p>Verse-linked concordance and embedded Church study helps are not yet available. Quick notes appear below the reader.</p></div></aside>
      <div className="workspace"><div className="toolbar"><div><small>READING</small><h2>{active?.title || 'Scriptures'} <span>{passage.chapter}:{passage.verse}</span></h2><p className="edition-current">{isBible ? `Main edition: ${editionLabel(placeholder)}` : 'Bible edition comparison is available in the Old and New Testaments.'}</p></div>{isBible && <div className="actions"><button onClick={()=>setPlaceholder(!placeholder)}>Switch main to {placeholder?'KJV':'WEB'}</button>{!popout && <><button onClick={toggleCompare}>{compare?'Hide side-by-side comparison':'Compare side by side'}</button><button onClick={openPopup}>Open comparison window</button></>}</div>}</div>
      {!popout && <div className="actions study-toggle"><button aria-expanded={wordStudy} aria-controls="word-study-panel" onClick={()=>setWordStudy(!wordStudy)}>{wordStudy?'Hide word study':'Open word study'}</button><button aria-expanded={friendsInsights} aria-controls="friends-insights-panel" onClick={()=>setFriendsInsights(!friendsInsights)}>{friendsInsights?'Hide Friends’ Insights':'Show Friends’ Insights'}</button></div>}
      {status && <p role="status" className="notice">{status}</p>}{error&&<p role="alert">{error}</p>}
      <div className={wordStudy && !popout?'study-layout':''}>
      <div className={`panes ${isBible && compare && !popout?'split':''}`}>{pane(placeholder)}{isBible && compare && !popout && pane(!placeholder)}</div>
      {wordStudy && !popout && <div id="word-study-panel"><WordStudy isBible={Boolean(isBible)} passage={passage} edition={placeholder?'webp':'kjv'}/></div>}</div>
      {friendsInsights && !popout && <div id="friends-insights-panel"><FriendsInsights passage={passage} edition={isBible?(placeholder?'webp':'kjv'):'standard-works'}/></div>}
      {!popout && <Notes passage={passage} books={books}/>}
      <footer>Local source: bcbooks scripture JSON. Text rights and redistribution remain under review. This preview is for private study; do not publish it.</footer></div></main></>;
}
createRoot(document.getElementById('root')!).render(<App/>);
