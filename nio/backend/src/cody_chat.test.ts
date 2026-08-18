import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { isStatusQuery } from './cody_persona';

describe('cody chat persona', () => {
  it('detects status queries', () => {
    assert.equal(isStatusQuery('what are agents doing?'), true);
    assert.equal(isStatusQuery('hello there'), false);
    assert.equal(isStatusQuery('active limbs'), true);
  });
});
