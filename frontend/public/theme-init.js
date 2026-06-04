(function () {
  var KEY = 'kpulla6.themePreference';
  var stored = localStorage.getItem(KEY);
  var preference =
    stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
  var resolved =
    preference === 'system'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : preference;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
})();
