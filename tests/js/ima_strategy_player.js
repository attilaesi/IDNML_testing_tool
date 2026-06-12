() => {
  try {
    var player = window.__strategyPlayer;
    if (!player) return null;
    return [player];
  } catch (e) { return null; }
}
