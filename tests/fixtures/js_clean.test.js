// Fixture: a clean JS test file — testguard must report nothing.

test('adds', () => { expect(add(2, 3)).toBe(5); });
test('rejects', async () => { await expect(f()).rejects.toThrow(); });
test('real value', () => { expect(total(cart)).toBe(59); });
