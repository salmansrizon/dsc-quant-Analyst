import { getZoneConfig, type ZoneType } from '../../design/zones';

interface ZoneHeaderProps {
  type: ZoneType;
}

// #90-architecture-review (candidate A): the icon+label rendering shared by
// Zone (a static header) and CollapsibleZone (rendered inside a Radix
// Collapsible.Trigger) — was independently duplicated in both. No wrapping
// row of its own beyond the icon/label pairing, since each caller places its
// own sibling (Zone's `actions`, CollapsibleZone's chevron) differently.
export function ZoneHeader({ type }: ZoneHeaderProps) {
  const config = getZoneConfig(type);
  const { Icon } = config;
  return (
    <div className="flex items-center gap-2">
      <Icon size={16} style={{ color: config.colorVar }} />
      <span className="text-sm font-semibold" style={{ color: config.colorVar }}>
        {config.label}
      </span>
    </div>
  );
}
