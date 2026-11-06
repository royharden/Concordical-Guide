import { describe, expect, it } from 'vitest';
import { popupStatus, receive, samePassage, verseAvailable } from './domain';

const p = {book:'gen', chapter:1, verse:1};
describe('passage synchronization', () => {
  // what_bug_this_catches: self-echo and duplicate updates never recirculate.
  it('ignores self messages and repeated locations', () => {
    expect(receive(p,{kind:'passage',sender:'a',passage:{...p,verse:2}},'a')).toBeNull();
    expect(receive(p,{kind:'passage',sender:'b',passage:p},'a')).toBeNull();
    expect(receive(p,{kind:'passage',sender:'b',passage:{...p,verse:2}},'a')?.verse).toBe(2);
  });
  it('preserves the reference through edition changes and detects missing verses', () => {
    expect(samePassage(p,{...p})).toBe(true);
    expect(verseAvailable([{verse:2,reference:'x',text:'x'}],1)).toBe(false);
  });
  it('makes a blocked popup explicit',()=>expect(popupStatus(false)).toContain('blocked'));
});
