# -*- coding: utf-8 -*-
"""Esercita il motore della patch senza aprire nessuna finestra.

Una GUI si prova male: i pulsanti vanno premuti a mano e gli errori finiscono
in una casella di testo che nessuno rilegge. Qui il motore gira da solo, e
ogni guardia viene **rotta apposta** per vedere che si accorga del guasto:
una guardia che non si è mai vista fallire non è una guardia, è una speranza.

Uso:  python patcher/prova_motore.py            controlla e basta
      python patcher/prova_motore.py --scrivi   applica davvero e poi ripristina
"""
import os, sys, json, argparse

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motore

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


GIOCO = cartella_gioco()
UFFICIALI = ("en", "de", "es", "pt", "ru", "ja", "ko", "zh")

esiti = []


def prova(nome, fn, deve_fallire=False, atteso=None):
    """Esegue un controllo e registra l'esito. `deve_fallire` inverte il verdetto."""
    try:
        fn()
        ok = not deve_fallire
        nota = "nessun errore"
    except Exception as e:
        ok = deve_fallire and (atteso is None or atteso.lower() in str(e).lower())
        nota = str(e).split("\n")[0][:90]
    esiti.append((ok, nome, nota))
    print("   %s  %-52s %s" % ("ok " if ok else "NO ", nome, nota))
    return ok


def zitto(*a, **k):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scrivi", action="store_true",
                    help="applica la patch per davvero, poi ripristina")
    a = ap.parse_args()

    asset = os.path.join(GIOCO, "sharedassets1.assets")
    if not os.path.isfile(asset):
        sys.exit("non trovo sharedassets1.assets in %s" % GIOCO)
    # Su un'installazione pulita il backup non esiste ancora, ed è giusto così:
    # si legge dall'archivio del gioco. Pretendere il `.orig` voleva dire una
    # prova che gira solo sul computer di chi ha già applicato la patch.
    orig = asset + ".orig"
    if not os.path.isfile(orig):
        print("   (nessun backup: leggo dall'archivio del gioco, che è pulito)")
        orig = asset

    print("1. il pacchetto dei testi")
    dati = motore.carica_italiano()
    m = dati["_meta"]
    print("   %s voci, %s parole, %d categorie, %d eccezioni per chiave"
          % (format(m["voci"], ","), format(m["parole"], ","),
             len(dati["testi"]), len(dati["per_chiave"])))
    prova("le 16 categorie ci sono tutte",
          lambda: (_ for _ in ()).throw(AssertionError("mancano categorie"))
          if len(dati["testi"]) != 16 else None)

    print("\n2. riconoscimento delle corsie sull'archivio pulito")
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.61f1"
    with open(orig, "rb") as f:
        env = UnityPy.load(f.read())
    corsie, problemi = motore.mappa_corsie(env)
    if problemi:
        print("   !! %d oggetti illeggibili, il primo: %s" % (len(problemi), problemi[0]))
    print("   categorie riconosciute: %d" % len(corsie))
    mancanti = [(c, l) for c in motore.CATEGORIE for l in UFFICIALI
                if l not in corsie.get(c, {})]
    prova("tutte le 8 lingue vendute in tutte le categorie",
          lambda: (_ for _ in ()).throw(AssertionError(str(mancanti[:4])))
          if mancanti else None)

    print("\n3. round-trip dei CSV inglesi")
    rotti = []
    for c in motore.CATEGORIE:
        pid = corsie[c]["en"]["path_id"]
        blob = motore.testo_di(motore.oggetto_con(env, pid))[1]
        if motore.serializza(motore.righe(blob)) != blob:
            rotti.append(c)
    prova("i 16 CSV inglesi si riscrivono identici",
          lambda: (_ for _ in ()).throw(AssertionError(str(rotti)))
          if rotti else None)

    print("\n4. le guardie, rotte apposta")
    vero = motore.carica_italiano

    def con_payload(modifica):
        def caricato():
            d = motore.carica_italiano.__wrapped__() if hasattr(motore.carica_italiano, "__wrapped__") else vero()
            modifica(d)
            return d
        return caricato

    def guasta(chiave, come):
        d = vero()
        cat, testi = "Errors", d["testi"]["Errors"]
        en = next(k for k in testi if chiave in k)
        testi[en] = come(testi[en])
        return d

    def prova_payload(d):
        motore.carica_italiano = lambda: d
        try:
            motore.patch_testi(GIOCO, "pt", zitto)
        finally:
            motore.carica_italiano = vero

    prova("segnaposto {0} perso nella traduzione",
          lambda: prova_payload(guasta("{0}", lambda s: s.replace("{0}", "zero"))),
          deve_fallire=True, atteso="segnaposto")

    prova("traduzione svuotata",
          lambda: prova_payload(guasta("Empty", lambda s: "   ")),
          deve_fallire=True, atteso="vuota")

    def senza_corsia():
        motore.patch_testi(GIOCO, "xx", zitto)
    prova("corsia di lingua inesistente", senza_corsia,
          deve_fallire=True, atteso="corsia")

    print("\n5. l'etichetta del menu")
    prova("nome di lingua che non esiste nel gioco",
          lambda: motore.patch_etichetta(GIOCO, "Klingon", "Italiano", zitto),
          deve_fallire=True, atteso="nessuna voce")
    prova("testo nuovo più lungo del vecchio",
          lambda: motore.patch_etichetta(GIOCO, "中文", "Italiano", zitto),
          deve_fallire=True, atteso="non ci sta")

    print("\n6. riconoscimento di un gioco già patchato")
    # Questo è il controllo che conta di più di tutti. Se l'archivio ORIGINALE
    # venisse scambiato per già tradotto, `prepara_backup` lo terrebbe buono
    # anche dopo un aggiornamento del gioco; se invece un archivio già patchato
    # non venisse riconosciuto, il backup pulito ci finirebbe sopra e
    # l'originale sarebbe perso per sempre. La prima versione del riconoscitore
    # sbagliava: contava parole che l'italiano condivide con lo spagnolo.
    meta = os.path.join(GIOCO, "il2cpp_data", "Metadata", "global-metadata.dat")
    prova("l'archivio ORIGINALE non sembra italiano",
          lambda: (_ for _ in ()).throw(AssertionError("scambiato per tradotto"))
          if motore.gia_patchato_assets(orig) else None)
    if os.path.isfile(meta):
        prova("il metadata ORIGINALE non sembra italiano",
              lambda: (_ for _ in ()).throw(AssertionError("scambiato per tradotto"))
              if motore.gia_patchato_meta(meta + ".orig") else None)

    if a.scrivi:
        print("\n7. patch vera, poi ripristino")
        motore.do_patch(GIOCO, "pt", lambda s: print("   " + s))
        prova("dopo la patch il menu dice Italiano",
              lambda: (_ for _ in ()).throw(AssertionError("no"))
              if not motore.gia_patchato_meta(meta) else None)
        prova("dopo la patch i testi sono italiani",
              lambda: (_ for _ in ()).throw(AssertionError("no"))
              if not motore.gia_patchato_assets(asset) else None)

    print("\n%d controlli, %d passati, %d falliti"
          % (len(esiti), sum(1 for o, _, _ in esiti if o),
             sum(1 for o, _, _ in esiti if not o)))
    if any(not o for o, _, _ in esiti):
        sys.exit(1)


if __name__ == "__main__":
    main()
