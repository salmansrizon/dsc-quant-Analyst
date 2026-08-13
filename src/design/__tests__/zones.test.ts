import { describe, expect, it } from 'vitest';
import { getZoneConfig, ZONE_TYPES, type ZoneType } from '../zones';

describe('zone vocabulary (#87)', () => {
  it('exposes the five zone types in map-order', () => {
    const expected: ZoneType[] = ['price', 'fundamentals', 'fit', 'sector', 'news'];
    expect(ZONE_TYPES).toEqual(expected);
  });

  it.each(ZONE_TYPES)('gives %s a label, description, css var, and icon', (type) => {
    const config = getZoneConfig(type);
    expect(config.type).toBe(type);
    expect(config.label.length).toBeGreaterThan(0);
    expect(config.description.length).toBeGreaterThan(0);
    expect(config.colorVar).toMatch(/^var\(--zone-[a-z]+\)$/);
    expect(config.Icon).toBeTypeOf('object');
  });

  it('gives every zone a distinct color token', () => {
    const vars = ZONE_TYPES.map((type) => getZoneConfig(type).colorVar);
    expect(new Set(vars).size).toBe(vars.length);
  });
});
