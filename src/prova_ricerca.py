# -*- coding: utf-8 -*-
"""Prova la ricerca dell'installazione: che trovi Dimraeth e non altro.

Sono i due difetti già pagati su Moonlighter 2, e qui vengono rimessi alla
prova invece di essere dati per risolti:

1. **Gli altri giochi Unity finivano nella ricerca.** Ogni build Unity ha una
   cartella che finisce in `_Data` con dentro `il2cpp_data`: cercare quella
   pescava Raft, Aim Lab e tutto il resto. Si riconosce il gioco giusto da
   `app.info`, che porta editore e nome del prodotto.

2. **La ricerca non si poteva fermare.** Chi ha più dischi aspettava che
   finisse di frugarli tutti. Adesso c'è un `threading.Event` che la
   interrompe, e lo stesso pulsante che la avvia la ferma.

Uso:  python patcher/prova_ricerca.py
"""
import os, sys, time, threading

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dimraeth_patch_gui as g

def cartella_gioco():
    """Dove sta il gioco su QUESTO computer.

    Il percorso non si può cablare: queste prove devono poter girare anche su
    un altro computer, dove il gioco sta in una libreria Steam invece che in
    Downloads. Si prende dal primo argomento, o dalla variabile d'ambiente
    DIMRAETH_DATA, e come ultima spiaggia si cerca da soli.
    """
    for p in (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None,
              os.environ.get("DIMRAETH_DATA")):
        if p and os.path.isdir(p):
            return p
    import dimraeth_patch_gui as _g
    trovati = _g.scan_game_dirs(lambda s: None, want=1)
    if trovati:
        return trovati[0]
    sys.exit(chr(10).join([
        "Non trovo l'installazione di Dimraeth.",
        "Indicala tu:  python %s <cartella Dimraeth_Data>" % os.path.basename(sys.argv[0]),
        "oppure metti il percorso nella variabile d'ambiente DIMRAETH_DATA."]))


DIMRAETH = cartella_gioco()
esiti = []


def chiedi(nome, ok, dettaglio=""):
    esiti.append((bool(ok), nome))
    print("   %s  %-56s %s" % ("ok " if ok else "NO ", nome, dettaglio))


def cartelle_data(radici, limite=3):
    """Tutte le cartelle `_Data` che stanno su questo computer."""
    fuori = []
    for root in radici:
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            if dp.count(os.sep) - root.count(os.sep) > limite:
                dn[:] = []
                continue
            if os.path.basename(dp).endswith("_Data"):
                fuori.append((dp, fn, list(dn)))
                dn[:] = []
    return fuori


def main():
    print("1. riconoscere Dimraeth e NON gli altri giochi Unity")
    radici = [os.path.expanduser("~/Downloads"),
              r"C:\Program Files (x86)\Steam\steamapps\common",
              r"C:\Program Files\Steam\steamapps\common",
              r"D:\SteamLibrary\steamapps\common"]
    tutte = cartelle_data(radici)
    print("   cartelle _Data trovate su questo computer: %d" % len(tutte))
    if len(tutte) < 2:
        print("   (serve almeno un altro gioco Unity installato per provare davvero)")

    nostre = [d for d, f, n in tutte if g.looks_like_game(d, f, n)]
    chiedi("Dimraeth viene riconosciuto",
           any(os.path.normcase(d) == os.path.normcase(DIMRAETH) for d in nostre),
           "%d riconosciute" % len(nostre))
    intrusi = [d for d in nostre if os.path.normcase(d) != os.path.normcase(DIMRAETH)]
    chiedi("nessun altro gioco Unity viene scambiato per Dimraeth",
           not intrusi, ", ".join(os.path.basename(d) for d in intrusi[:3]))
    for d, f, n in tutte:
        if os.path.normcase(d) == os.path.normcase(DIMRAETH):
            continue
        print("      scartato: %-52s" % os.path.basename(d)[:52])

    print("\n2. la ricerca si può interrompere")
    stop = threading.Event()
    stop.set()
    t0 = time.time()
    trovati = g.scan_game_dirs(lambda s: None, stop=stop)
    dt = time.time() - t0
    chiedi("con lo stop già alzato torna subito", dt < 2.0 and not trovati,
           "%.2f s, %d trovati" % (dt, len(trovati)))

    stop2 = threading.Event()
    visti = []
    t0 = time.time()

    def alza():
        time.sleep(1.5)
        stop2.set()

    threading.Thread(target=alza, daemon=True).start()
    g.scan_game_dirs(visti.append, want=99, stop=stop2)
    dt = time.time() - t0
    chiedi("interrotta a metà si ferma entro pochi secondi", dt < 25,
           "%.1f s, %d cartelle guardate" % (dt, len(visti)))

    print("\n3. la ricerca non tocca i dischi che non sono fissi")
    fissi = g.dischi_fissi()
    chiedi("almeno un disco fisso riconosciuto", bool(fissi), "".join(fissi))
    radici_scan = g.candidate_roots()
    chiedi("nessuna radice fuori dai dischi fissi",
           all(r[0].upper() in fissi for r in radici_scan if len(r) > 1 and r[1] == ":"),
           "%d radici" % len(radici_scan))

    print("\n%d controlli, %d passati, %d falliti"
          % (len(esiti), sum(1 for o, _ in esiti if o),
             sum(1 for o, _ in esiti if not o)))
    if any(not o for o, _ in esiti):
        sys.exit(1)


if __name__ == "__main__":
    main()
