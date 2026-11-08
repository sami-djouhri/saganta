import { describe, expect, it } from 'vitest';
import { jahrestageAus, kontaktAus } from './formular';

function fd(paare: [string, string][]): FormData {
  const f = new FormData();
  for (const [k, v] of paare) f.append(k, v);
  return f;
}

describe('formular', () => {
  it('nimmt nur vollstaendige Jahrestage', () => {
    expect(
      jahrestageAus(
        fd([
          ['jt_bezeichnung', 'Hochzeitstag'],
          ['jt_datum', '2020-06-20'],
          ['jt_bezeichnung', ''],
          ['jt_datum', ''],
          ['jt_bezeichnung', 'Kennenlerntag'],
          ['jt_datum', ''],
        ]),
      ),
    ).toEqual([{ bezeichnung: 'Hochzeitstag', datum: '2020-06-20' }]);
  });

  it('macht aus leeren Feldern null', () => {
    const k = kontaktAus(fd([['name', ' Anna '], ['telefon', '  '], ['geburtstag', '1995-03-10']]));
    expect(k).toMatchObject({ name: 'Anna', telefon: null, geburtstag: '1995-03-10', jahrestage: [] });
  });
});
