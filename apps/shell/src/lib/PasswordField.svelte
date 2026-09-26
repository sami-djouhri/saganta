<script lang="ts">
  // Passwort-Eingabe mit Anzeigen/Verbergen-Umschalter. Uncontrolled (das Formular
  // liest per name-Attribut ab) → Passwörter werden nie in State gespiegelt oder
  // nach einem Fehler neu befüllt. Wird auf Login/Register und Reset genutzt.
  import { Icon } from '@saganta/ui';

  interface Props {
    name?: string;
    id?: string;
    autocomplete?: string;
    required?: boolean;
    minlength?: number;
  }
  let {
    name = 'password',
    id,
    autocomplete = 'current-password',
    required = false,
    minlength,
  }: Props = $props();

  let show = $state(false);
</script>

<div class="relative">
  <input
    {id}
    {name}
    {required}
    {minlength}
    {autocomplete}
    type={show ? 'text' : 'password'}
    class="w-full rounded-lg border border-border bg-surface px-3 py-2 pr-10 text-text outline-none transition-colors duration-fast ease-saganta focus:border-accent-400"
  />
  <button
    type="button"
    onclick={() => (show = !show)}
    aria-label={show ? 'Passwort verbergen' : 'Passwort anzeigen'}
    aria-pressed={show}
    title={show ? 'Verbergen' : 'Anzeigen'}
    class="absolute inset-y-0 right-0 grid w-10 place-items-center rounded-lg text-muted transition-colors duration-fast ease-saganta hover:text-text"
  >
    <Icon name={show ? 'eye-off' : 'eye'} size={16} />
  </button>
</div>
