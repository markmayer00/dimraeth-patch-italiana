# -*- coding: utf-8 -*-
"""Apre la finestra per davvero e controlla che ci sia tutto, poi la chiude.

Il `mainloop` va avviato: senza, i widget non si disegnano e ogni controllo
sullo stato dei pulsanti dà un falso negativo. Quindi si fa partire la finestra
vera e i controlli si programmano con `after`.

Uso:  python patcher/prova_finestra.py
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
esiti = []


def chiedi(nome, condizione, dettaglio=""):
    ok = bool(condizione)
    esiti.append((ok, nome))
    print("   %s  %-50s %s" % ("ok " if ok else "NO ", nome, dettaglio))


def main():
    import dimraeth_patch_gui as g
    app = g.App()
    # La ricerca automatica parte dopo 300 ms: dandole subito una cartella non
    # si mette a frugare nei dischi durante la prova.
    app.var_game.set(GIOCO)

    def controlla():
        try:
            print("finestra:")
            chiedi("il banner è stato caricato", app.banner_src is not None,
                   str(getattr(app.banner_src, "size", "")))
            chiedi("la finestra ha un titolo", app.title() == g.APP, app.title())
            chiedi("la tendina elenca le 7 lingue cedibili",
                   len(app.cmb.cget("values")) == len(g.LINGUE),
                   str(len(app.cmb.cget("values"))))
            chiedi("la prima voce della tendina è il portoghese",
                   "Portoghese" in app.var_lang.get(), app.var_lang.get())
            corsia, nome = app.scelta()
            chiedi("la scelta si traduce in (corsia, nome del menu)",
                   (corsia, nome) == ("pt", "Português"), "%s / %s" % (corsia, nome))
            chiedi("i tre pulsanti esistono e sono attivi",
                   all(str(b["state"]) == "normal"
                       for b in (app.btn_auto, app.btn_go, app.btn_undo)))
            testo = app.txt.get("1.0", "end")
            chiedi("il riquadro dei messaggi ha il benvenuto", "Benvenuto" in testo)
            chiedi("la scritta scorrevole si muove", app.scroll_lbl.cget("text") != "")
            chiedi("la cartella del gioco è quella indicata",
                   app.var_game.get() == GIOCO)
            # ogni voce della tendina deve risolversi in una corsia vera
            buone = 0
            for _, _, etichetta in g.LINGUE:
                app.var_lang.set(etichetta)
                c, n = app.scelta()
                if c and n:
                    buone += 1
            chiedi("tutte le voci della tendina si risolvono", buone == len(g.LINGUE),
                   "%d/%d" % (buone, len(g.LINGUE)))
            chiedi("riconosce la cartella del gioco",
                   g.looks_like_game(GIOCO, os.listdir(GIOCO),
                                     [d for d in os.listdir(GIOCO)
                                      if os.path.isdir(os.path.join(GIOCO, d))]))
            chiedi("NON scambia una cartella qualunque per il gioco",
                   not g.looks_like_game(os.path.expanduser("~"), [], []))
        finally:
            app.destroy()

    app.after(700, controlla)
    app.mainloop()

    # Nei crediti c'è scritto che senza l'immagine il programma funziona lo
    # stesso: è una promessa, quindi va provata invece che data per buona.
    print("\nsenza il banner:")
    vero = g.res_path
    g.res_path = lambda n: vero(n) if n != "banner.png" else vero("non_esiste.png")
    try:
        app2 = g.App()
        app2.var_game.set(GIOCO)

        def controlla2():
            try:
                chiedi("la finestra si apre lo stesso", True)
                chiedi("il banner risulta assente", app2.banner_src is None)
                chiedi("i pulsanti ci sono comunque",
                       all(str(b["state"]) == "normal"
                           for b in (app2.btn_auto, app2.btn_go, app2.btn_undo)))
            finally:
                app2.destroy()

        app2.after(500, controlla2)
        app2.mainloop()
    except Exception as e:
        chiedi("la finestra si apre lo stesso", False, str(e)[:70])
    finally:
        g.res_path = vero

    print("\n%d controlli, %d passati, %d falliti"
          % (len(esiti), sum(1 for o, _ in esiti if o),
             sum(1 for o, _ in esiti if not o)))
    if any(not o for o, _ in esiti):
        sys.exit(1)


if __name__ == "__main__":
    main()
