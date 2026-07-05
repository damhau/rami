// French UI strings. Centralised so a language toggle could be added later;
// for now the app ships in French only (the game is Rami Portugais).

import type { MeldKind, ReqView } from "./types";

export function meldKindLabel(kind: MeldKind): string {
  return kind === "set" ? "brelan" : "suite";
}

// French messages for the server's stable error codes (the engine speaks English).
const ERRORS: Record<string, string> = {
  illegal_move: "Coup non autorisé.",
  not_your_turn: "Ce n'est pas votre tour.",
  contract_not_met: "Vos combinaisons ne remplissent pas le contrat (40 points minimum pour sortir).",
  table_state: "Action impossible pour l'instant.",
  table_full: "La table est complète.",
  table_not_found: "Table introuvable.",
  not_found: "Introuvable.",
  bad_message: "Message invalide.",
};

export function errorLabel(code: string | undefined): string {
  return (code && ERRORS[code]) || "Une erreur s'est produite.";
}

/** Build the round's contract label in French from its requirements. */
export function contractLabel(requirements: ReqView[]): string {
  const parts = requirements.map((r) =>
    r.kind === "set" ? "brelan" : `suite de ${r.min_len}`,
  );
  const counts = new Map<string, number>();
  for (const p of parts) counts.set(p, (counts.get(p) ?? 0) + 1);
  return [...counts.entries()]
    .map(([label, n]) => (n > 1 ? `${n} ${label.replace("brelan", "brelans")}` : `1 ${label}`))
    .join(" + ");
}

export const t = {
  brand: { rami: "Rami", suffix: "Portugais" },

  home: {
    heroLead: "Jouez au",
    heroName: "Rami Portugais",
    heroTail: "en ligne entre amis.",
    blurb:
      "Le Rami portugais à 11 contrats. Créez une table, partagez le code et jouez en temps réel — sans compte.",
    meta: "2–4 joueurs · 11 manches · le score le plus bas gagne.",
    yourName: "Votre nom",
    namePlaceholder: "ex. Damien",
    create: "+ Créer une table",
    vsComputer: "Jouer contre l'ordinateur",
    opponents: "Adversaires",
    orDivider: "ou",
    orJoin: "ou rejoindre",
    join: "Rejoindre",
    joinTable: (code: string) => `Rejoindre la table ${code}`,
    invitedTo: (code: string) => `Vous êtes invité à la table ${code} — entrez votre nom pour rejoindre.`,
    needName: "Entrez d'abord un nom.",
    genericError: "Une erreur s'est produite.",
  },

  lobby: {
    tableCode: "Code de la table",
    copyCode: "Copier le code",
    copyLink: "Copier le lien",
    linkCopied: "Lien copié !",
    scanToJoin: "Scannez pour rejoindre",
    players: (n: number) => `Joueurs (${n}/4)`,
    host: "hôte",
    you: "(vous)",
    ready: "prêt",
    notReady: "pas prêt",
    waitingPlayer: "En attente d'un joueur…",
    imNotReady: "Pas prêt",
    imReady: "Je suis prêt",
    start: "Démarrer la partie",
    needTwo: "Il faut au moins 2 joueurs pour démarrer.",
    waitingHost: "En attente de l'hôte…",
  },

  table: {
    connected: "connecté",
    connecting: "connexion…",
    leave: "Quitter",
    connectingTable: "Connexion à la table…",
  },

  game: {
    round: (n: number) => `Manche ${n} / 11`,
    contract: "Contrat",
    goOutWith: (n: number) => ["sortez avec ≥ ", `${n} pts`] as const,
    offline: "hors ligne",
    theirTurn: "● son tour",
    wentOut: "▣ sorti",
    cards: (n: number) => `${n} cartes`,
    drawTitle: "Piocher",
    stock: (n: number) => `Pioche · ${n}`,
    takeDiscardTitle: "Prendre la défausse",
    discardPile: "Défausse",
    empty: "vide",
    tableMelds: "Combinaisons sur la table",
    clickToLayOff: "Cliquez une combinaison pour la compléter",
    noMelds: "Aucune combinaison.",
    freePrompt: (label: string) => [`Prendre `, label, ` de la défausse gratuitement ?`] as const,
    claim: "Prendre",
    pass: "Passer",
    freeForYou: "Une carte gratuite vous est proposée.",
    freeDeciding: (who: string) => `${who} décide pour la carte gratuite…`,
    yourTurnShort: "À vous",
    yourTurnDraw: "À vous — piochez une carte.",
    yourTurnAct: "À vous — combinez et défaussez.",
    waitingFor: (who: string) => `En attente de ${who}…`,
    mustLayTaken:
      "Vous avez pris une carte de la défausse — vous devez l'utiliser dans une combinaison avant de défausser.",
    cancelPickup: "Annuler la prise",
    tray: "Combinaison en préparation",
    trayTotal: (pts: number) => `${pts} pts`,
    enoughToGoOut: "assez pour sortir",
    needMore: (min: number) => `il faut ≥ ${min}`,
    selectedHint: (n: number) => `${n} sélectionnée${n > 1 ? "s" : ""} — ajoutez-les en combinaison.`,
    clear: "Effacer",
    layDown: "Poser",
    goOut: "Sortir",
    yourTurnBadge: "à vous",
    outBadge: "sorti",
    handHint: "cliquez pour sélectionner · formez une combinaison · défaussez pour finir",
    draw: "Piocher",
    takeDiscard: "Prendre la défausse",
    takeShort: "Prendre",
    addMeld: "Ajouter la combinaison",
    addShort: "Ajouter",
    discard: "Défausser",
    tooFewCards: "Sélectionnez au moins 3 cartes.",
    notAMeld: "Ces cartes ne forment ni brelan ni suite.",
  },

  dialogs: {
    roundFinished: (n: number) => `Manche ${n} terminée`,
    wentOutScores0: (name: string) => [name, " est sorti et marque 0."] as const,
    player: "Joueur",
    round: "Manche",
    total: "Total",
    nextRound: "Manche suivante",
    waitingHostNext: "En attente de l'hôte pour la manche suivante…",
    wins: (name: string) => `${name} gagne !`,
    lowestWins: "Score le plus bas après 11 manches.",
    backHome: "Retour à l'accueil",
  },

  scoreboard: {
    title: "Scores",
    round: (n: number) => `manche ${n}/11`,
    player: "Joueur",
    hand: "Main",
    total: "Total",
    out: "▣ sorti",
    lowestWins: "Le score le plus bas après la manche 11 gagne.",
    thisRound: "Cette manche",
    contract: "Contrat",
    minToGoOut: "Min. pour sortir",
    dealer: "Donneur",
    stock: "Pioche",
    cards: (n: number) => `${n} cartes`,
    log: "Journal",
    noMoves: "Aucun coup joué.",
  },

  event: {
    roundStarted: (n: number) => `Manche ${n} commencée.`,
    tookDiscard: (who: string) => `${who} a pris la défausse.`,
    drewStock: (who: string) => `${who} a pioché.`,
    freeClaimed: (who: string) => `${who} a pris la carte gratuite.`,
    freePassed: (who: string) => `${who} a passé la carte gratuite.`,
    wentOut: (who: string) => `${who} est sorti !`,
    melded: (who: string) => `${who} a posé une combinaison.`,
    laidOff: (who: string) => `${who} a complété une combinaison.`,
    recoveredJoker: (who: string) => `${who} a récupéré un joker.`,
    discarded: (who: string) => `${who} a défaussé.`,
    returnedDiscard: (who: string) => `${who} a remis la carte à la défausse.`,
    roundOver: (n: number, who: string) => `Manche ${n} terminée — ${who} est sorti.`,
    gameOver: "Partie terminée !",
  },
} as const;
