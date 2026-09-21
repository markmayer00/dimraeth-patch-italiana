# -*- coding: utf-8 -*-
"""Tira fuori dal gioco le due immagini che servono al banner.

Sono texture del gioco, dentro `sharedassets1.assets`: il ritratto di Eldorian
e il logo del titolo. Si cercano **per nome**, non per path_id: i path_id
cambiano a ogni build del gioco, i nomi no.

Uso:  python patcher/estrai_grafica.py
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")
import UnityPy

UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.61f1"

QUI = os.path.dirname(os.path.abspath(__file__))
GRAFICA = os.path.join(QUI, "grafica")


def cartella_gioco():
    """Dove sta il gioco su QUESTO computer.

    Il percorso non si può cablare: chi rigenera le immagini ha il gioco dove
    ce l'ha lui. Si prende dal primo argomento, o dalla variabile d'ambiente
    DIMRAETH_DATA, e come ultima spiaggia lo si cerca da soli.
    """
    for p in (sys.argv[1] if len(sys.argv) > 1 else None,
              os.environ.get("DIMRAETH_DATA")):
        if p and os.path.isdir(p):
            return p
    sys.path.insert(0, QUI)
    import dimraeth_patch_gui as g
    trovati = g.scan_game_dirs(lambda s: None, want=1)
    if trovati:
        return trovati[0]
    sys.exit(chr(10).join([
        "Non trovo l'installazione di Dimraeth.",
        "Indicala tu:  python %s <cartella Dimraeth_Data>" % os.path.basename(sys.argv[0]),
        "oppure metti il percorso nella variabile d'ambiente DIMRAETH_DATA."]))

VOLUTE = {
    "Eldorian_Guildhall_Export": "eldorian.png",
    "Title 3 Updated w Shadow": "titolo.png",
}


def main():
    gioco = cartella_gioco()
    asset = os.path.join(gioco, "sharedassets1.assets")
    orig = asset + ".orig"
    # Se il gioco è già patchato, le texture stanno uguali in tutti e due i
    # file — sono immagini, la patch tocca solo il testo — ma partire
    # dall'originale è comunque la scelta giusta per abitudine.
    sorgente = orig if os.path.isfile(orig) else asset
    if not os.path.isfile(sorgente):
        sys.exit("non trovo l'archivio del gioco in %s" % gioco)
    os.makedirs(GRAFICA, exist_ok=True)

    env = UnityPy.load(sorgente)
    trovate = {}
    for o in env.objects:
        if o.type.name != "Texture2D":
            continue
        try:
            d = o.read()
        except Exception:
            continue
        nome = getattr(d, "m_Name", "")
        if nome in VOLUTE and nome not in trovate:
            p = os.path.join(GRAFICA, VOLUTE[nome])
            d.image.save(p)
            trovate[nome] = (p, d.image.size)
            print("   %-30s -> %s  %dx%d" % (nome, VOLUTE[nome], *d.image.size))

    mancano = [n for n in VOLUTE if n not in trovate]
    if mancano:
        sys.exit("!! non ho trovato queste texture: %s\n"
                 "   il gioco è cambiato: cerca i nomi nuovi e aggiorna VOLUTE" % mancano)
    print("fatte %d immagini in %s" % (len(trovate), GRAFICA))


if __name__ == "__main__":
    main()
