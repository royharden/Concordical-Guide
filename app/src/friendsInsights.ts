import type {Passage} from './domain';

// This is a bounded demo contract, not an authoritative cross-edition map.
export const DEMO_MAPPING_VERSION = 'cg-demo-reference-v1';
export type Point = {chapter:number;verse:number};
export type DemoRange = {workId:'bible'|'bom';bookId:'genesis'|'john'|'1-nephi';start:Point;end:Point;mappingVersion:typeof DEMO_MAPPING_VERSION};
export type DemoPost = {id:string;author:string;text:string;state:'draft'|'public';anchors:DemoRange[]};
const catalog:Record<string,{workId:DemoRange['workId'];bookId:DemoRange['bookId'];chapters:number[];edition:'kjv'|'standard-works'}> = {
  'bcbooks:gen':{workId:'bible',bookId:'genesis',chapters:[31,25],edition:'kjv'},
  'bcbooks:john':{workId:'bible',bookId:'john',chapters:[51,25],edition:'kjv'},
  'bcbooks:1-ne':{workId:'bom',bookId:'1-nephi',chapters:[20,24],edition:'standard-works'},
};
const key=(p:Point)=>p.chapter*1000+p.verse;
export function mapReaderRange(book:string,start:Point,end:Point,edition:'kjv'|'webp'|'standard-works'):DemoRange|null {
  const entry=Object.hasOwn(catalog,book)?catalog[book]:undefined;
  if(!entry || entry.edition!==edition) return null;
  const valid=(p:Point)=>Number.isInteger(p.chapter)&&Number.isInteger(p.verse)&&p.chapter>=1&&p.chapter<=entry.chapters.length&&p.verse>=1&&p.verse<=entry.chapters[p.chapter-1];
  if(!valid(start)||!valid(end)||key(start)>key(end))return null;
  return {workId:entry.workId,bookId:entry.bookId,start:{...start},end:{...end},mappingVersion:DEMO_MAPPING_VERSION};
}
export function mapPassage(p:Passage,edition:'kjv'|'webp'|'standard-works'):DemoRange|null {
  const point={chapter:p.chapter,verse:p.verse};return mapReaderRange(p.book,point,point,edition);
}
export function overlaps(a:DemoRange,b:DemoRange):boolean {
  return a.mappingVersion===b.mappingVersion&&a.workId===b.workId&&a.bookId===b.bookId&&key(a.start)<=key(b.end)&&key(b.start)<=key(a.end);
}
export function matchingInsights(posts:DemoPost[],following:readonly string[],blocked:readonly string[],context:DemoRange):Array<{post:DemoPost;matched:DemoRange[]}> {
  return posts.filter(p=>p.state==='public'&&following.includes(p.author)&&!blocked.includes(p.author))
    .map(post=>({post,matched:post.anchors.filter(a=>overlaps(a,context))})).filter(x=>x.matched.length>0);
}
const range=(book:string,start:Point,end:Point,edition:'kjv'|'standard-works'):DemoRange=>{
  const result=mapReaderRange(book,start,end,edition);if(!result)throw Error('Invalid fictional demo anchor');return result;
};
export const demoPosts:DemoPost[]=[
  {id:'example-maya',author:'Maya',text:'I wonder how a fresh beginning changes the choices we make next.',state:'public',anchors:[range('bcbooks:gen',{chapter:1,verse:30},{chapter:2,verse:2},'kjv'),range('bcbooks:1-ne',{chapter:1,verse:1},{chapter:1,verse:3},'standard-works')]},
  {id:'example-eli',author:'Eli',text:'These passages make me think about paying attention to each other.',state:'public',anchors:[range('bcbooks:john',{chapter:1,verse:1},{chapter:1,verse:5},'kjv')]},
];
export const demoFollowing=['Maya'];
export const demoBlocked:string[]=[];
