# -*- coding: utf-8 -*-
"""Il motore della patch: tutto quello che tocca i file del gioco.

Sta separato dalla finestra apposta, così si può provare senza interfaccia —
`python patcher/prova_motore.py` lo esercita per intero.

Dimraeth va patchato in **due file**, e non è un dettaglio:

  - `sharedassets1.assets` contiene i testi, in 16 CSV `Key,Text` per ognuna
    delle 10 corsie di lingua. L'italiano prende il posto di una corsia.
  - `global-metadata.dat` contiene il nome che il menu dà a quella lingua:
    *Português*, *Deutsch*… sono letterali C# compilati, non righe di CSV.
    Senza questo secondo passaggio l'italiano ci sarebbe, ma il giocatore
    dovrebbe sceglierlo sotto il nome di un'altra lingua.

Ognuno dei due ha il suo backup `.orig`, e si riparte **sempre** da quello:
così la patch si può riapplicare quante volte si vuole senza impilare
modifiche sopra modifiche.
"""
import os, re, sys, json, gzip, shutil, struct, hashlib, collections

# ------------------------------------------------------------------ costanti

CATEGORIE = ["UI", "Items", "Equipment", "Spells", "Quests", "NPCDialogues", "Codex",
             "Cinematics", "Tutorials", "Skills", "Passives", "Attributes",
             "BuildItems", "POIMarkers", "InScene", "Errors"]

# corsia nei CSV, nome che il menu le dà, etichetta per chi installa.
# L'inglese non si offre: è il ripiego di tutto quello che non è tradotto, e
# sacrificarlo lascerebbe il giocatore senza una lingua comprensibile se
# qualcosa andasse storto.
LINGUE = [
    ("pt", "Português", "al posto del Portoghese  (consigliato)"),
    ("de", "Deutsch",   "al posto del Tedesco"),
    ("es", "Español",   "al posto dello Spagnolo"),
    ("ru", "Русский",   "al posto del Russo"),
    ("ja", "日本語",      "al posto del Giapponese"),
    ("ko", "한국어",      "al posto del Coreano"),
    ("zh", "中文",        "al posto del Cinese"),
]

BOM = "﻿"
SEGNAPOSTO = re.compile(r"\{[^}]*\}|%[sd]")
TAG = re.compile(r"<[^>]+>")

FIRMA_META = 0xFAB11BAF
VERSIONI_META = (29, 31)


def res_path(nome):
    """Un file che viaggia dentro l'eseguibile, o accanto al sorgente."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome)


def carica_italiano():
    with gzip.open(res_path("italiano.json.gz"), "rb") as f:
        return json.loads(f.read().decode("utf-8"))


# ------------------------------------------------------------------ i CSV

def righe(blob):
    """Il CSV del gioco spezzato in terne (chiave, testo, era quotato).

    Il formato è particolare e va rispettato alla lettera: UTF-8 con BOM, righe
    CRLF, chiave mai quotata, testo quasi sempre quotato, **intestazione non
    quotata**. Quest'ultimo dettaglio aveva fatto fallire il primo
    serializzatore del progetto, ed è stato preso da una guardia di round-trip,
    non dall'occhio.
    """
    txt = blob.decode("utf-8-sig", "replace")
    fuori = []
    for riga in txt.split("\r\n"):
        if not riga:
            continue
        i = riga.find(",")
        if i < 0:
            fuori.append((riga, None, False))
            continue
        k, v = riga[:i], riga[i + 1:]
        quotato = len(v) >= 2 and v.startswith('"') and v.endswith('"')
        if quotato:
            v = v[1:-1].replace('""', '"')
        fuori.append((k, v, quotato))
    return fuori


def serializza(terne):
    buf = [BOM]
    for k, v, q in terne:
        if v is None:
            buf.append(k + "\r\n")
        elif q:
            buf.append(k + ',"' + v.replace('"', '""') + '"\r\n')
        else:
            buf.append(k + "," + v + "\r\n")
    return "".join(buf).encode("utf-8")


def lingua(t):
    """Riconosce la lingua di un CSV dal suo contenuto.

    Si guarda il testo e non il nome né la posizione: i path_id cambiano a ogni
    build del gioco, e fidarsi di quelli vorrebbe dire una patch che si rompe al
    primo aggiornamento. L'ordine dei controlli conta: prima gli alfabeti, che
    sono inequivocabili, poi la pseudo-localizzazione, infine le lingue latine
    per parole funzione.
    """
    if len(t.strip()) <= 12:
        return "vuoto"
    if re.search(r"[Ѐ-ӿ]", t):
        return "ru"
    if re.search(r"[぀-ヿ]", t):
        return "ja"
    if re.search(r"[가-힯]", t):
        return "ko"
    if re.search(r"[Ạ-ỹ]|ươ|ế|ộ", t):
        return "vi"
    if re.search(r"[一-鿿]", t):
        return "zh"
    if len(re.findall(r"\[[ÁÉÍÓÚÞÐÑáéíóúþðñ]", t)) > 5 or t.count("áéíóú") > 3:
        return "pseudo"
    punteggi = {
        "de": len(re.findall(r"\b(der|die|das|und|nicht|dich|wird|Ihr)\b", t)) + t.count("ß"),
        "es": len(re.findall(r"\b(el|los|las|del|que|para|una|está)\b", t))
              + len(re.findall(r"ción|ñ", t)),
        "pt": len(re.findall(r"\b(não|você|uma|para|dos|das|pela)\b", t))
              + len(re.findall(r"ção|ã|õ", t)),
        "en": len(re.findall(r"\b(the|you|your|and|with|that|from|have|this)\b", t)),
    }
    return max(punteggi, key=punteggi.get)


def testo_di(oggetto):
    d = oggetto.read()
    s = getattr(d, "m_Script", b"") or b""
    if isinstance(s, str):
        s = s.encode("utf-8", "surrogateescape")
    return d, s


def mappa_corsie(env):
    """Per ogni categoria, quale TextAsset è quale lingua.

    Una categoria può avere due file classificati uguale: `Attributes` ha due
    corsie inglesi (una completa e una a metà, cioè una lingua mai tradotta che
    ricade sull'inglese). Vince la più grossa, che è quella buona come
    riferimento.
    """
    fuori = collections.defaultdict(dict)
    # Gli errori di lettura non si buttano via. Inghiottirli faceva dire al
    # programma «0 categorie: versione del gioco non supportata», che è una
    # diagnosi sbagliata e manda a cercare dalla parte opposta: la prima volta
    # che è successo, il gioco era quello giusto e mancava un file di dati di
    # UnityPy dentro l'eseguibile.
    fuori_problemi = []
    for o in env.objects:
        if o.type.name != "TextAsset":
            continue
        try:
            d, s = testo_di(o)
        except Exception as e:
            fuori_problemi.append("%s: %s" % (type(e).__name__, str(e)[:120]))
            continue
        nome = getattr(d, "m_Name", "")
        if nome not in CATEGORIE:
            continue
        lang = lingua(s.decode("utf-8-sig", "replace"))
        voce = {"path_id": o.path_id, "byte": len(s)}
        vecchia = fuori[nome].get(lang)
        if vecchia is None or voce["byte"] > vecchia["byte"]:
            fuori[nome][lang] = voce
    return fuori, fuori_problemi


def oggetto_con(env, path_id):
    for o in env.objects:
        if o.type.name == "TextAsset" and o.path_id == path_id:
            return o
    raise RuntimeError("TextAsset %d sparito dall'archivio" % path_id)


# ------------------------------------------------------------------ backup

def impronta(path, blocco=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(blocco)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# Parole funzione che l'italiano NON condivide con lo spagnolo e il portoghese,
# le uniche due lingue del gioco che gli somigliano. Un elenco più ovvio —
# `la`, `di`, `del`, `per`, `una`, `con` — sullo spagnolo prende 45 colpi e lo
# scambia per italiano: misurato, non immaginato.
PAROLE_ITALIANE = re.compile(r"\b(il|gli|degli|negli|della|delle|dello|nella|nelle|"
                             r"sulla|che|non|più|può|perché|così|anche|puoi|viene|"
                             r"essere|quello)\b")


def sembra_italiano(txt):
    """Il testo è nostro?

    Sullo stesso CSV di prova questo conta 0 per lo spagnolo e 98 per il nostro
    italiano: la soglia sta larga in mezzo, dove nessun rumore la raggiunge.
    """
    return len(PAROLE_ITALIANE.findall(txt.lower())) >= 20


def gia_patchato_assets(path):
    """Questo `sharedassets1.assets` l'abbiamo scritto noi?

    Serve quando manca il `.patchinfo` — per esempio perché la patch è stata
    applicata con una versione precedente, o dagli strumenti del progetto. Senza
    questa domanda il file patchato verrebbe scambiato per un aggiornamento del
    gioco, e il backup pulito ci finirebbe sopra: il vero originale sarebbe
    perso, e da lì in poi ogni patch ripartirebbe da un file già tradotto.
    """
    try:
        import UnityPy
        UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.61f1"
        with open(path, "rb") as f:
            env = UnityPy.load(f.read())
        for o in env.objects:
            if o.type.name != "TextAsset":
                continue
            try:
                d, s = testo_di(o)
            except Exception:
                continue
            if getattr(d, "m_Name", "") != "Errors":
                continue
            if sembra_italiano(s.decode("utf-8-sig", "replace")):
                return True
    except Exception:
        return False
    return False


def gia_patchato_meta(path):
    """Questo `global-metadata.dat` ha già la voce di menu in italiano?"""
    try:
        b, _, dati_off, lit = _leggi_meta(path)
    except Exception:
        return False
    return any(_testo_lit(b, dati_off, v) == "Italiano" for v in lit if v[0] == 8)


def prepara_backup(path, log, riconosci=None):
    """Garantisce un backup che corrisponda alla versione installata ADESSO.

    La patch riparte sempre dal backup. Se il gioco viene aggiornato e il backup
    resta quello vecchio, riapplicarla riporterebbe indietro il file e il
    giocatore si ritroverebbe la versione precedente senza capire perché. Per
    accorgersene, ogni patch registra l'impronta di quello che ha prodotto: se
    al giro dopo il file non è più quello, il gioco è cambiato.

    Quando l'impronta non c'è — patch applicata da una versione precedente o
    dagli strumenti del progetto — prima di dichiarare il backup scaduto si
    chiede a `riconosci` se quel file per caso non l'abbiamo scritto noi.
    Saltare questa domanda vuol dire sovrascrivere il backup pulito con un file
    già patchato, e perdere l'originale per sempre.
    """
    orig = path + ".orig"
    info = path + ".patchinfo"
    if not os.path.isfile(orig):
        log("Creo il backup di %s ..." % os.path.basename(path))
        shutil.copy2(path, orig)
        return

    attuale = impronta(path)
    registrato = None
    if os.path.isfile(info):
        try:
            with open(info, encoding="utf-8") as f:
                registrato = json.load(f).get("prodotto")
        except (OSError, ValueError):
            registrato = None

    if registrato is not None:
        valido = (attuale == registrato)
    elif attuale == impronta(orig):
        valido = True                      # il gioco non è patchato: copia fedele
    else:
        log("Controllo se il gioco è già tradotto ...")
        valido = bool(riconosci and riconosci(path))

    if not valido:
        log("%s è cambiato: il vecchio backup non vale più, ne faccio uno nuovo."
            % os.path.basename(path))
        shutil.copy2(path, orig)


def registra_patch(path):
    try:
        with open(path + ".patchinfo", "w", encoding="utf-8") as f:
            json.dump({"prodotto": impronta(path),
                       "nota": "impronta del file scritto dalla patch italiana; "
                               "se non corrisponde, il gioco è stato aggiornato"},
                      f, ensure_ascii=False, indent=1)
    except OSError:
        pass


# ------------------------------------------------------------------ i testi

def patch_testi(data_dir, corsia, log):
    """Scrive i CSV italiani nella corsia scelta. Nessuna guardia può fallire."""
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.61f1"

    asset = os.path.join(data_dir, "sharedassets1.assets")
    if not os.path.isfile(asset):
        raise RuntimeError("Non trovo sharedassets1.assets in:\n%s" % data_dir)
    prepara_backup(asset, log, gia_patchato_assets)
    orig = asset + ".orig"

    dati = carica_italiano()
    testi, per_chiave = dati["testi"], dati.get("per_chiave", {})
    meta = dati.get("_meta", {})
    log("Testi italiani caricati: %s voci." % format(meta.get("voci", 0), ","))

    log("Apro l'archivio del gioco ...")
    with open(orig, "rb") as f:                # in memoria: l'handle non resta aperto
        env = UnityPy.load(f.read())

    corsie, problemi = mappa_corsie(env)
    if len(corsie) != len(CATEGORIE):
        msg = ["Ho riconosciuto %d categorie di testo su %d."
               % (len(corsie), len(CATEGORIE))]
        if problemi:
            # Se la lettura degli oggetti è fallita, il gioco non c'entra: il
            # guasto è qui dentro, e dirlo evita di mandare in caccia al gioco
            # sbagliato chi legge il messaggio.
            conteggio = collections.Counter(problemi)
            msg.append("%d oggetti non si sono lasciati leggere. Il primo motivo:"
                       % len(problemi))
            msg.append("   " + conteggio.most_common(1)[0][0])
            msg.append("Non è la versione del gioco: è il programma che non "
                       "riesce a interpretare l'archivio.")
        else:
            msg.append("Questa versione del gioco non è supportata.")
        raise RuntimeError(chr(10).join(msg))

    guai, scritture, tradotte_tot, righe_tot = [], [], 0, 0
    usate_ecc = set()

    for cat in CATEGORIE:
        v = corsie[cat]
        if "en" not in v:
            guai.append("%s: non trovo la corsia inglese" % cat)
            continue
        if corsia not in v:
            guai.append("%s: non trovo la corsia %s" % (cat, corsia))
            continue

        blob_en = testo_di(oggetto_con(env, v["en"]["path_id"]))[1]
        terne_en = righe(blob_en)
        if serializza(terne_en) != blob_en:
            guai.append("%s: il round-trip del CSV inglese non è identico" % cat)
            continue

        mappa = testi.get(cat, {})
        nuove, tradotte = [], 0
        for k, testo, q in terne_en:
            if testo is None or (testo not in mappa and k not in per_chiave):
                nuove.append((k, testo, q))
                continue
            it = per_chiave.get(k, mappa.get(testo))
            confronto = it
            if k in per_chiave:
                usate_ecc.add(k)
                confronto = it.replace("<nobr>", "").replace("</nobr>", "")
            if sorted(SEGNAPOSTO.findall(testo)) != sorted(SEGNAPOSTO.findall(it)):
                guai.append("%s / %s: segnaposto diversi" % (cat, k))
            if sorted(TAG.findall(testo)) != sorted(TAG.findall(confronto)):
                guai.append("%s / %s: tag diversi" % (cat, k))
            if testo.count("\\n") != it.count("\\n"):
                guai.append("%s / %s: numero di a capo diverso" % (cat, k))
            if not it.strip():
                guai.append("%s / %s: traduzione vuota" % (cat, k))
            nuove.append((k, it, q))
            tradotte += 1

        if len(nuove) != len(terne_en):
            guai.append("%s: %d righe invece di %d" % (cat, len(nuove), len(terne_en)))
        if [k for k, _, _ in nuove] != [k for k, _, _ in terne_en]:
            guai.append("%s: le chiavi non coincidono con l'inglese" % cat)

        scritture.append((cat, v[corsia]["path_id"], serializza(nuove)))
        tradotte_tot += tradotte
        righe_tot += len(terne_en) - 1

    if guai:
        raise RuntimeError("Controlli falliti, non ho scritto niente:\n  "
                           + "\n  ".join(guai[:12])
                           + ("\n  ... e altri %d" % (len(guai) - 12) if len(guai) > 12 else ""))

    log("Righe tradotte: %s su %s (%.1f%%)."
        % (format(tradotte_tot, ","), format(righe_tot, ","),
           100.0 * tradotte_tot / righe_tot if righe_tot else 0))

    log("Scrivo i testi (può richiedere un minuto) ...")
    for cat, pid, blob_it in scritture:
        d = oggetto_con(env, pid).read()
        d.m_Script = blob_it.decode("utf-8")
        d.save()
    with open(asset, "wb") as f:
        f.write(env.file.save())
    registra_patch(asset)

    # Rilettura di controllo: l'unica prova che il file scritto sia buono.
    env2 = UnityPy.load(asset)
    cat0, pid0, blob0 = scritture[0]
    riletto = testo_di(oggetto_con(env2, pid0))[1]
    if riletto != blob0:
        raise RuntimeError("Riletto, il CSV di %s non è quello che ho scritto." % cat0)
    log("Riletto e verificato: %s è a posto." % cat0)
    return tradotte_tot, righe_tot


# ------------------------------------------------------------------ l'etichetta del menu

def _leggi_meta(percorso):
    b = open(percorso, "rb").read()
    firma, versione = struct.unpack_from("<Ii", b, 0)
    if firma != FIRMA_META:
        raise RuntimeError("%s non sembra un global-metadata.dat."
                           % os.path.basename(percorso))
    if versione not in VERSIONI_META:
        raise RuntimeError("Metadati di versione %d, mai vista: non tocco niente."
                           % versione)
    tab_off, tab_dim, dati_off, _ = struct.unpack_from("<4i", b, 8)
    n = tab_dim // 8
    lit = [struct.unpack_from("<II", b, tab_off + 8 * i) for i in range(n)]
    return b, tab_off, dati_off, lit


def _testo_lit(b, dati_off, voce):
    lung, idx = voce
    return b[dati_off + idx: dati_off + idx + lung].decode("utf-8", "replace")


def patch_etichetta(data_dir, da, a, log):
    """Rinomina la voce del menu delle lingue, dentro global-metadata.dat.

    I testi dei letterali stanno attaccati in un unico blocco senza terminatore:
    la lunghezza scritta in tabella è l'unica cosa che dice dove finisce una
    stringa. Quindi **accorciare** un letterale è un cambio locale — si
    riscrivono i byte e si abbassa la lunghezza — mentre allungarlo vorrebbe
    dire spostare il blocco e riscrivere decine di migliaia di indici.
    `Italiano` sono 8 byte e ci sta sotto tutti i nomi che il gioco usa.
    """
    meta = os.path.join(data_dir, "il2cpp_data", "Metadata", "global-metadata.dat")
    if not os.path.isfile(meta):
        raise RuntimeError("Non trovo global-metadata.dat: il menu resterà in %s." % da)
    prepara_backup(meta, log, gia_patchato_meta)
    orig = meta + ".orig"

    b, tab_off, dati_off, lit = _leggi_meta(orig)
    nuovo = a.encode("utf-8")

    quali = [i for i, v in enumerate(lit) if _testo_lit(b, dati_off, v) == da]
    if not quali:
        raise RuntimeError("Nel gioco non c'è nessuna voce di menu che dica %r." % da)
    if len(quali) > 1:
        raise RuntimeError("%r compare in %d punti: non so quale sia quello del menu."
                           % (da, len(quali)))
    i = quali[0]
    lung, idx = lit[i]
    if len(nuovo) > lung:
        raise RuntimeError("%r non ci sta al posto di %r (%d byte contro %d)."
                           % (a, da, len(nuovo), lung))
    vicini = [j for j, (L, d) in enumerate(lit)
              if j != i and d < idx + len(nuovo) and d + L > idx]
    if vicini:
        raise RuntimeError("Quei byte sono letti anche da altre %d stringhe: non li tocco."
                           % len(vicini))

    fuori = bytearray(b)
    fuori[dati_off + idx: dati_off + idx + len(nuovo)] = nuovo
    struct.pack_into("<II", fuori, tab_off + 8 * i, len(nuovo), idx)
    if len(fuori) != len(b):
        raise RuntimeError("La dimensione di global-metadata.dat è cambiata: mi fermo.")

    with open(meta, "wb") as f:
        f.write(bytes(fuori))
    registra_patch(meta)

    b2, _, dati_off2, lit2 = _leggi_meta(meta)
    if _testo_lit(b2, dati_off2, lit2[i]) != a:
        raise RuntimeError("Riletto, la voce di menu non dice %r." % a)
    log("Nel menu delle lingue \"%s\" adesso si chiama \"%s\"." % (da, a))


# ------------------------------------------------------------------ azioni

def do_patch(data_dir, corsia, log):
    nome_menu = dict((c, n) for c, n, _ in LINGUE)[corsia]
    patch_testi(data_dir, corsia, log)
    try:
        patch_etichetta(data_dir, nome_menu, "Italiano", log)
    except Exception as e:
        # I testi ci sono comunque: vale la pena dirlo invece di far sembrare
        # fallito tutto quanto.
        log("")
        log("ATTENZIONE: i testi sono a posto, ma non sono riuscito a rinominare")
        log("la voce del menu. Nel gioco scegli la lingua \"%s\"." % nome_menu)
        log("Motivo: %s" % e)
        return
    log("")
    log("FATTO. Avvia il gioco, vai nelle impostazioni e scegli ITALIANO.")


def do_restore(data_dir, log):
    fatti = 0
    for rel in ("sharedassets1.assets",
                os.path.join("il2cpp_data", "Metadata", "global-metadata.dat")):
        p = os.path.join(data_dir, rel)
        orig = p + ".orig"
        if os.path.isfile(orig):
            shutil.copy2(orig, p)
            info = p + ".patchinfo"
            if os.path.isfile(info):
                try:
                    os.remove(info)
                except OSError:
                    pass
            log("Ripristinato %s" % os.path.basename(p))
            fatti += 1
    if not fatti:
        raise RuntimeError("Backup non trovati: non c'è nulla da ripristinare.")
    log("Il gioco è tornato come prima.")
