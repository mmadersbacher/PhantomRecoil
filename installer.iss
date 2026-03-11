#define AppName "Phantom Recoil"
#ifndef AppVersion
  #define AppVersion "1.0.23"
#endif
#ifndef SignedUninstallerMode
  #define SignedUninstallerMode "no"
#endif
#define AppPublisher "mmadersbacher"
#define AppURL "https://github.com/mmadersbacher/PhantomRecoil"
#define AppExeName "Phantom_Recoil_Standalone.exe"

#ifexist "dist\\Phantom_Recoil_Standalone.exe"
  #define AppExePath "dist\\Phantom_Recoil_Standalone.exe"
#else
  #define AppExePath "Phantom_Recoil_Standalone.exe"
#endif

[Setup]
AppId={{A2B8F018-DBAA-4B35-A8E0-6C6D035B0DEB}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={localappdata}\\Programs\\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=
InfoAfterFile=
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=PhantomRecoilSetup_v{#AppVersion}
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\\{#AppExeName}
DisableProgramGroupPage=yes
DisableReadyMemo=no
SetupLogging=yes
SignedUninstaller={#SignedUninstallerMode}
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=no

; Optional code signing. Configure SignTool in your secure release environment.
; SignTool=signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a $f

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#AppExePath}"; DestDir: "{app}"; Flags: ignoreversion restartreplace
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"
Name: "{autodesktop}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure ForceCloseProcess(const ProcessName: string);
var
  ResultCode: Integer;
begin
  Log(Format('Attempting to close process: %s', [ProcessName]));
  Exec(
    ExpandConstant('{cmd}'),
    '/C taskkill /IM "' + ProcessName + '" /F /T >nul 2>nul',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

function InitializeSetup(): Boolean;
begin
  ForceCloseProcess('Phantom_Recoil_Standalone.exe');
  ForceCloseProcess('Phantom_Recoil.exe');
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  ForceCloseProcess('Phantom_Recoil_Standalone.exe');
  ForceCloseProcess('Phantom_Recoil.exe');
  Result := '';
end;
