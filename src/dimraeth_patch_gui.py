# -*- coding: utf-8 -*-
"""Patch Italiana per Dimraeth — la finestra.

Tutto quello che tocca i file del gioco sta in `motore.py`, che si può provare
da solo con `prova_motore.py`. Qui c'è solo l'interfaccia: trovare
l'installazione, chiedere quale lingua sacrificare, e mostrare cosa succede.

Dimraeth va patchato in due file — i testi in `sharedassets1.assets` e il nome
della lingua nel menu dentro `global-metadata.dat` — ma chi installa non deve
saperlo: preme un pulsante e gli succedono tutte e due le cose.
"""
import os, sys, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motore
from motore import LINGUE, res_path

APP = "Patch Italiana — Dimraeth"
AUTORE = "traduzione e patch: MarkMayer, con i TWR"
URL_SEGNALA = "https://github.com/markmayer00/dimraeth-patch-italiana/issues/new/choose"
URL_REPO = "https://github.com/markmayer00/dimraeth-patch-italiana"
URL_DISCORD = "https://discord.gg/85ayAcHRfH"


# ------------------------------------------------------------------ dove sta il gioco

def steam_paths():
    """Tutte le librerie Steam: registro + libraryfolders.vdf, anche su altri dischi."""
    import re as _re
    bases = []
    try:
        import winreg
        for hive, key, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                               (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                               (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    bases.append(winreg.QueryValueEx(k, val)[0].replace("/", "\\"))
            except OSError:
                pass
    except ImportError:
        pass
    bases += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam", r"C:\Steam"]

    libs, seen = [], set()
    for b in bases:
        if not b or not os.path.isdir(b):
            continue
        found = [b]
        vdf = os.path.join(b, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            try:
                txt = open(vdf, encoding="utf-8", errors="ignore").read()
                found += [p.replace("\\\\", "\\") for p in _re.findall(r'"path"\s+"([^"]+)"', txt)]
            except OSError:
                pass
        for p in found:
            common = os.path.join(p, "steamapps", "common")
            if os.path.isdir(common) and common.lower() not in seen:
                seen.add(common.lower())
                libs.append(common)
    return libs


def dischi_fissi():
    """Solo i dischi fissi: niente CD, chiavette o unità di rete, che
    rallenterebbero la ricerca per niente."""
    import string
    out = []
    try:
        import ctypes
        for L in string.ascii_uppercase:
            if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(f"{L}:\\")) == 3:
                out.append(L)
    except Exception:
        out = [L for L in string.ascii_uppercase if os.path.isdir(f"{L}:\\")]
    return out


def candidate_roots():
    roots, seen = [], set()

    def add(p):
        if p and os.path.isdir(p) and p.lower() not in seen:
            seen.add(p.lower())
            roots.append(p)

    for p in steam_paths():
        add(p)
    for p in (r"C:\Program Files\Epic Games", r"C:\Program Files (x86)\Epic Games",
              r"C:\XboxGames", r"C:\GOG Games", r"C:\Program Files (x86)\GOG Galaxy\Games",
              r"C:\Games", r"C:\Giochi"):
        add(p)
    home = os.path.expanduser("~")
    for sub in ("Downloads", "Desktop", "Documents", "Games", "Giochi"):
        add(os.path.join(home, sub))
    dischi = dischi_fissi()
    for drive in dischi:
        for sub in ("SteamLibrary", "Games", "Giochi", "Epic Games", "XboxGames", "GOG Games"):
            add(f"{drive}:\\{sub}")
    for drive in dischi:
        add(f"{drive}:\\")
    return roots


SKIP_DIRS = {"windows", "appdata", "$recycle.bin", "system volume information",
             "programdata", "node_modules", "onedrive"}


def e_dimraeth(dirpath, filenames):
    """Distingue Dimraeth dagli altri giochi Unity.

    Ogni build Unity ha un `app.info` di poche decine di byte con dentro
    l'editore e il nome del prodotto: qui è "Mudtek / Dimraeth". Senza quello
    ci si affida al nome della cartella o dell'eseguibile che sta accanto.
    """
    if "app.info" in filenames:
        try:
            with open(os.path.join(dirpath, "app.info"), encoding="utf-8", errors="ignore") as f:
                return "dimraeth" in f.read(400).lower()
        except OSError:
            pass
    if "dimraeth" in os.path.basename(dirpath).lower():
        return True
    try:
        padre = os.path.dirname(dirpath)
        return any(f.lower().endswith(".exe") and "dimraeth" in f.lower()
                   for f in os.listdir(padre))
    except OSError:
        return False


def looks_like_game(dirpath, filenames, dirnames):
    return (os.path.basename(dirpath).endswith("_Data")
            and "sharedassets1.assets" in filenames
            and "il2cpp_data" in dirnames
            and e_dimraeth(dirpath, filenames))


def scan_game_dirs(progress=lambda s: None, want=8, stop=None):
    """Cerca le installazioni. `stop` è un threading.Event: se scatta, si ferma."""
    def fermare():
        return stop is not None and stop.is_set()

    trovati, seen = [], set()
    for root in candidate_roots():
        if len(trovati) >= want or fermare():
            break
        progress("Cerco in %s ..." % root)
        depth_root = root.rstrip("\\").count(os.sep)
        limit = 6 if len(root) > 3 else 4
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            if fermare():
                dirnames[:] = []
                break
            if dirpath.count(os.sep) - depth_root > limit:
                dirnames[:] = []
                continue
            dirnames[:] = [x for x in dirnames
                           if x.lower() not in SKIP_DIRS and not x.startswith("$")]
            if looks_like_game(dirpath, filenames, dirnames):
                key = os.path.normcase(dirpath)
                if key not in seen:
                    seen.add(key)
                    trovati.append(dirpath)
    return trovati


# ------------------------------------------------------------------ la finestra

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.geometry("860x700")
        self.minsize(760, 620)
        self.busy = False
        self.scanning = False
        self.stop_scan = threading.Event()
        pad = {"padx": 10, "pady": 6}

        self.banner_src = None
        self.banner_img = None
        self._banner_w = 0
        self._banner_job = None
        self.banner_lbl = tk.Label(self, bd=0, highlightthickness=0)
        if self.load_banner():
            self.banner_lbl.pack(fill="x", side="top")
            self.bind("<Configure>", self.fit_banner)
        else:
            ttk.Label(self, text="Patch Italiana per Dimraeth",
                      font=("Segoe UI", 13, "bold")).pack(anchor="w", **pad)

        # Il conteggio delle voci sta già dentro il banner: qui sotto ci va
        # l'unica cosa che chi installa vuole sapere prima di premere, cioè che
        # può tornare indietro.
        ttk.Label(self, text="Traduzione e patch di MarkMayer, con i TWR   ·   "
                             "il backup è automatico: \"Ripristina\" riporta il gioco com'era.",
                  foreground="#666").pack(anchor="w", padx=10, pady=(8, 0))

        f1 = ttk.LabelFrame(self, text="Cartella del gioco")
        f1.pack(fill="x", **pad)
        self.var_game = tk.StringVar()
        ttk.Entry(f1, textvariable=self.var_game).pack(side="left", fill="x",
                                                       expand=True, padx=8, pady=8)
        ttk.Button(f1, text="Sfoglia...", command=self.pick_game).pack(side="left", padx=(0, 8))

        f2 = ttk.LabelFrame(self, text="Quale lingua cedere all'italiano")
        f2.pack(fill="x", **pad)
        self.var_lang = tk.StringVar(value=LINGUE[0][2])
        self.cmb = ttk.Combobox(f2, textvariable=self.var_lang, state="readonly",
                                values=[e for _, _, e in LINGUE])
        self.cmb.pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ttk.Label(f2, text="nel menu si chiamerà \"Italiano\"",
                  foreground="#666").pack(side="left", padx=(0, 8))

        f3 = ttk.Frame(self)
        f3.pack(fill="x", **pad)
        self.btn_auto = ttk.Button(f3, text="Trova il gioco", command=self.on_auto_button)
        self.btn_auto.pack(side="left")
        self.btn_go = ttk.Button(f3, text="APPLICA LA TRADUZIONE", command=self.apply)
        self.btn_go.pack(side="left", padx=8)
        self.btn_undo = ttk.Button(f3, text="Ripristina", command=self.restore)
        self.btn_undo.pack(side="left")
        self.var_music = tk.BooleanVar(value=False)
        ttk.Checkbutton(f3, text="♪ Musica", variable=self.var_music,
                        command=self.toggle_music).pack(side="right")

        self.bar = ttk.Progressbar(self, mode="indeterminate")
        self.bar.pack(fill="x", padx=10)

        self.txt = tk.Text(self, height=11, wrap="word", state="disabled",
                           bg="#12151f", fg="#dcdcdc", insertbackground="#dcdcdc")
        self.txt.pack(fill="both", expand=True, padx=10, pady=(10, 4))

        piede = ttk.Frame(self)
        piede.pack(fill="x", padx=10, pady=(2, 0))
        self.link(piede, "Segnala un problema", URL_SEGNALA).pack(side="left")
        ttk.Label(piede, text="·", foreground="#999").pack(side="left", padx=6)
        self.link(piede, "Pagina della patch", URL_REPO).pack(side="left")
        ttk.Label(piede, text="·", foreground="#999").pack(side="left", padx=6)
        self.link(piede, "Discord dei TWR", URL_DISCORD).pack(side="left")

        self.scroll_lbl = tk.Label(self, anchor="w", font=("Consolas", 10, "bold"),
                                   bg="#000000", fg="#d9a441")
        self.scroll_lbl.pack(fill="x", padx=10, pady=(6, 10))
        self.scroll_text = (
            "*** DIMRAETH - PATCH ITALIANA ***   "
            "tutto il gioco in italiano: interfaccia, missioni, dialoghi, codice, "
            "abilita, incantesimi, oggetti   ***   "
            "14.995 voci - 176.226 parole - nessuna riga lasciata a meta   ***   "
            "traduzione e patch: MARKMAYER, con i TWR   ***   "
            "nel gioco scegli la lingua ITALIANO   ***   "
            "il backup e automatico: puoi sempre tornare indietro   ***   "
            "buon viaggio nelle Montagne di Dimraeth   ***      ")
        self.scroll_i = 0
        self._scroll_job = None
        self.animate_scroll()

        self.log("Benvenuto.")
        self.log("Questa patch traduce Dimraeth in italiano: tutto il testo del gioco,")
        self.log("dai menu all'ultima battuta di ogni personaggio.")
        # Si caricano i testi subito, non al momento di applicare: se il pacchetto
        # non fosse finito dentro l'eseguibile è meglio saperlo adesso, con la
        # finestra ancora vuota, che a metà della patch.
        try:
            m = motore.carica_italiano().get("_meta", {})
            self.log("Testi pronti: %s voci, %s parole."
                     % (format(m.get("voci", 0), ","), format(m.get("parole", 0), ",")))
        except Exception as e:
            self.log("ATTENZIONE: non riesco a leggere i testi italiani (%s)." % e)
        self.log("")
        self.log("L'italiano prende il posto di una delle lingue del gioco, perché il")
        self.log("menu non ne accetta una in più. Scegline una che non useresti.")
        self.log("")
        self.log("Premi \"Trova il gioco\", poi \"APPLICA LA TRADUZIONE\".")

        self.music = None
        self.after(300, self.autodetect)

    # ---------------- collegamenti ----------------
    def link(self, padre, testo, url):
        lbl = tk.Label(padre, text=testo, fg="#0b62c4", cursor="hand2",
                       font=("Segoe UI", 9, "underline"))
        lbl.bind("<Button-1>", lambda e: self.apri(url))
        return lbl

    def apri(self, url):
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as e:
            self.log("(non riesco ad aprire il browser: %s)" % e)
            self.log(url)

    # ---------------- intestazione grafica ----------------
    def load_banner(self):
        p = res_path("banner.png")
        if not os.path.isfile(p):
            return False
        try:
            from PIL import Image
            self.banner_src = Image.open(p).convert("RGB")
            return True
        except Exception as e:
            print("banner non caricato:", e)
            return False

    def fit_banner(self, event=None):
        """Ridisegna al termine del ridimensionamento, non a ogni evento."""
        if self.banner_src is None:
            return
        if self._banner_job:
            self.after_cancel(self._banner_job)
        self._banner_job = self.after(120, self._do_fit_banner)

    def _do_fit_banner(self):
        self._banner_job = None
        w = self.winfo_width()
        if w < 50 or w == self._banner_w:
            return
        self._banner_w = w
        try:
            from PIL import Image, ImageTk
            sw, sh = self.banner_src.size
            h = max(1, round(sh * w / sw))
            self.banner_img = ImageTk.PhotoImage(self.banner_src.resize((w, h), Image.LANCZOS))
            self.banner_lbl.configure(image=self.banner_img)   # va tenuto vivo
        except Exception as e:
            print("banner non ridimensionato:", e)

    # ---------------- musica e scroller ----------------
    def start_music(self):
        try:
            import chiptune
            self.music = chiptune.Player(on_error=self.music_error)
            self.music.start()
        except Exception as e:
            self.music = None
            self.music_error(e)

    def music_error(self, e):
        """Gli errori audio non si nascondono: il programma resta usabile, ma si vedono."""
        self.after(0, lambda: self.log("(musica non disponibile: %s)" % e))

    def toggle_music(self):
        if self.var_music.get():
            self.start_music()
        elif self.music:
            self.music.stop()

    def animate_scroll(self):
        t = self.scroll_text
        self.scroll_i = (self.scroll_i + 1) % len(t)
        self.scroll_lbl.configure(text=(t + t)[self.scroll_i:self.scroll_i + 104])
        self._scroll_job = self.after(70, self.animate_scroll)

    def destroy(self):
        # Le animazioni vanno fermate PRIMA di smontare i widget: un `after`
        # che scatta su un'etichetta gia' distrutta stampa un errore Tcl in
        # faccia a chi chiude la finestra, senza che sia successo niente di male.
        for job in ("_scroll_job", "_banner_job"):
            j = getattr(self, job, None)
            if j:
                try:
                    self.after_cancel(j)
                except Exception:
                    pass
                setattr(self, job, None)
        if self.music:
            self.music.cleanup()
        super().destroy()

    # ---------------- utilità ----------------
    def log(self, s):
        self.txt.configure(state="normal")
        self.txt.insert("end", s + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")
        self.update_idletasks()

    def set_busy(self, on):
        self.busy = on
        for b in (self.btn_go, self.btn_undo):
            b.configure(state="disabled" if on else "normal")
        # durante la ricerca il pulsante resta premibile: serve per interromperla
        self.btn_auto.configure(state="normal" if (not on or self.scanning) else "disabled")
        self.btn_auto.configure(text="Interrompi ricerca" if self.scanning else "Trova il gioco")
        self.bar.start(12) if on else self.bar.stop()

    def run_bg(self, fn):
        if self.busy:
            return
        self.set_busy(True)

        def worker():
            try:
                fn()
            except Exception as e:
                self.log("\nERRORE: " + str(e))
                messagebox.showerror(APP, str(e))
            finally:
                self.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def scelta(self):
        """(corsia, nome nel menu) della lingua scelta nella tendina."""
        e = self.var_lang.get()
        for corsia, nome, etichetta in LINGUE:
            if etichetta == e:
                return corsia, nome
        return LINGUE[0][0], LINGUE[0][1]

    # ---------------- azioni ----------------
    def pick_game(self):
        p = filedialog.askdirectory(title="Scegli la cartella del gioco")
        if not p:
            return
        p = p.replace("/", "\\")
        if not os.path.isfile(os.path.join(p, "sharedassets1.assets")) and os.path.isdir(p):
            for sub in sorted(os.listdir(p)):
                cand = os.path.join(p, sub)
                if sub.endswith("_Data") and os.path.isfile(
                        os.path.join(cand, "sharedassets1.assets")):
                    p = cand
                    break
        self.var_game.set(p)
        if self.scanning:
            self.cancel_scan()
        if not os.path.isfile(os.path.join(p, "sharedassets1.assets")):
            messagebox.showwarning(APP, "In questa cartella non c'è sharedassets1.assets.\n\n"
                                        "Scegli la cartella del gioco (quella con l'eseguibile)\n"
                                        "oppure direttamente quella che finisce con _Data.")

    def choose_install(self, found):
        box = tk.Toplevel(self)
        box.title("Quale installazione?")
        box.transient(self)
        box.grab_set()
        ttk.Label(box, text="Ho trovato più installazioni del gioco.\nScegli quella da tradurre:",
                  justify="left").pack(anchor="w", padx=12, pady=(12, 6))
        var = tk.StringVar(value=found[0])
        for p in found:
            ttk.Radiobutton(box, text=p, value=p, variable=var).pack(anchor="w", padx=16)
        ttk.Button(box, text="Usa questa", command=box.destroy).pack(pady=12)
        self.wait_window(box)
        return var.get()

    def on_auto_button(self):
        """Lo stesso pulsante avvia la ricerca e la interrompe."""
        if self.scanning:
            self.cancel_scan()
        else:
            self.autodetect()

    def cancel_scan(self):
        self.stop_scan.set()
        self.log("Ricerca interrotta.")

    def autodetect(self):
        if self.busy:
            return
        self.stop_scan.clear()
        self.scanning = True

        def job():
            try:
                if self.var_game.get():
                    return
                self.log("")
                self.log("Cerco l'installazione del gioco...")
                self.log('Se sai dove si trova, usa "Sfoglia..." oppure "Interrompi ricerca".')
                found = scan_game_dirs(self.log, stop=self.stop_scan)
                if self.var_game.get():
                    return                       # nel frattempo l'ha scelta l'utente
                if self.stop_scan.is_set() and not found:
                    return
                if len(found) > 1:
                    self.log("Trovate %d installazioni." % len(found))
                    box, done = [found[0]], threading.Event()

                    def ask():
                        try:
                            box[0] = self.choose_install(found)
                        finally:
                            done.set()

                    self.after(0, ask)
                    done.wait(300)
                    self.var_game.set(box[0])
                    self.log("Uso: " + box[0])
                elif found:
                    self.var_game.set(found[0])
                    self.log("Trovato il gioco: " + found[0])
                else:
                    self.log('Gioco non trovato: indicalo a mano con "Sfoglia...".')
            finally:
                self.scanning = False

        self.run_bg(job)

    def apply(self):
        g = self.var_game.get().strip()
        if not g:
            messagebox.showwarning(APP, "Indica prima la cartella del gioco.")
            return
        corsia, nome = self.scelta()
        if not messagebox.askyesno(
                APP,
                "L'italiano prenderà il posto del %s, che nel menu delle lingue\n"
                "si chiamerà \"Italiano\". Le altre lingue restano come sono.\n\n"
                "Viene creato un backup automatico e puoi sempre premere \"Ripristina\".\n\n"
                "Procedo?" % nome.upper()):
            return
        self.log("")
        self.run_bg(lambda: (motore.do_patch(g, corsia, self.log),
                             messagebox.showinfo(APP, "Traduzione applicata.\n\n"
                                                      "Avvia il gioco, vai nelle impostazioni\n"
                                                      "e scegli la lingua ITALIANO.")))

    def restore(self):
        g = self.var_game.get().strip()
        if not g:
            messagebox.showwarning(APP, "Indica prima la cartella del gioco.")
            return
        self.log("")
        self.run_bg(lambda: (motore.do_restore(g, self.log),
                             messagebox.showinfo(APP, "Ripristinato: il gioco è tornato come prima.")))


def riga_di_comando(argv):
    """La patch senza finestra, per provare l'eseguibile vero.

    Serve soprattutto a questo: un programma `--windowed` si può aprire e
    fotografare, ma finché non lo si fa *applicare* non si sa se dentro il
    pacchetto c'è tutto. La prima versione compilata si apriva benissimo e poi
    falliva con «0 categorie», perché a UnityPy mancava un file di dati che
    `--collect-submodules` non raccoglie.

    Senza console attaccata (è il caso dell'eseguibile) `print` non si vede:
    per questo c'è `--log`.
    """
    import argparse
    ap = argparse.ArgumentParser(prog="PatchItaliana_Dimraeth",
                                 description="Patch italiana per Dimraeth, senza finestra.")
    ap.add_argument("cartella", help="la cartella Dimraeth_Data del gioco")
    ap.add_argument("--lingua", default="pt",
                    help="quale corsia cedere: %s" % ", ".join(c for c, _, _ in LINGUE))
    ap.add_argument("--ripristina", action="store_true", help="rimette i file originali")
    ap.add_argument("--log", help="scrive qui quello che succede")
    a = ap.parse_args(argv)

    righe = []

    def dì(s):
        righe.append(s)
        try:
            print(s)
        except Exception:
            pass
        if a.log:
            try:
                with open(a.log, "w", encoding="utf-8") as f:
                    f.write("\n".join(righe) + "\n")
            except OSError:
                pass

    try:
        if a.ripristina:
            motore.do_restore(a.cartella, dì)
        else:
            if a.lingua not in [c for c, _, _ in LINGUE]:
                raise RuntimeError("lingua %r sconosciuta" % a.lingua)
            motore.do_patch(a.cartella, a.lingua, dì)
        dì("ESITO: riuscito")
        return 0
    except Exception as e:
        dì("ERRORE: %s" % e)
        dì("ESITO: fallito")
        return 1


if __name__ == "__main__":
    # Con argomenti fa il lavoro e se ne va; senza, apre la finestra.
    if len(sys.argv) > 1:
        sys.exit(riga_di_comando(sys.argv[1:]))
    App().mainloop()
