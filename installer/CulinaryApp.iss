#ifndef AppVersion
  #define AppVersion "0.1.4"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\CulinaryApp"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist\installer"
#endif

[Setup]
AppId={{7AB12BBE-8A4F-4F85-9D53-C0A1AABB0001}
AppName=Culinary App
AppVersion={#AppVersion}
AppPublisher=Culinary App
DefaultDirName={localappdata}\Programs\CulinaryApp
DefaultGroupName=Culinary App
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=CulinaryApp-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\CulinaryApp.exe
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Culinary App"; Filename: "{app}\CulinaryApp.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Culinary App"; Filename: "{app}\CulinaryApp.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"

[Run]
Filename: "{app}\CulinaryApp.exe"; Description: "Запустить Culinary App"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\CulinaryApp\cache"
