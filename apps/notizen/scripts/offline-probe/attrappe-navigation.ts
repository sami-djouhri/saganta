export function goto(ziel: string) {
  document.body.dataset.goto = ziel;
  return Promise.resolve();
}
export async function invalidateAll() {}
export async function invalidate() {}
export function beforeNavigate() {}
export function afterNavigate() {}
export function onNavigate() {}
