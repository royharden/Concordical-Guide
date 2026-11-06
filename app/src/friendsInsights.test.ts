import {afterEach,describe,expect,it,vi} from 'vitest';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {FriendsInsights} from './FriendsInsightsPane';
import {demoPosts,mapPassage,mapReaderRange,matchingInsights,overlaps, type DemoPost} from './friendsInsights';

const point=(chapter:number,verse:number)=>({chapter,verse});
const map=(book:string,a:number,b:number,c:number,d:number,edition:'kjv'|'webp'|'standard-works'='kjv')=>mapReaderRange(book,point(a,b),point(c,d),edition);
afterEach(()=>vi.unstubAllGlobals());
describe('fictional insights reference contract',()=>{
  it('maps only explicit versioned books and edition-specific valid bounds',()=>{
    expect(map('bcbooks:gen',1,1,2,25)).toMatchObject({workId:'bible',bookId:'genesis',mappingVersion:'cg-demo-reference-v1'});
    expect(map('bcbooks:john',1,1,1,5)?.bookId).toBe('john');
    expect(map('bcbooks:1-ne',1,1,1,3,'standard-works')?.workId).toBe('bom');
    for(const invalid of [map('bcbooks:gen',1,1,1,1,'webp'),map('bcbooks:gen',2,26,2,26),map('bcbooks:gen',3,1,3,1),map('bcbooks:gen',2,1,1,31),map('unknown',1,1,1,1)])expect(invalid).toBeNull();
  });
  it('matches inclusive cross-chapter boundaries without widening',()=>{
    const a=demoPosts[0].anchors[0];
    for(const p of [[1,30],[1,31],[2,1],[2,2]])expect(overlaps(a,map('bcbooks:gen',p[0],p[1],p[0],p[1])!)).toBe(true);
    expect(overlaps(a,map('bcbooks:gen',2,3,2,3)!)).toBe(false);
    expect(overlaps(a,map('bcbooks:john',1,30,1,30)!)).toBe(false);
    expect(overlaps(a,map('bcbooks:1-ne',1,2,1,2,'standard-works')!)).toBe(false);
  });
  it('returns one post and only the group matching the selected work',()=>{
    const context=mapPassage({book:'bcbooks:1-ne',chapter:1,verse:2},'standard-works')!;
    const matches=matchingInsights(demoPosts,['Maya'],[],context);
    expect(matches).toHaveLength(1);expect(matches[0].matched).toHaveLength(1);expect(matches[0].matched[0].workId).toBe('bom');
  });
  it('excludes drafts, non-followed and blocked posts',()=>{
    const context=map('bcbooks:gen',1,31,1,31)!;
    const draft:DemoPost={...demoPosts[0],id:'draft',state:'draft'};
    expect(matchingInsights([...demoPosts,draft],['Maya'],[],context).map(x=>x.post.id)).toEqual(['example-maya']);
    expect(matchingInsights(demoPosts,[],[],context)).toEqual([]);
    expect(matchingInsights(demoPosts,['Maya'],['Maya'],context)).toEqual([]);
  });
  it('renders the pane without reading notes, storage or network',()=>{
    const getItem=vi.fn();const setItem=vi.fn();const fetch=vi.fn();vi.stubGlobal('localStorage',{getItem,setItem});vi.stubGlobal('fetch',fetch);
    const html=renderToStaticMarkup(createElement(FriendsInsights,{passage:{book:'bcbooks:gen',chapter:1,verse:31},edition:'kjv'}));
    expect(html).toContain('FICTIONAL LOCAL DEMO');expect(html).toContain('Maya');expect(html).not.toContain('1-nephi');
    expect(getItem).not.toHaveBeenCalled();expect(setItem).not.toHaveBeenCalled();expect(fetch).not.toHaveBeenCalled();
  });
});
