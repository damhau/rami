import { useState } from "react";
import { Button } from "./ui/button";

const CONTRACTS: [number, string][] = [
  [1, "1 brelan"],
  [2, "1 suite de 4"],
  [3, "1 suite de 5"],
  [4, "2 brelans"],
  [5, "1 suite de 4 + 1 brelan"],
  [6, "2 suites de 4"],
  [7, "3 brelans"],
  [8, "2 brelans + 1 suite de 4"],
  [9, "2 suites de 4 + 1 brelan"],
  [10, "3 suites de 4"],
  [11, "3 brelans + 1 suite de 4"],
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-1 font-semibold text-gold">{title}</h3>
      <div className="space-y-1 text-sm text-slate-300">{children}</div>
    </div>
  );
}

/** "Aide" button that opens a French rules guide. */
export function HelpButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)} title="Aide">
        Aide
      </Button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-white/10 bg-ink p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold">Comment jouer au Rami Portugais</h2>
              <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
                ✕
              </Button>
            </div>

            <div className="space-y-4">
              <Section title="But du jeu">
                <p>
                  11 manches, une par contrat. À chaque manche, soyez le premier à vous débarrasser
                  de toutes vos cartes. Vous marquez les points des cartes qui restent en main — le
                  score le plus bas après 11 manches gagne.
                </p>
              </Section>

              <Section title="Votre tour">
                <p>1. Piochez une carte (pioche ou défausse visible).</p>
                <p>2. Posez des combinaisons et/ou complétez celles sur la table (facultatif).</p>
                <p>3. Défaussez une carte — le tour se termine toujours par une défausse.</p>
                <p className="text-slate-400">
                  Prendre la défausse vous oblige à l'utiliser dans une combinaison ce tour-ci.
                </p>
              </Section>

              <Section title="Combinaisons">
                <p>
                  <b>Brelan</b> : au moins 3 cartes de même valeur (ex. 7♠ 7♥ 7♦).
                </p>
                <p>
                  <b>Suite</b> : au moins 3 cartes qui se suivent, même couleur (ex. 4♠ 5♠ 6♠).
                  L'As est bas ou haut, sans boucler (A‑2‑3 ✓, Q‑K‑A ✓, K‑A‑2 ✗).
                </p>
              </Section>

              <Section title="Sortir">
                <p>
                  Votre première pose (« sortie ») doit réaliser le contrat de la manche <b>et</b>{" "}
                  totaliser au moins <b>40 points</b>, le tout en une seule fois. Ensuite, vous
                  posez le reste au fil des tours.
                </p>
              </Section>

              <Section title="Contrats (manche par manche)">
                <table className="w-full text-sm">
                  <tbody>
                    {CONTRACTS.map(([n, label]) => (
                      <tr key={n} className="border-t border-white/5">
                        <td className="py-1 pr-3 text-slate-400">Manche {n}</td>
                        <td className="py-1 font-medium">{label}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Section>

              <Section title="Jokers">
                <p>Un joker remplace n'importe quelle carte, sans limite par combinaison.</p>
                <p>
                  <b>Récupération</b> : posez la carte exacte que le joker représente sur la
                  combinaison pour le reprendre en main.
                </p>
                <p className="text-slate-400">Un joker gardé en main vaut 25 points à la fin.</p>
              </Section>

              <Section title="Carte gratuite">
                <p>
                  À 3+ joueurs, quand un joueur pioche (refusant la défausse visible), les joueurs
                  suivants peuvent la prendre gratuitement — jusqu'à ce que le joueur actif
                  défausse.
                </p>
              </Section>

              <Section title="Score">
                <p>As = 11 · figures = 10 · joker en main = 25 · autres = leur valeur.</p>
                <p>Celui qui sort marque 0 pour la manche. Plus bas total après 11 manches gagne.</p>
              </Section>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
