/*
 * captcha-guard widget: self-hosted Proof-of-Work Captcha (ALTCHA-kompatibel).
 *
 * Framework-agnostisches Web-Component. Holt eine PoW-Challenge vom captcha-guard-
 * Dienst, loest sie unsichtbar per Web-Crypto (SHA-256) und legt einen ALTCHA-
 * kompatiblen base64-Payload in ein verstecktes Formfeld. Kein externer Anbieter,
 * keine Cookies, kein CDN.
 *
 * Einbindung:
 *   <script src="/captcha-guard/captcha-guard.js" defer></script>
 *   <captcha-guard challenge-url="https://captcha.example/captcha/challenge"></captcha-guard>
 *
 * Attribute:
 *   challenge-url  (Pflicht) URL des captcha-guard /captcha/challenge Endpunkts
 *   field-name     (opt.)    Name des Hidden-Inputs (Default: "altcha")
 *   auto           (opt.)    "false" = nicht sofort loesen (Default: sofort loesen)
 *
 * JS-API (fuer SPA/React):
 *   const el = document.querySelector('captcha-guard');
 *   const token = await el.ensureToken();   // frischen Token garantieren
 *   el.token;                               // aktueller Token (oder null)
 * Events:
 *   'captcha-guard:solved'  detail: { token }
 *   'captcha-guard:error'   detail: { error }
 */
(function () {
  "use strict";
  if (customElements.get("captcha-guard")) return;

  const enc = new TextEncoder();

  async function sha256Hex(str) {
    const buf = await crypto.subtle.digest("SHA-256", enc.encode(str));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  class CaptchaGuard extends HTMLElement {
    constructor() {
      super();
      this.token = null;
      this._solving = null;
      this._input = null;
      this._status = null;
    }

    get fieldName() {
      return this.getAttribute("field-name") || "altcha";
    }

    connectedCallback() {
      // Sichtbarer Status + Hidden-Input im Light-DOM (damit es mit dem Form submitted).
      this.innerHTML = "";
      const wrap = document.createElement("div");
      wrap.className = "cg-box";
      wrap.setAttribute("role", "status");
      wrap.setAttribute("aria-live", "polite");
      this._status = document.createElement("span");
      this._status.className = "cg-status";
      this._status.textContent = "";
      const spinner = document.createElement("span");
      spinner.className = "cg-spinner";
      wrap.appendChild(spinner);
      wrap.appendChild(this._status);
      this.appendChild(wrap);

      this._input = document.createElement("input");
      this._input.type = "hidden";
      this._input.name = this.fieldName;
      this.appendChild(this._input);

      // Bei nativem Form-Submit sicherstellen, dass ein frischer Token da ist.
      this._form = this.closest("form");
      if (this._form && !this._form.__cgHooked) {
        this._form.__cgHooked = true;
        this._form.addEventListener("submit", (e) => this._onSubmit(e), true);
      }

      this._setState("pending", "Sicherheitsprüfung …");
      if (this.getAttribute("auto") !== "false") {
        this.ensureToken().catch(() => {});
      }
    }

    _setState(state, text) {
      this.dataset.state = state;
      if (this._status) this._status.textContent = text;
    }

    async _onSubmit(e) {
      // Nur eingreifen, wenn noch kein Token vorliegt (sonst laesst der Handler durch).
      if (this.token) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      try {
        await this.ensureToken();
      } catch (_) {
        /* Fehler ist im Status sichtbar; Absenden trotzdem versuchen (fail-open UX) */
      }
      // Nach dem Loesen erneut absenden.
      if (typeof this._form.requestSubmit === "function") this._form.requestSubmit();
      else this._form.submit();
    }

    /** Garantiert einen frischen, geloesten Token. Cached laufende Loesungen. */
    ensureToken() {
      if (this.token) return Promise.resolve(this.token);
      if (this._solving) return this._solving;
      this._solving = this._solve().finally(() => {
        this._solving = null;
      });
      return this._solving;
    }

    async _solve() {
      const url = this.getAttribute("challenge-url");
      if (!url) {
        this._setState("error", "Captcha nicht konfiguriert.");
        throw new Error("challenge-url fehlt");
      }
      this._setState("solving", "Sicherheitsprüfung läuft …");
      try {
        const res = await fetch(url, { method: "GET", cache: "no-store" });
        if (!res.ok) throw new Error("challenge " + res.status);
        const ch = await res.json();
        const salt = ch.salt;
        const target = ch.challenge;
        const max = ch.maxnumber || 1000000;

        let number = null;
        for (let n = 0; n <= max; n++) {
          if ((await sha256Hex(salt + n)) === target) {
            number = n;
            break;
          }
        }
        if (number === null) throw new Error("keine Loesung");

        const payload = {
          algorithm: ch.algorithm || "SHA-256",
          challenge: target,
          number: number,
          salt: salt,
          signature: ch.signature,
        };
        const token = btoa(JSON.stringify(payload));
        this.token = token;
        if (this._input) this._input.value = token;
        this._setState("solved", "Verifiziert ✓");
        this.dispatchEvent(
          new CustomEvent("captcha-guard:solved", { detail: { token }, bubbles: true })
        );
        return token;
      } catch (err) {
        this._setState("error", "Prüfung fehlgeschlagen: erneut versuchen.");
        this.dispatchEvent(
          new CustomEvent("captcha-guard:error", { detail: { error: err }, bubbles: true })
        );
        throw err;
      }
    }

    /** Token verwerfen (z.B. nach fehlgeschlagenem Login, um neu zu loesen). */
    reset() {
      this.token = null;
      if (this._input) this._input.value = "";
      this._setState("pending", "Sicherheitsprüfung …");
      if (this.getAttribute("auto") !== "false") this.ensureToken().catch(() => {});
    }
  }

  customElements.define("captcha-guard", CaptchaGuard);
})();
