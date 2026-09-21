# Come funziona

Come è fatta la patch, e perché è fatta così. Niente di tutto questo serve per
usarla: serve a chi vuole controllare, rifarla, o portarla su un'altra lingua.

---

## Dove sta il testo

Dimraeth è Unity 6 con IL2CPP. La localizzazione se la sono scritta in casa gli
sviluppatori (`Assets/System/Scripts/Localization/`, con `CsvHelper`), e i testi
sono **263 TextAsset** dentro `Dimraeth_Data/sharedassets1.assets`.

Ogni TextAsset è un CSV `Key,Text`, e il formato va rispettato alla lettera:

- UTF-8 **con BOM**
- righe terminate CRLF
- la chiave non è mai quotata
- il testo è quasi sempre quotato, con le virgolette interne raddoppiate
- **l'intestazione `Key,Text` non è quotata**

L'ultimo punto sembra un dettaglio da niente ed è quello che ha fatto fallire il
primo serializzatore del progetto. Non se n'è accorto nessuno leggendo: se n'è
accorta la guardia che riscrive il CSV inglese e lo confronta byte per byte con
l'originale.

I 263 file sono **16 categorie × 10 corsie di lingua**:

| | |
|---|---|
| categorie | UI, Items, Equipment, Spells, Quests, NPCDialogues, Codex, Cinematics, Tutorials, Skills, Passives, Attributes, BuildItems, POIMarkers, InScene, Errors |
| corsie | le 8 vendute (en de es pt ru ja ko zh) + un vietnamita incompleto + una pseudo-localizzazione di QA |

**Le due corsie nascoste non sono selezionabili**: il menu ne mostra otto,
verificato a schermo. Per questo una lingua vera va ceduta.

## Come si riconosce una corsia

Non dalla posizione nel file. Gli identificativi interni di Unity (`path_id`)
cambiano a ogni build del gioco, e una patch che si fidasse di quelli si
romperebbe al primo aggiornamento — scrivendo per giunta l'italiano nel posto
sbagliato, che è peggio che non scriverlo affatto.

Si riconosce **dal contenuto**, con un test per lingua sull'ordine giusto:
prima gli alfabeti, che sono inequivocabili (cirillico, kana, hangul, han); poi
il vietnamita, che è latino ma ha segni suoi ed è mescolato a righe inglesi;
poi la pseudo-localizzazione, che ha una firma sua; infine le lingue latine, a
punteggio sulle parole funzione.

Il vietnamita va provato **prima** del cinese, o un test sui caratteri han lo
mancherebbe.

## Come si scrive l'italiano

La patch parte **sempre dall'inglese** e ci sovrascrive le traduzioni, poi
mette il risultato nella corsia ceduta. Tre conseguenze, tutte volute:

1. quello che non è tradotto resta **inglese**, mai vuoto e mai nella lingua
   ceduta, che sarebbe la cosa peggiore — un misto incomprensibile;
2. la patch si può riapplicare quante volte si vuole senza impilarsi su se
   stessa, perché riparte dal backup;
3. righe e chiavi restano **esattamente** quelle dell'inglese, e questo si può
   controllare.

Si traduce **per testo, non per riga**. La stessa voce di menu esiste sotto
chiavi diverse a seconda della schermata, e `0/3` compare 4.277 volte: delle
24.887 righe grezze, il lavoro vero sono **14.995 stringhe uniche**. Ogni testo
tradotto viene poi rimappato su tutte le chiavi che lo condividono.

Le poche chiavi che vogliono una resa diversa dalle gemelle — `Heroic` è una
personalità e una rarità, la stessa domanda la fa un personaggio che dà del tu e
uno che riceve il lei — stanno in un elenco a parte, applicato dopo.

## Il nome della lingua nel menu

Questo non sta nei CSV. *Deutsch*, *Español*, *Português* sono **letterali C#**
compilati dentro il gioco, e vivono nella tabella `stringLiteral` di
`il2cpp_data/Metadata/global-metadata.dat`.

L'intestazione del file comincia con la firma `FAB11BAF`, poi la versione dei
metadati (qui **31**), poi quattro interi che dicono dove sta la tabella dei
letterali e dove stanno i loro dati. Ogni voce della tabella è una coppia
`(lunghezza, indice nei dati)`, e i testi stanno tutti attaccati in un unico
blocco **senza terminatore**.

Questo cambia tutto: la lunghezza scritta in tabella è l'**unica** cosa che dice
dove finisce una stringa. Quindi

- **accorciare** un letterale è un cambio locale — si riscrivono i byte
  all'inizio e si abbassa la lunghezza — e i byte che avanzano restano nel file
  senza che nessuno li legga;
- **allungarlo** vorrebbe dire spostare il blocco dei dati e riscrivere tutti e
  30.543 gli indici.

`Italiano` sono 8 byte e `Português` ne erano 10: ci sta. Il risultato sul file
vero è di **nove byte cambiati** — uno nella tabella, otto nei dati — e
dimensione identica.

Restano dentro intatti i letterali `Portuguese`, `Portuguese (Brazil)` e
`Portuguese (Portugal)`: sono i nomi Unity della lingua, un'altra cosa dal nome
che il menu mostra di sé.

## Le guardie

Il programma **non scrive niente se un controllo fallisce**. Sono queste:

| guardia | cosa impedisce |
|---|---|
| round-trip del CSV inglese byte per byte | che il serializzatore sbagli il formato |
| stesse righe e stesse chiavi dell'inglese | che una riga si perda o si aggiunga |
| segnaposto `{0}` identici | che una frase perda il numero che ci va dentro |
| tag `<b>` `<color=...>` identici | che il gioco mostri il markup invece del testo |
| stesso numero di a capo | che un testo su due righe ne diventi uno solo |
| nessuna traduzione vuota | che una voce di menu sparisca |
| firma e versione dei metadati | che si scriva dentro un file che non è quello |
| il nome della lingua esiste una volta sola | che si rinomini la voce sbagliata |
| il testo nuovo non è più lungo del vecchio | che si sfondi il blocco dei dati |
| nessun altro letterale legge quei byte | che si rompa una stringa vicina |
| rilettura dopo la scrittura | che si dia per riuscito un file che non lo è |

Ognuna è stata **fatta fallire apposta** prima di essere accettata. Una guardia
che non si è mai vista scattare non è una guardia, è una speranza.

## Il backup, e come si accorge di un aggiornamento

Alla prima esecuzione ogni file toccato viene copiato in `.orig`, e da lì in poi
la patch riparte sempre da quello.

C'è un caso scomodo: il gioco si aggiorna, il `.orig` resta quello vecchio, e
riapplicare la patch **riporterebbe indietro il file** senza che nessuno capisca
perché. Per accorgersene, ogni patch registra in un `.patchinfo` l'impronta
SHA-256 di quello che ha prodotto: se al giro dopo il file non è più quello, il
gioco è cambiato e il backup va rifatto.

Quando il `.patchinfo` manca — patch applicata da una versione precedente — si
guarda il file e ci si chiede se per caso non l'abbiamo scritto noi. **Questa
domanda va fatta bene.** Il primo riconoscitore contava parole italiane comuni
(`la`, `di`, `del`, `per`, `una`, `con`) e sullo stesso CSV faceva 45 colpi sul
**portoghese e sullo spagnolo**, che quelle parole le hanno quasi tutte. Un
originale scambiato per patchato vuol dire il backup pulito sovrascritto con un
file già tradotto, e l'originale perso per sempre.

L'elenco stretto usa solo parole che l'italiano non condivide con quelle due —
`il`, `gli`, `della`, `che`, `non`, `più`, `può`, `perché` — e sullo stesso
confronto fa **0 contro 98**.

## Riconoscere il gioco

Ogni build Unity ha una cartella che finisce in `_Data` con dentro
`il2cpp_data`: cercare quella pesca qualsiasi gioco Unity installato. Il gioco
giusto si riconosce da `app.info`, un file di poche decine di byte con editore e
nome del prodotto — qui «Mudtek / Dimraeth». Se manca o è vuoto si ripiega sul
nome della cartella e sull'eseguibile che sta accanto.

`prova_ricerca.py` passa **tutte** le cartelle `_Data` presenti sul computer e
verifica che ne venga riconosciuta una sola.

La ricerca si può interrompere in qualunque momento, e guarda solo i dischi
**fissi**: niente chiavette, niente unità di rete, che sono lente e non
contengono giochi installati.

## Come è stata fatta la traduzione

Non a lotti indipendenti, e non per caso. Metà delle voci erano **nomi brevi**,
e i nomi ricorrono dentro le descrizioni di mezzo gioco: `Frost Javelin` compare
nelle abilità, negli incantesimi, nel codice e sugli oggetti. Tradurre una
categoria per volta significava dare tre nomi diversi allo stesso incantesimo.

Quindi **prima tutti i nomi, poi tutte le descrizioni**, e i nomi nell'ordine in
cui si citano: incantesimi → oggetti, equipaggiamento e luoghi → abilità e
passive → codice.

A sorvegliare la coerenza ci sono strumenti fatti apposta, che restano nel
progetto della traduzione:

- una guardia che sorveglia **2.283 nomi** e segnala quando un testo ne nomina
  uno senza usare la resa decisa;
- una che trova le **voci gemelle** — 1.612 stringhe inglesi compaiono in più
  categorie — e riporta la resa già scelta invece di ritradurre;
- una che confronta **i numeri** dell'inglese e dell'italiano, perché nelle
  descrizioni delle abilità il numero è il contenuto e uno sbagliato suona
  benissimo dicendo una cosa falsa.

Hanno intercettato cose che a occhio non si vedevano: la stessa abilità chiamata
*Rappresaglia* nel grimorio e *Ritorsione* nella sua descrizione, un materiale
reso in quattro modi diversi, due oggetti distinti finiti con lo stesso nome, e
missioni che chiedevano un oggetto con un nome che nell'inventario non esisteva.

## Due difetti del gioco, non della patch

**L'etichetta della classe va a capo in creazione personaggio.** Sotto l'icona
della classe, `Ombra` si legge `Ombr` + `a`. Non è un problema di lunghezza:
`Ombra` è il 17% più **stretta** di `Shadow`, che in inglese sta in riga.
Indagato a fondo e chiuso senza soluzione dal lato dei testi — il widget non ha
un riquadro stretto, la larghezza è quella della stringa stessa, e il kerning è
escluso alla fonte perché la tabella del font è vuota.

**Due stringhe portoghesi nel CSV inglese**: `Continuar Jogo` e il messaggio di
fine demo. Sono nella corsia `en` dell'originale, non è la patch.
