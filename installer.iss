; Script Inno Setup pour créer un installateur Windows
; Nécessite Inno Setup: https://jrsoftware.org/isdl.php

[Setup]
AppName=OpenSuperWhisper
AppVersion=1.0
AppPublisher=OpenSuperWhisper
AppPublisherURL=https://github.com/votre-repo/OpenSuperWhisper
DefaultDirName={pf}\OpenSuperWhisper
DefaultGroupName=OpenSuperWhisper
OutputDir=installer
OutputBaseFilename=OpenSuperWhisper-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
LicenseFile=
InfoBeforeFile=README.md
SetupIconFile=
WizardImageFile=
WizardSmallImageFile=

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
Source: "dist\OpenSuperWhisper.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "check_nvidia_drivers.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_cuda.py"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\OpenSuperWhisper"; Filename: "{app}\OpenSuperWhisper.exe"
Name: "{group}\Vérifier drivers NVIDIA"; Filename: "{app}\check_nvidia_drivers.py"
Name: "{group}\{cm:UninstallProgram,OpenSuperWhisper}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\OpenSuperWhisper"; Filename: "{app}\OpenSuperWhisper.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\OpenSuperWhisper"; Filename: "{app}\OpenSuperWhisper.exe"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\OpenSuperWhisper.exe"; Description: "{cm:LaunchProgram,OpenSuperWhisper}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure InitializeWizard;
begin
  // Afficher un message sur les drivers NVIDIA
  WizardForm.InfoBeforePage.InfoBeforeLabel.Caption := 
    'OpenSuperWhisper - Transcription vocale avec Whisper' + #13#10 + #13#10 +
    'Pour utiliser l''accélération GPU (optionnel):' + #13#10 +
    '1. Installez les drivers NVIDIA depuis https://www.nvidia.com/Download/' + #13#10 +
    '2. Redémarrez votre ordinateur' + #13#10 +
    '3. L''application détectera automatiquement le GPU' + #13#10 + #13#10 +
    'L''application fonctionne aussi en mode CPU sans GPU.';
end;
