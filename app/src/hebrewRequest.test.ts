import {describe, expect, it, vi} from 'vitest';
import {HebrewState, startHebrewRequest} from './hebrewRequest';

function deferred<T>() {
  let resolve!:(value:T)=>void, reject!:(reason?:unknown)=>void;
  const promise=new Promise<T>((ok,fail)=>{resolve=ok;reject=fail;});
  return {promise,resolve,reject};
}
const response = (data:Promise<unknown>) => ({ok:true,json:()=>data} as Response);
const flush = async () => {for(let i=0;i<8;i++) await Promise.resolve();};

describe('Hebrew selection request lifecycle',()=>{
  it('ignores late success from a previously selected verse',async()=>{
    const slow=deferred<unknown>(); let current:HebrewState|null=null;
    const fetcher=vi.fn().mockResolvedValueOnce(response(slow.promise)).mockResolvedValueOnce(response(Promise.resolve({available:true,osis:'Gen.1.31',tokens:[]}))) as unknown as typeof fetch;
    const cancel=startHebrewRequest('/old','old',value=>{current=value;},fetcher); await flush(); cancel();
    startHebrewRequest('/new','new',value=>{current=value;},fetcher); await flush();
    expect(current).toMatchObject({key:'new',osis:'Gen.1.31'});
    slow.resolve({available:true,osis:'Gen.1.5',tokens:[]}); await flush();
    expect(current).toMatchObject({key:'new',osis:'Gen.1.31'});
  });
  it('ignores late failure after selecting an unavailable edition',async()=>{
    const slow=deferred<unknown>(); let current:HebrewState|null=null;
    const fetcher=vi.fn().mockResolvedValueOnce(response(slow.promise)).mockResolvedValueOnce(response(Promise.resolve({available:false,tokens:[]}))) as unknown as typeof fetch;
    const cancel=startHebrewRequest('/old','old',value=>{current=value;},fetcher); await flush(); cancel();
    startHebrewRequest('/web','web',value=>{current=value;},fetcher); await flush();
    slow.reject(new Error('late failure')); await flush();
    expect(current).toMatchObject({key:'web',available:false});
    expect(current).not.toHaveProperty('error');
  });
  it('does not publish after the pane closes',async()=>{
    const slow=deferred<unknown>(); const publish=vi.fn();
    const fetcher=vi.fn().mockResolvedValue(response(slow.promise)) as unknown as typeof fetch;
    const cancel=startHebrewRequest('/old','old',publish,fetcher); await flush(); cancel();
    slow.resolve({available:true,tokens:[]}); await flush();
    expect(publish).not.toHaveBeenCalled();
  });
  it('reports a current failure and permits a later retry',async()=>{
    const publish=vi.fn();
    const fetcher=vi.fn().mockResolvedValueOnce({ok:false}).mockResolvedValueOnce(response(Promise.resolve({available:true,osis:'Gen.1.1',tokens:[]}))) as unknown as typeof fetch;
    const cancel=startHebrewRequest('/first','same',publish,fetcher); await flush();
    expect(publish).toHaveBeenLastCalledWith({key:'same',available:false,tokens:[],error:true});
    cancel();
    startHebrewRequest('/retry','same',publish,fetcher); await flush();
    expect(publish).toHaveBeenLastCalledWith({key:'same',available:true,osis:'Gen.1.1',tokens:[]});
  });
});
