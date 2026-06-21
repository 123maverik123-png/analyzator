;-- Inno Setup Script for "Анализатор разговоров" --
#define MyAppName "Анализатор разговоров"
#define MyAppVersion "1.0"
#define MyAppPublisher "Ваша Компания"
#define MyAppURL "https://ваш-сайт.ru"
#define MyAppExeName "gui.exe"

[Setup]
AppId={{EEBF66EF-F576-4D42-B843-68B6B945F076}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={pf}\MyCallAnalyzer
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputBaseFilename=MyCallAnalyzerSetup
SetupIconFile=C:\Users\vanis\Downloads\free-icon-ico-15671473.ico
SolidCompression=yes
WizardStyle=modern dark windows11

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Ваше приложение
Source: "C:\Users\vanis\botanalyzer_fixed\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Установщики Python и VLC (кладутся во временную папку {tmp})
Source: "installers\python-3.12.4-amd64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "installers\vlc-3.0.20-win64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Установка Python (только если не установлен)
Filename: "{tmp}\python-3.12.4-amd64.exe"; Parameters: "/quiet InstallAllUsers=1 PrependPath=1"; StatusMsg: "Установка Python 3.12.4..."; Check: NeedInstallPython

; Установка VLC (только если не установлен)
Filename: "{tmp}\vlc-3.0.20-win64.exe"; Parameters: "/S"; StatusMsg: "Установка VLC Media Player..."; Check: NeedInstallVLC

; Запуск вашего приложения
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function NeedInstallPython: Boolean;
begin
  if RegKeyExists(HKLM, 'SOFTWARE\Python\PythonCore\3.12') or
     RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Python\PythonCore\3.12') then
  begin
    Result := False;
    Exit;
  end;
  Result := True;
end;

function NeedInstallVLC: Boolean;
begin
  if RegKeyExists(HKLM, 'SOFTWARE\VideoLAN\VLC') or
     RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\VideoLAN\VLC') then
  begin
    Result := False;
    Exit;
  end;
  Result := True;
end;