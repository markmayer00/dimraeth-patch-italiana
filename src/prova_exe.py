# -*- coding: utf-8 -*-
"""Esercita l'ESEGUIBILE compilato, non i sorgenti.

Questa prova nasce da un difetto vero. Le altre provano il motore con il Python
di sistema, e passavano tutte; l'eseguibile si apriva, mostrava il banner e
trovava il gioco, e sembrava a posto. Poi, al momento di applicare, diceva
«Ho riconosciuto 0 categorie di testo su 16: questa versione del gioco non è
supportata» — e non era vero niente: il gioco era quello giusto.

Mancava `UnityPy/resources/lzma.tpk` dentro il pacchetto. È un file di **dati**,
e `--collect-submodules` raccoglie solo i moduli Python. Senza quello, su una
build IL2CPP — che i type tree non li porta dentro — UnityPy non ha come
interpretare gli oggetti, ogni `read()` falliva, e il conteggio restava a zero.

Morale: un programma compilato va provato **mentre fa il lavoro**, non mentre
si apre. Per questo l'eseguibile ha una modalità senza finestra.

Uso:  python patcher/prova_exe.py [<cartella Dimraeth_Data>]
"""
import os, sys, subprocess, tempfile

sys.stdout.reconfigure(encoding="utf-8")
QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
import motore

EXE = os.path.join(QUI, "dist", "PatchItaliana_Dimraeth.exe")
esiti = []


def cartella_gioco():
    for p in (sys.argv[1] if len(sys.argv) > 1 else None,
              os.environ.get("DIMRAETH_DATA")):
        if p and os.path.isdir(p):
            return p
    import dimraeth_patch_gui as g
    trovati = g.scan_game_dirs(lambda s: None, want=1)
    if trovati:
        return trovati[0]
    sys.exit(chr(10).join([
        "Non trovo l'installazione di Dimraeth.",
        "Indicala tu:  python %s <cartella Dimraeth_Data>" % os.path.basename(sys.argv[0]),
        "oppure metti il percorso nella variabile d'ambiente DIMRAETH_DATA."]))


def chiedi(nome, ok, dettaglio=""):
    esiti.append((bool(ok), nome))
    print("   %s  %-52s %s" % ("ok " if ok else "NO ", nome, dettaglio))


def lancia(*args):
    """Fa girare l'eseguibile e restituisce (codice di uscita, quello che ha detto)."""
    with tempfile.TemporaryDirectory() as d:
        log = os.path.join(d, "log.txt")
        r = subprocess.run([EXE] + list(args) + ["--log", log],
                           capture_output=True, timeout=900)
        testo = ""
        if os.path.isfile(log):
            testo = open(log, encoding="utf-8", errors="replace").read()
        return r.returncode, testo


def main():
    gioco = cartella_gioco()
    if not os.path.isfile(EXE):
        sys.exit("manca %s: compila prima l'eseguibile" % EXE)
    print("eseguibile: %s (%s byte)" % (os.path.basename(EXE),
                                        format(os.path.getsize(EXE), ",")))
    print("gioco:      %s" % gioco)

    asset = os.path.join(gioco, "sharedassets1.assets")
    meta = os.path.join(gioco, "il2cpp_data", "Metadata", "global-metadata.dat")

    print("\n1. una cartella che non è il gioco")
    codice, testo = lancia(os.path.expanduser("~"))
    chiedi("fallisce, e dice perché", codice != 0 and "ERRORE" in testo,
           testo.strip().split(chr(10))[-2][:60] if testo else "nessun messaggio")

    print("\n2. applica per davvero")
    codice, testo = lancia(gioco, "--lingua", "pt")
    chiedi("l'eseguibile applica la patch", codice == 0 and "riuscito" in testo,
           "uscita %d" % codice)
    righe = [r for r in testo.splitlines() if "Righe tradotte" in r]
    chiedi("ha tradotto delle righe", bool(righe), righe[0].strip() if righe else "")
    chiedi("ha rinominato la voce del menu", "Italiano" in testo)

    print("\n3. il gioco, guardato dopo")
    chiedi("il menu adesso dice Italiano", motore.gia_patchato_meta(meta))
    chiedi("i testi adesso sono italiani", motore.gia_patchato_assets(asset))
    chiedi("i backup ci sono tutti e due",
           os.path.isfile(asset + ".orig") and os.path.isfile(meta + ".orig"))

    print("\n4. riapplicare non impila")
    codice, testo2 = lancia(gioco, "--lingua", "pt")
    r2 = [r for r in testo2.splitlines() if "Righe tradotte" in r]
    chiedi("la seconda passata dà lo stesso conteggio",
           bool(r2) and bool(righe) and r2[0] == righe[0],
           r2[0].strip() if r2 else "")

    print("\n5. ripristino")
    codice, testo = lancia(gioco, "--ripristina")
    chiedi("l'eseguibile ripristina", codice == 0 and "riuscito" in testo)
    chiedi("il menu è tornato com'era", not motore.gia_patchato_meta(meta))
    chiedi("i testi sono tornati com'erano", not motore.gia_patchato_assets(asset))

    print("\n%d controlli, %d passati, %d falliti"
          % (len(esiti), sum(1 for o, _ in esiti if o),
             sum(1 for o, _ in esiti if not o)))
    if any(not o for o, _ in esiti):
        sys.exit(1)


if __name__ == "__main__":
    main()
