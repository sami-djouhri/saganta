// Attrappen fuer die $app-Module, die @saganta/ui beim Import mitzieht.
import { readable } from 'svelte/store';
export const page = readable({ url: new URL(location.href), data: {}, params: {} });
export const navigating = readable(null);
export const updated = { subscribe: readable(false).subscribe, check: async () => false };
export const browser = true;
export const dev = false;
export const building = false;
export function enhance() {
  return { destroy() {} };
}
export function deserialize(s: string) {
  return JSON.parse(s);
}
export async function invalidateAll() {}
export function beforeNavigate() {}
export function afterNavigate() {}
