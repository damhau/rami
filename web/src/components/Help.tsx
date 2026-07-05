import { useState } from "react";
import { createPortal } from "react-dom";
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
      {open &&
        // Portal to <body> so the header's backdrop-blur (a containing block for
        // fixed elements) doesn't trap the overlay behind the table.
        createPortal(
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-white/10 bg-ink shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
              <h2 className="text-xl font-bold">Comment jouer au Rami Portugais</h2>
              <button
                onClick={() => setOpen(false)}
                aria-label="Fermer"
                className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-white/10 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 overflow-y-auto px-6 py-5">
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

              <Section title="Commandes en jeu">
                <p>
                  <b>Piocher</b> / <b>Prendre la défausse</b> : votre première action du tour.
                </p>
                <p>
                  <b>Cliquez</b> vos cartes pour les sélectionner ; <b>glissez-les</b> pour
                  réorganiser votre main.
                </p>
                <p>
                  <b>Ajouter la combinaison</b> : le jeu devine s'il s'agit d'un brelan ou d'une
                  suite et l'ajoute à la zone de préparation (qui affiche le total de points).
                </p>
                <p>
                  <b>Sortir</b> / <b>Poser</b> : valide les combinaisons préparées (la sortie exige
                  le contrat et ≥ 40 pts).
                </p>
                <p>
                  <b>Compléter</b> : après être sorti, sélectionnez une carte puis cliquez une
                  combinaison de la table pour l'y ajouter.
                </p>
                <p>
                  <b>Récupérer un joker</b> : posez la carte exacte qu'il représente sur la
                  combinaison ; le joker revient dans votre main.
                </p>
                <p>
                  <b>Défausser</b> : termine votre tour.
                </p>
              </Section>

              <div className="pt-1">
                <Button className="w-full" onClick={() => setOpen(false)}>
                  Fermer
                </Button>
              </div>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
