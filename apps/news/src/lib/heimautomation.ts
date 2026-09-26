/**
 * Die fertige Home-Assistant-Konfiguration zum Kopieren.
 *
 * ★★ **Der Abrufweg existiert seit Langem, er war nur nicht auffindbar.** Die
 * Route `/briefing/json/<token>` liegt im Repo und ihr Kommentar nennt
 * ausdruecklich „eine Heim-Automation" als Zweck. Benutzt hat sie niemand, und
 * das ist kein Wunder: in der Oberflaeche stand sie nirgends, man haette also
 * erst den Quelltext lesen, dann den Pfad raten und schliesslich die Form der
 * Antwort erraten muessen, um einen Sensor dafuer zu schreiben.
 *
 * Dieselbe Sorte Befund wie am 2026-09-13 bei Gartiko: ein fertiger Weg, der
 * ungenutzt bleibt, weil ihn nichts sichtbar macht. Deshalb steht die
 * Konfiguration jetzt zum Kopieren da, statt beschrieben zu werden.
 *
 * ★ Bewusst **Pull statt Push**: der Webhook-Weg daneben verlangt, dass Home
 * Assistant von aussen erreichbar ist. Das ist im Heimnetz ein Loch, das man
 * dafuer nicht aufmachen will (Owner-Regel: kein Fernzugang ins Heimnetz). Beim
 * Abruf geht die Verbindung in die andere Richtung, und der Token ist nur ein
 * Lesezugang auf die eigenen Briefings.
 */

/** Die Felder, die das Briefing liefert. Vollstaendig, damit die Vorlage passt. */
export interface BriefingFelder {
  date: string;
  generated_at: string;
  day: unknown;
  weather: unknown;
  top_story: { title?: string } | null;
  top_items: unknown[];
  sections: unknown[];
  item_count: number;
  /** Der vorgelesene Fliesstext. Das, was ein Lautsprecher sagen wuerde. */
  spoken_text: string;
}

/**
 * REST-Sensor plus ein Skript zum Vorlesen.
 *
 * ⚠️ `value_template` liefert das **Datum**, nicht den Text: ein Zustandswert in
 * Home Assistant ist auf 255 Zeichen begrenzt, und ein Briefing ist laenger.
 * Wer den Text dorthin legt, bekommt einen Sensor, der ohne Fehlermeldung
 * `unknown` anzeigt, sobald das Briefing etwas ausfuehrlicher ausfaellt. Der
 * Text steht deshalb als Attribut daneben, wo es keine Grenze gibt.
 *
 * `scan_interval` ist bewusst gross: das Briefing entsteht einmal am Morgen.
 * Ein Minutentakt erzeugte nur Last auf beiden Seiten.
 */
export function haKonfiguration(jsonUrl: string): string {
  return `# Saganta-Briefing in Home Assistant.
# Einfuegen in configuration.yaml, danach HA neu starten.
#
# Der Link ist privat und ersetzt keine Anmeldung: er gibt ausschliesslich die
# eigenen Briefings her, sonst nichts. Unter "Neuen Link erzeugen" wird er
# ungueltig, falls er doch einmal irgendwo landet.

rest:
  - resource: "${jsonUrl}"
    scan_interval: 1800          # alle 30 Minuten; das Briefing entsteht einmal am Morgen
    sensor:
      - name: "Saganta Briefing"
        unique_id: saganta_briefing
        # ⚠️ Hier steht das DATUM, nicht der Text. Ein Zustandswert darf in Home
        # Assistant hoechstens 255 Zeichen haben; der Text kommt als Attribut.
        value_template: "{{ value_json.date }}"
        json_attributes:
          - spoken_text
          - top_story
          - item_count
          - generated_at
          - audio_url

template:
  - sensor:
      - name: "Briefing Schlagzeile"
        state: >-
          {{ state_attr('sensor.saganta_briefing', 'top_story').title
             if state_attr('sensor.saganta_briefing', 'top_story') else 'noch keins' }}

script:
  briefing_vorlesen:
    alias: "Briefing vorlesen"
    sequence:
      - service: tts.speak
        target:
          entity_id: tts.piper          # eigene TTS-Entitaet eintragen
        data:
          media_player_entity_id: media_player.wohnzimmer   # eigenen Lautsprecher eintragen
          message: "{{ state_attr('sensor.saganta_briefing', 'spoken_text') }}"
`;
}

/** Ein kurzer Abruf zum Ausprobieren, bevor man etwas in HA eintraegt. */
export function probeBefehl(jsonUrl: string): string {
  return `curl -s "${jsonUrl}" | head -c 400`;
}
