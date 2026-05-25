export default function Button({
  variant = 'primary',
  disabled = false,
  type = 'button',
  onClick,
  className = '',
  children,
  ...rest
}) {
  const classes = ['ui-btn', `ui-btn--${variant}`, className].filter(Boolean).join(' ');

  return (
    <button type={type} disabled={disabled} onClick={onClick} className={classes} {...rest}>
      {children}
    </button>
  );
}
