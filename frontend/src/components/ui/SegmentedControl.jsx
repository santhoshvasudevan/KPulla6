export default function SegmentedControl({
  label,
  ariaLabel,
  options = [],
  value,
  onChange,
  className = '',
}) {
  const classes = ['ui-segmented-control', className].filter(Boolean).join(' ');
  const groupLabel = ariaLabel || label;

  return (
    <div className={classes}>
      {label ? <span className="ui-segmented-control__label">{label}</span> : null}
      <div
        className="ui-segmented-control__track"
        role="group"
        aria-label={groupLabel}
      >
        {options.map((opt) => {
          const selected = value === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              className={`ui-segmented-control__option${selected ? ' ui-segmented-control__option--selected' : ''}`}
              aria-pressed={selected}
              aria-label={opt.ariaLabel || opt.label}
              onClick={() => onChange(opt.value)}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
