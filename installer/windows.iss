; Inno Setup script. Build: ISCC /DVersion=1.0.0 installer\windows.iss  (expects dist\craftopia-server-manager.exe and build\ payloads)
#ifndef Version
  #define Version "0.0.0"
#endif
[Setup]
AppName=Craftopia Server Manager
AppVersion={#Version}
DefaultDirName={autopf}\CraftopiaServerManager
DefaultGroupName=Craftopia Server Manager
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=CraftopiaServerManager-Setup
Compression=lzma2
SolidCompression=yes
LicenseFile=..\LICENSE
DisableProgramGroupPage=yes

[Files]
Source: "..\dist\craftopia-server-manager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\bepinex-win_x64\*"; DestDir: "{code:GameDir}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\build\CraftopiaServerChat.dll"; DestDir: "{code:GameDir}\BepInEx\plugins"; Flags: ignoreversion

[Icons]
Name: "{group}\Craftopia Server Manager"; Filename: "{app}\craftopia-server-manager.exe"
Name: "{group}\Config folder"; Filename: "{userappdata}\CraftopiaServerManager"

[Code]
var GamePage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  GamePage := CreateInputDirPage(wpSelectDir, 'Craftopia Dedicated Server', 'Where is the dedicated server installed?',
    'Select the CraftopiaDedicatedServer folder (the one containing Craftopia.exe), usually under Steam\steamapps\common.', False, '');
  GamePage.Add('');
  GamePage.Values[0] := ExpandConstant('{commonpf32}') + '\Steam\steamapps\common\CraftopiaDedicatedServer';
end;

function GameDir(Param: String): String;
begin
  Result := GamePage.Values[0];
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = GamePage.ID then
    if not FileExists(AddBackslash(GamePage.Values[0]) + 'Craftopia.exe') then
    begin
      MsgBox('Craftopia.exe was not found in that folder. Install "Craftopia Dedicated Server" from Steam first.', mbError, MB_OK);
      Result := False;
    end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Dir, Cfg, Game: String;
begin
  if CurStep = ssPostInstall then
  begin
    Dir := ExpandConstant('{userappdata}\CraftopiaServerManager');
    Cfg := Dir + '\config.json';
    ForceDirectories(Dir);
    if not FileExists(Cfg) then
    begin
      Game := GamePage.Values[0];
      StringChangeEx(Game, '\', '\\', True);  { JSON needs escaped backslashes }
      SaveStringToFile(Cfg, '{"install_dir": "' + Game + '"}', False);
    end;
  end;
end;
