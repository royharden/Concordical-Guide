import {demoBlocked,demoFollowing,demoPosts,mapPassage,matchingInsights, type DemoRange} from './friendsInsights';
import type {Passage} from './domain';

const label=(r:DemoRange)=>`${r.workId==='bom'?'Book of Mormon':'Bible'} / ${r.bookId} ${r.start.chapter}:${r.start.verse}–${r.end.chapter}:${r.end.verse}`;
export function FriendsInsights({passage,edition}:{passage:Passage;edition:'kjv'|'webp'|'standard-works'}) {
  const context=mapPassage(passage,edition);
  const matches=context?matchingInsights(demoPosts,demoFollowing,demoBlocked,context):[];
  return <section className="friends-insights" aria-label="Friends’ Insights demo">
    <h3>Friends’ Insights <small>FICTIONAL LOCAL DEMO</small></h3>
    <p>Examples from fictional people you follow. No accounts, sharing, reading activity or notes are sent anywhere. These examples are separate from the social lab’s saved data.</p>
    {!context ? <p role="status">Insights are unavailable for this passage or edition in the demo. Only selected KJV and Book of Mormon sample references are mapped; WEB mapping has not been verified.</p> : matches.length===0 ? <p role="status">No followed fictional insights match this passage.</p> : matches.map(({post,matched})=><article key={post.id}><strong>{post.author} (fictional)</strong><p>{post.text}</p><p className="insight-match">Matches: {matched.map(label).join('; ')}. A range match does not mean every verse was discussed.</p></article>)}
  </section>;
}
