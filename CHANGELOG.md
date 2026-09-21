# Cosa è cambiato

Le versioni che toccano i testi vanno riapplicate; quelle che toccano solo il
programma no, a meno che non sia scritto il contrario.

---

## v1.0 — 21 settembre 2026

La prima. **Tutto il gioco in italiano.**

Traduzione e patch di MarkMayer, pubblicate insieme ai
[TWR](https://discord.gg/85ayAcHRfH). Prima di questa patch Dimraeth in
italiano non c'era: è tradotto da zero, non riadattato.

### Cosa c'è dentro

**Copertura 100%**: 14.995 voci di testo, 176.226 parole, tutte e sedici le
categorie del gioco.

| | |
|---|---|
| Interfaccia | menu, impostazioni, inventario, mappa, messaggi d'errore |
| Missioni | titoli, obiettivi, bacheca degli incarichi |
| Dialoghi | tutti e diciassette i personaggi, con i quattro toni di risposta |
| Codice | mostri, oggetti, costruzioni, statistiche, effetti, potenziamenti |
| Abilità | l'albero intero, di tutte le razze e classi |
| Incantesimi | nomi, descrizioni, potenziamenti |
| Oggetti | materiali, cibo, pozioni, ricette, equipaggiamento |
| Scene | la voce narrante sul posto e le battute gridate |
| Cinematica | l'apertura per intero |

### Le scelte che si vedono giocando

- **I quattro toni delle risposte restano distinti.** Ogni battuta del
  giocatore esiste in versione eroica, stoica, burlona e da studioso: se in
  italiano collassassero, il sistema di personalità sparirebbe.
- **Il personaggio del giocatore non ha genere**, e l'italiano lo mette
  dappertutto. Tutte le frasi sono girate per non darglielo.
- **Tre personaggi danno del lei** — Alaric, Basilton e Aelwynor — perché il
  gioco li caratterizza come formali. Gli altri quattordici danno del tu.
- **Niente prestiti inglesi** nei termini di gioco: non *stamina*, non *loot*,
  non *cooldown*. Due eccezioni, decise e segnate: `Boss` e `Treant`.

### Il programma

- Trova il gioco da solo, e la ricerca si può interrompere
- Riconosce Dimraeth e non gli altri giochi Unity installati
- Backup automatico dei due file toccati, con pulsante **Ripristina**
- Si accorge se il gioco è stato aggiornato e rifà il backup
- Non scrive niente se un controllo fallisce
- Rinomina la voce del menu: *Português* diventa *Italiano*
