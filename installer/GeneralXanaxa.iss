#define MyAppName "Генерал Ксанакса"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Генерал Ксанакса"
#define MyAppExeName "GeneralXanaxa.exe"

[Setup]
AppId={{7D2E6E34-77D1-4D5C-8F7A-3A3E8D3B1B9A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\\Programs\\GeneralXanaxa
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=GeneralXanaxa-Setup
SetupIconFile=..\\assets\\icon.ico
WizardImageFile=..\\assets\\installer_sidebar.bmp
UninstallDisplayIcon={app}\\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
CloseApplications=yes
RestartApplications=no
Uninstallable=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
Source: "..\\dist\\GeneralXanaxa\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Пользовательские голоса, история и аудио в LocalAppData намеренно сохраняются.
