// Fixture: a JS test file full of manipulation patterns.
// Do NOT copy these patterns into real tests.

test.skip('skipped', () => { expect(value).toBe(1); });
test.only('focused', () => { expect(value).toBe(1); });
test.todo('later');
test('sleepy', async () => { await new Promise(r => setTimeout(r, 1000)); expect(value).toBe(1); });
test('fake', () => { expect(true).toBe(true); });
test('empty', () => {});
test('retry', async () => {
  for (let i = 0; i < 3; i++) {
    try { expect(flaky()).toBe(1); break; } catch { continue; }
  }
});
test('swallowed', () => {
  try { expect(risky()).toBe(1); } catch (e) {}
});
test('real', () => { expect(add(2, 3)).toBe(5); });
