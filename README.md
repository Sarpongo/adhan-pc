# Adhan PC

Application de bureau (Windows) qui affiche les horaires de prière de votre
mosquée — récupérés sur **Mawaqit** — et déclenche des rappels puis l'adhan
en son, avec des notifications personnalisables.

## Fonctionnalités

- **Horaires Mawaqit** : recherche par ville/nom ou géolocalisation
  approximative (IP), calendrier annuel mis en cache pour fonctionner hors
  ligne.
- **Rappels configurables** : 30 / 15 / 10 / 5 minutes par défaut, modifiable
  librement (ajout, suppression, réglage propre à chaque prière).
- **Adhan sonore** à l'heure de la prière (fichier par défaut ou par prière,
  volume réglable).
- **Notifications ornementées** (bannière discrète ou voile plein écran),
  qui ne prennent jamais le focus de l'application en cours — jeu, film,
  document — et repassent en bannière si une application plein écran est
  active.
- **Widget permanent** à l'écran (très faible opacité, déplaçable à la
  souris, choix de l'écran sur une configuration multi-moniteurs).
- **Notification Windows native** (centre de notifications).
- **Icône dans la barre des tâches**, démarrage automatique avec Windows.
- Interface adaptée automatiquement à la résolution de l'écran (pas de
  réglage manuel nécessaire, du 1366×768 au 4K).

## Installation (utilisateur final)

Le plus simple : téléchargez `installer_output\AdhanPC-Setup-1.0.0.exe` et
lancez-le. C'est un installateur classique (assistant en français) qui
n'installe rien pour Python — tout est embarqué. Aucun droit administrateur
n'est requis (installation dans le profil utilisateur). Il propose :

- un raccourci menu Démarrer et, en option, un raccourci Bureau ;
- une case *« Lancer Adhan PC au démarrage de Windows »* ;
- un désinstalleur classique (Panneau de configuration / menu Démarrer).

Premier lancement : onglet **Mosquée**, recherchez votre mosquée (ville,
quartier ou nom) ou cliquez sur **Autour de moi**.

## Lancer depuis les sources (développement)

```bash
pip install -r requirements.txt
python adhan_pc.py
```

## Reconstruire l'installateur

Après une modification du code, régénérez l'exécutable puis l'installateur :

```bash
pip install pyinstaller
python -m PyInstaller --name AdhanPC --windowed --icon=assets/icon.ico --noconfirm --clean ^
  --exclude-module numpy --exclude-module pandas --exclude-module scipy ^
  --exclude-module matplotlib --exclude-module IPython --exclude-module jupyter ^
  adhan_pc.py
xcopy /E /I assets dist\AdhanPC\assets
"C:\Users\<vous>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

Le programme d'installation est écrit dans `installer_output\`. Le script
`installer.iss` (Inno Setup) décrit les raccourcis, la clé de démarrage
automatique et le désinstalleur ; `dist\AdhanPC\` (généré par PyInstaller)
en est la source. Ces deux dossiers, ainsi que `build\`, sont des artefacts
reconstructibles — inutile de les partager avec les sources, seul
`AdhanPC-Setup-1.0.0.exe` suffit pour diffuser l'application.

## Démarrage automatique

Dans l'onglet **Général**, cochez *« Lancer Adhan PC au démarrage de
Windows »*. L'application s'ajoute alors à la clé `Run` du registre
(`HKEY_CURRENT_USER`) et démarre silencieusement (`pythonw.exe`, sans
console) à l'ouverture de session.

## Structure du projet

```
adhan_pc.py              point d'entree
adhan/
  config.py              configuration persistante (%APPDATA%/AdhanPC)
  mawaqit.py              client Mawaqit (recherche + horaires + cache)
  times.py                calcul des horaires du jour, date hijri
  scheduler.py            planification des rappels et de l'adhan
  audio.py                lecture MP3/WAV (winmm, sans dependance externe)
  notify.py               notification Windows native
  screens.py              detection multi-ecrans, DPI, anti-vol-de-focus
  startup.py              demarrage automatique (registre)
  singleton.py            verrou mono-instance
  ui/
    app.py                fenetre principale (6 onglets)
    popup.py              banniere / plein ecran ornementes
    overlay.py             widget permanent semi-transparent
    notifier.py            aiguillage evenement -> notifications
    theme.py, widgets.py   palette et composants graphiques
    tray.py                icone dans la barre des taches
assets/
  audio/                  fichiers adhan (mp3)
  icon.png, icon.ico       icone de l'application
```

Les réglages sont enregistrés dans `%APPDATA%\AdhanPC\config.json`, le
calendrier de la mosquée en cache dans `%APPDATA%\AdhanPC\cache\`.

## Notes

- Toutes les fenêtres de notification utilisent `WS_EX_NOACTIVATE` : elles
  s'affichent et restent cliquables sans jamais voler le focus clavier de
  l'application que vous utilisez.
- Une seule instance peut tourner à la fois (verrou système) : relancer
  l'application ramène simplement l'existante au premier plan.
