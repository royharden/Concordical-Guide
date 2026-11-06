import {describe, expect, it} from 'vitest';
import {latestRequest} from './latestRequest';

describe('word-study request ordering', () => {
  it('does not let a delayed older response overwrite a newer response', async () => {
    const gate = latestRequest();
    let releaseOld!: (value:string)=>void;
    const delayed = new Promise<string>(resolve=>{releaseOld=resolve;});
    let displayed = '';
    const run = async (result:Promise<string>) => {
      const isCurrent = gate.begin();
      const value = await result;
      if (isCurrent()) displayed = value;
    };
    const old = run(delayed);
    await run(Promise.resolve('G26'));
    releaseOld('H7225');
    await old;
    expect(displayed).toBe('G26');
  });
  it('invalidates pending responses when an empty search starts', () => {
    const gate = latestRequest();
    const older = gate.begin();
    const empty = gate.begin();
    expect(older()).toBe(false);
    expect(empty()).toBe(true);
  });
});
