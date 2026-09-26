<script lang="ts">
  /**
   * Vorschau eines Bild-Anhangs über eine `blob:`-Adresse.
   *
   * Der Anhang kommt mit `Content-Disposition: attachment` und einer CSP, die
   * alles verbietet; als Seitenadresse würde er also nie angezeigt, nur
   * heruntergeladen. Deshalb holt die Komponente ihn per `fetch` und zeigt das
   * Ergebnis als `blob:` an. Eine solche Adresse hat keinen Zugriff auf Cookies
   * oder Sitzung, und die Datei selbst wird nie im Ursprung der Anwendung
   * ausgeführt. Scheitert der Abruf, verschwindet die Vorschau einfach: der
   * Download-Link in der Liste bleibt der verlässliche Weg.
   */
  let { url, beschriftung }: { url: string; beschriftung: string } = $props();

  let quelle = $state('');
  let fehlgeschlagen = $state(false);

  $effect(() => {
    let aktiv = true;
    let objektAdresse = '';
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.blob();
      })
      .then((blob) => {
        if (!aktiv) return;
        objektAdresse = URL.createObjectURL(blob);
        quelle = objektAdresse;
      })
      .catch(() => {
        if (aktiv) fehlgeschlagen = true;
      });
    return () => {
      aktiv = false;
      if (objektAdresse) URL.revokeObjectURL(objektAdresse);
    };
  });
</script>

{#if quelle && !fehlgeschlagen}
  <figure class="min-w-0">
    <img
      src={quelle}
      alt={beschriftung}
      loading="lazy"
      class="max-h-56 w-auto max-w-full rounded-md border border-border object-contain"
    />
    <figcaption class="mt-1 truncate text-xs text-muted">{beschriftung}</figcaption>
  </figure>
{/if}
