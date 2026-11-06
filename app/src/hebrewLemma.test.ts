import {expect, it} from 'vitest';
import {candidateHebrewId} from './hebrewLemma';

it('links only an unambiguous numeric OSHB lemma component',()=>{
  expect(candidateHebrewId('b/7225')).toBe('H7225');
  expect(candidateHebrewId('3068')).toBe('H3068');
  expect(candidateHebrewId('1254 a')).toBeNull();
  expect(candidateHebrewId('a/1/2')).toBeNull();
  expect(candidateHebrewId(null)).toBeNull();
});
