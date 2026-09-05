; Assistant d'installation Adhan PC (Inno Setup).
; Compilation : "C:\Users\sarpo\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
;
; Installation par utilisateur (aucun droit administrateur requis), avec
; raccourcis menu Demarrer / bureau et lancement optionnel a la fin.
; Necessite que dist\AdhanPC\ existe deja (build PyInstaller prealable).

#define MyAppName "Adhan PC"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Adhan PC"
#define MyAppExeName "AdhanPC.exe"
#define MyAppSourceDir "dist\AdhanPC"

[Setup]
AppId={{8F2C9E1A-4B7D-4E6A-9B3F-2D5A7C61E9F4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=AdhanPC-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Icônes supplémentaires :"
Name: "startupicon"; Description: "Lancer {#MyAppName} au démarrage de Windows"; GroupDescription: "Options de démarrage :"

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Désinstaller {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "AdhanPC"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; \
    Tasks: startupicon; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName} maintenant"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
