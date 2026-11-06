import React from 'react';
import {candidateHebrewId} from './hebrewLemma';
import {HebrewToken} from './hebrewRequest';

// OSHB's raw morphology prefix is source metadata, not a linguistic adjudication.
export function sourceLanguage(morphology:string|null):'Hebrew'|'Aramaic'|'Unspecified' {
  if (morphology?.startsWith('H')) return 'Hebrew';
  if (morphology?.startsWith('A')) return 'Aramaic';
  return 'Unspecified';
}

export function SourceToken({token,lookup}:{token:HebrewToken;lookup:(id:string)=>void}) {
  const language=sourceLanguage(token.morphology);
  const id=language==='Hebrew' ? candidateHebrewId(token.lemma) : null;
  const lang=language==='Hebrew' ? 'he' : language==='Aramaic' ? 'arc' : undefined;
  return <span className="hebrew-token"><bdi dir="rtl" lang={lang}>{token.text}</bdi>
    <small dir="ltr">{language} (source morphology) · {token.lemma || 'no lemma'} · {token.morphology || 'no morphology'}</small>
    {id && <button onClick={()=>lookup(id)}>Look up {id}</button>}
  </span>;
}
