import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it, vi} from 'vitest';
import {SourceToken, sourceLanguage} from './SourceToken';

describe('OSHB token language', () => {
  it('uses source morphology without guessing missing or unknown codes', () => {
    expect(sourceLanguage('HNcmsa')).toBe('Hebrew');
    expect(sourceLanguage('ANp')).toBe('Aramaic');
    expect(sourceLanguage(null)).toBe('Unspecified');
    expect(sourceLanguage('X')).toBe('Unspecified');
  });
  it('labels and renders mixed-language tokens without inventing lemma links', () => {
    const render=(morphology:string|null,lemma:string)=>renderToStaticMarkup(<SourceToken token={{token_id:'x', text:'אב', lemma, morphology}} lookup={vi.fn()}/>);
    const hebrew=render('HN','7225');
    expect(hebrew).toContain('lang="he"');
    expect(hebrew).toContain('Hebrew (source morphology)');
    expect(hebrew).toContain('Look up H7225');
    const aramaic=render('ANp','3026 a');
    expect(aramaic).toContain('lang="arc"');
    expect(aramaic).toContain('Aramaic (source morphology)');
    expect(aramaic).toContain('3026 a');
    expect(aramaic).not.toContain('Look up');
    const unknown=render(null,'7225');
    expect(unknown).toContain('Unspecified (source morphology)');
    expect(unknown).not.toContain('lang=');
    expect(unknown).not.toContain('Look up');
  });
});
