// Public API of web/src/compare (owner: thread 10). Mount guide in README.md next to this file.
export { CardCompareStrip, AddToCompare, CompareBar, CompareOptionsButton, CompareRoot, pinHTML, useCompareItems, openCompare } from './Compare.jsx';
export { compareStore, createCompareStore, currentWeather, COMPARE_CHANGE, COMPARE_OPEN, COMPARE_KEY } from './store.js';
export { compareSiblings, cardCompareHTML, cardStripEnabled, CARD_STRIP_KEY, chipText, placeLabel, optionPaths, buildComparison, onlyDifferences, pathKey, MAX_COMPARE } from './model.js';
export { loadComparison, fromExpand, normalizeServer } from './data.js';
