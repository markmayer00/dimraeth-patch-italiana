# -*- coding: utf-8 -*-
"""Disegna i bottoni del README.

Nel Markdown di GitHub non si può usare CSS: un bottone vero si ottiene solo
con un'immagine dentro un link. Vengono disegnati a tripla risoluzione e
mostrati più piccoli, così restano nitidi anche sugli schermi ad alta densità.

Il download è il bottone principale (oro pieno); gli altri sono secondari
(fondo scuro, bordo colorato) per non rubargli l'attenzione. I colori sono
quelli del gioco: l'oro bronzeo delle cornici e il blu notte dei menu.

Uso:  python patcher/make_bottone.py
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

S = 3                                    # sovracampionamento
H = 62 * S
R = 10 * S
QUI = os.path.dirname(os.path.abspath(__file__))
GRAFICA = os.path.join(QUI, "grafica")

ORO_ALTO, ORO_BASSO = (226, 180, 96), (169, 123, 47)
SCURO = (18, 21, 31)
ORO = (217, 164, 65)
OSSO = (196, 186, 168)
BLU_DISCORD = (110, 122, 240)
TESTO_SCURO = (24, 18, 7)


def font(nome, size):
    for f in (nome, "seguisb.ttf", "segoeui.ttf", "arial.ttf"):
        p = os.path.join(r"C:\Windows\Fonts", f)
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


F = font("seguisb.ttf", 19 * S)


def freccia_giu(d, cx, cy, col):
    d.rectangle([cx - 2 * S, cy - 11 * S, cx + 2 * S, cy + 2 * S], fill=col)
    d.polygon([(cx - 8 * S, cy + 1 * S), (cx + 8 * S, cy + 1 * S), (cx, cy + 10 * S)], fill=col)
    d.rectangle([cx - 10 * S, cy + 13 * S, cx + 10 * S, cy + 16 * S], fill=col)


def punto_esclamativo(d, cx, cy, col):
    r = 12 * S
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=2 * S)
    d.rectangle([cx - 1.5 * S, cy - 7 * S, cx + 1.5 * S, cy + 2 * S], fill=col)
    d.ellipse([cx - 2 * S, cy + 5 * S, cx + 2 * S, cy + 9 * S], fill=col)


def libro(d, cx, cy, col):
    """Un libro aperto: l'interfaccia di Dimraeth è tutta pagine di libro."""
    w, h = 26 * S, 18 * S
    d.line([(cx, cy - h // 2 + 2 * S), (cx, cy + h // 2)], fill=col, width=2 * S)
    for verso in (-1, 1):
        d.polygon([(cx, cy - h // 2 + 2 * S),
                   (cx + verso * w // 2, cy - h // 2),
                   (cx + verso * w // 2, cy + h // 2 - 2 * S),
                   (cx, cy + h // 2)], outline=col, width=2 * S)


def fumetto(d, cx, cy, col):
    """Un fumetto di chat: la comunita'."""
    w, h = 24 * S, 17 * S
    d.rounded_rectangle([cx - w // 2, cy - h // 2 - 2 * S, cx + w // 2, cy + h // 2 - 2 * S],
                        radius=5 * S, outline=col, width=2 * S)
    d.polygon([(cx - 5 * S, cy + h // 2 - 3 * S), (cx + 1 * S, cy + h // 2 - 3 * S),
               (cx - 4 * S, cy + h // 2 + 5 * S)], fill=col)


def lista(d, cx, cy, col):
    """Un foglio con delle righe: l'elenco delle novità."""
    w, h = 19 * S, 24 * S
    d.rounded_rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
                        radius=2 * S, outline=col, width=2 * S)
    for i, larg in enumerate((10, 8, 10)):
        y = cy - 6 * S + i * 6 * S
        d.rectangle([cx - 5 * S, y - S, cx - 5 * S + larg * S, y + S], fill=col)


def bottone(nome, testo, icona, primario=False, colore=ORO):
    # la larghezza segue il testo: icona a sinistra, poi la scritta, poi il margine
    X_TESTO, MARGINE = 56 * S, 26 * S
    misura = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    W = int(X_TESTO + misura.textlength(testo, font=F) + MARGINE)
    btn = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=R, fill=255)

    if primario:
        grad = Image.new("RGB", (1, H))
        gd = ImageDraw.Draw(grad)
        for y in range(H):
            t = y / H
            gd.point((0, y), fill=tuple(round(ORO_ALTO[i] + (ORO_BASSO[i] - ORO_ALTO[i]) * t)
                                        for i in range(3)))
        btn.paste(grad.resize((W, H)), (0, 0), mask)
        col_testo = TESTO_SCURO
        bordo = (248, 220, 160, 130)
    else:
        btn.paste(Image.new("RGB", (W, H), SCURO), (0, 0), mask)
        col_testo = colore
        bordo = colore + (185,)

    d = ImageDraw.Draw(btn)
    d.rounded_rectangle([1, 1, W - 2, H - 2], radius=R - 1, outline=bordo, width=S)
    icona(d, 30 * S, H // 2, col_testo)
    d.text((X_TESTO, (H - 24 * S) / 2), testo, font=F, fill=col_testo)

    btn = btn.resize((W // S, H // S), Image.LANCZOS)
    os.makedirs(GRAFICA, exist_ok=True)
    out = os.path.join(GRAFICA, nome)
    btn.save(out)
    print("   %-26s %dx%d  %s byte" % (nome, *btn.size, format(os.path.getsize(out), ",")))


if __name__ == "__main__":
    bottone("bottone-download.png", "SCARICA LA PATCH", freccia_giu, primario=True)
    bottone("bottone-segnala.png", "SEGNALA UN PROBLEMA", punto_esclamativo)
    bottone("bottone-comefunziona.png", "COME FUNZIONA", libro, colore=OSSO)
    bottone("bottone-discord.png", "DISCORD DEI TWR", fumetto, colore=BLU_DISCORD)
    bottone("bottone-novita.png", "NOVITÀ", lista, colore=(150, 160, 190))
