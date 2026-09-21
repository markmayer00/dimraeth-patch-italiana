# -*- coding: utf-8 -*-
"""Compone il banner del launcher: notte, Eldorian, il logo del gioco.

Le due immagini vengono dal gioco stesso, estratte da `sharedassets1.assets`:
il ritratto di Eldorian (`Eldorian_Guildhall_Export`) e il logo del titolo
(`Title 3 Updated w Shadow`). Se mancano, `estrai_grafica.py` le rifà.

Il ritratto è su fondo trasparente e il personaggio sta tutto a destra: è la
forma giusta per un banner, perché lascia libera la metà sinistra per il titolo.
Si ritaglia sul riquadro dell'alfa invece che a coordinate fisse, così se un
giorno l'artwork cambia il montaggio regge lo stesso.

Uso:  python patcher/make_banner.py
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

QUI = os.path.dirname(os.path.abspath(__file__))
GRAFICA = os.path.join(QUI, "grafica")
RITRATTO = os.path.join(GRAFICA, "eldorian.png")
LOGO = os.path.join(GRAFICA, "titolo.png")
OUT = os.path.join(QUI, "banner.png")

W, H = 1600, 400

NOTTE_ALTO = (10, 14, 28)
NOTTE_BASSO = (4, 6, 14)
OSSO = "#efe3cf"          # il bianco caldo del logo del gioco
ORO = "#d8a champagne"    # sostituito sotto: tenuto qui solo per leggibilità
ORO = "#d9a441"
GRIGIO = "#9aa2bd"
GRIGIO_2 = "#6f7794"
FILO = "#a97b2f"


def font(nome, size):
    for f in (nome, "seguisb.ttf", "segoeui.ttf", "arial.ttf"):
        p = os.path.join(r"C:\Windows\Fonts", f)
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def ombra(d, xy, testo, fnt, fill, offset=3, colore=(0, 0, 0, 180)):
    x, y = xy
    d.text((x + offset, y + offset), testo, font=fnt, fill=colore)
    d.text((x, y), testo, font=fnt, fill=fill)


def sfondo():
    """Cielo notturno in gradiente, con una velatura più scura in basso."""
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = (y / H) ** 1.2
        d.line([(0, y), (W, y)],
               fill=tuple(round(a + (b - a) * t) for a, b in zip(NOTTE_ALTO, NOTTE_BASSO)))
    return img


def ritaglia(p):
    """L'immagine ridotta al suo contenuto: via il trasparente intorno."""
    im = Image.open(p).convert("RGBA")
    bbox = im.getbbox()
    if not bbox:
        raise SystemExit("%s è tutta trasparente" % p)
    return im.crop(bbox)


def main():
    for p in (RITRATTO, LOGO):
        if not os.path.isfile(p):
            sys.exit("manca %s: lancia prima `python patcher/estrai_grafica.py`" % p)

    img = sfondo()

    # ---- Eldorian a destra, intero: alto quanto il banner, niente tagli
    rit = ritaglia(RITRATTO)
    rit = rit.resize((round(rit.width * H / rit.height), H), Image.LANCZOS)
    x_rit = W - rit.width - 24
    img.paste(rit, (x_rit, 0), rit)

    # ---- velatura da sinistra, che si spegne prima di arrivare sul personaggio:
    # serve a dare contrasto al titolo, non a mettere in ombra il ritratto.
    fine = x_rit - 40
    velo = Image.new("L", (W, 1))
    for x in range(W):
        t = x / fine
        velo.putpixel((x, 0), 0 if t >= 1 else round(240 * (1 - t) ** 1.6))
    img = Image.composite(Image.new("RGB", (W, H), "#06080f"), img, velo.resize((W, H)))

    # ---- il logo del gioco, a sinistra
    logo = ritaglia(LOGO)
    larg = 560
    logo = logo.resize((larg, round(logo.height * larg / logo.width)), Image.LANCZOS)
    X = 70
    img.paste(logo, (X, 66), logo)

    d = ImageDraw.Draw(img, "RGBA")
    f_sub = font("seguisb.ttf", 38)
    f_cre = font("seguisb.ttf", 25)
    f_cre2 = font("segoeui.ttf", 25)

    y = 66 + logo.height + 26
    ombra(d, (X + 4, y), "Traduzione italiana completa", f_sub, OSSO)

    y2 = y + 56
    primo = "MarkMayer"
    ombra(d, (X + 4, y2), primo, f_cre, GRIGIO, 2)
    larg_t = d.textlength(primo, font=f_cre)
    ombra(d, (X + 4 + larg_t + 22, y2), "·   con i TWR   ·   14.995 voci",
          f_cre2, GRIGIO_2, 2)

    # ---- filo dorato in basso
    d.rectangle([0, H - 6, W, H], fill=FILO)

    img.save(OUT)
    print("scritto", OUT, img.size, format(os.path.getsize(OUT), ","), "byte")


if __name__ == "__main__":
    main()
