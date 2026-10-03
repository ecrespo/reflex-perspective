// Minimal React stub: the bridge's pure helpers never render.
const noop = () => {};
export const useCallback = (fn) => fn;
export const useEffect = noop;
export const useRef = (value) => ({ current: value });
export const useState = (value) => [value, noop];
export default { useCallback, useEffect, useRef, useState };
