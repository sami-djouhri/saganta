/** `use:enhance` ohne SvelteKit: tut nichts, die Probe schickt nichts ab. */
export function enhance() {
  return { destroy() {} };
}
