#define AppName "VeilClip"
#define AppPublisher "Osenpa"
#define AppPublisherURL "https://osenpa.com"
#define AppSupportURL "https://osenpa.com/veilclip"
#define AppUpdatesURL "https://osenpa.com/veilclip"
#define AppExeName "VeilClip.exe"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8B8A493F-95D3-4E90-A18A-0FFFD44F64D1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppPublisherURL}
AppSupportURL={#AppSupportURL}
AppUpdatesURL={#AppUpdatesURL}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist-installer
OutputBaseFilename=VeilClip-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=no
CloseApplications=yes
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installer
VersionInfoProductName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\VeilClip\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\install_defaults.json"
Type: filesandordirs; Name: "{userappdata}\VeilClip"

[Code]
var
  AppLanguagePage: TWizardPage;
  AppLanguageLabel: TNewStaticText;
  AppLanguageCombo: TNewComboBox;
  ConfiguredDbPath: String;
  ConfiguredBackupDir: String;

function SelectedAppLanguageCode(): String;
begin
  case AppLanguageCombo.ItemIndex of
    0: Result := 'en';
    1: Result := 'de';
    2: Result := 'fr';
    3: Result := 'id';
    4: Result := 'zh_CN';
    5: Result := 'ru';
    6: Result := 'ko';
    7: Result := 'ja';
    8: Result := 'es';
    9: Result := 'ar';
    10: Result := 'it';
    11: Result := 'uk';
    12: Result := 'tr';
    13: Result := 'hi';
    14: Result := 'pt';
    15: Result := 'pl';
  else
    Result := 'en';
  end;
end;

function BuildInstallDefaults(): String;
begin
  Result :=
    '{' + #13#10 +
    '  "first_run": true,' + #13#10 +
    '  "language": "' + SelectedAppLanguageCode() + '"' + #13#10 +
    '}' + #13#10;
end;

function LoadTextFile(const FileName: String): String;
var
  FileContents: AnsiString;
begin
  Result := '';
  if FileExists(FileName) then
  begin
    LoadStringFromFile(FileName, FileContents);
    Result := String(FileContents);
  end;
end;

function DecodeJsonString(const Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '\\', '\', True);
  StringChangeEx(Result, '\/', '/', True);
end;

function PosFrom(const Needle, Haystack: String; const StartIndex: Integer): Integer;
var
  Offset: Integer;
begin
  Result := 0;
  if StartIndex < 1 then
    Exit;

  Offset := Pos(Needle, Copy(Haystack, StartIndex, MaxInt));
  if Offset > 0 then
    Result := StartIndex + Offset - 1;
end;

function LoadJsonStringValue(const FileName, Key: String): String;
var
  JsonText: String;
  KeyPos: Integer;
  ColonPos: Integer;
  StartPos: Integer;
  EndPos: Integer;
begin
  Result := '';
  JsonText := LoadTextFile(FileName);
  if JsonText = '' then
    Exit;

  KeyPos := Pos('"' + Key + '"', JsonText);
  if KeyPos = 0 then
    Exit;

  ColonPos := PosFrom(':', JsonText, KeyPos);
  if ColonPos = 0 then
    Exit;

  StartPos := PosFrom('"', JsonText, ColonPos + 1);
  if StartPos = 0 then
    Exit;

  EndPos := PosFrom('"', JsonText, StartPos + 1);
  if EndPos = 0 then
    Exit;

  Result := DecodeJsonString(Copy(JsonText, StartPos + 1, EndPos - StartPos - 1));
end;

procedure CacheConfiguredDataPaths();
var
  ConfigFile: String;
begin
  ConfigFile := ExpandConstant('{userappdata}\VeilClip\config.json');
  ConfiguredDbPath := LoadJsonStringValue(ConfigFile, 'db_path');
  ConfiguredBackupDir := LoadJsonStringValue(ConfigFile, 'backup_dir');
end;

procedure DeleteFileIfPresent(const FileName: String);
begin
  if (FileName <> '') and FileExists(FileName) then
    DeleteFile(FileName);
end;

procedure DeleteBackupArtifacts(const BackupDir: String);
var
  FindRec: TFindRec;
  SearchPattern: String;
begin
  if (BackupDir = '') or (not DirExists(BackupDir)) then
    Exit;

  SearchPattern := AddBackslash(BackupDir) + 'veilclip_backup_*.db';
  if FindFirst(SearchPattern, FindRec) then
  begin
    try
      repeat
        DeleteFile(AddBackslash(BackupDir) + FindRec.Name);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;

  RemoveDir(BackupDir);
end;

procedure DeleteConfiguredDataArtifacts();
begin
  CacheConfiguredDataPaths();

  DeleteFileIfPresent(ConfiguredDbPath);
  DeleteFileIfPresent(ConfiguredDbPath + '-wal');
  DeleteFileIfPresent(ConfiguredDbPath + '-shm');
  DeleteBackupArtifacts(ConfiguredBackupDir);
end;

procedure KillVeilClipProcesses();
var
  ResultCode: Integer;
begin
  Exec(
    ExpandConstant('{cmd}'),
    '/C taskkill /IM VeilClip.exe /F /T >nul 2>nul',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
  Sleep(1000);
end;

procedure InitializeWizard();
begin
  AppLanguagePage := CreateCustomPage(
    wpSelectDir,
    'VeilClip Language',
    'Choose the default app language for the first launch.'
  );

  AppLanguageLabel := TNewStaticText.Create(AppLanguagePage);
  AppLanguageLabel.Parent := AppLanguagePage.Surface;
  AppLanguageLabel.Caption :=
    'This is only used when VeilClip does not already have a saved language setting.';
  AppLanguageLabel.WordWrap := True;
  AppLanguageLabel.SetBounds(0, 0, AppLanguagePage.SurfaceWidth, ScaleY(32));

  AppLanguageCombo := TNewComboBox.Create(AppLanguagePage);
  AppLanguageCombo.Parent := AppLanguagePage.Surface;
  AppLanguageCombo.Style := csDropDownList;
  AppLanguageCombo.SetBounds(0, ScaleY(44), ScaleX(280), ScaleY(24));
  AppLanguageCombo.Items.Add('English');
  AppLanguageCombo.Items.Add('Deutsch');
  AppLanguageCombo.Items.Add('Francais');
  AppLanguageCombo.Items.Add('Bahasa Indonesia');
  AppLanguageCombo.Items.Add('Chinese (Simplified)');
  AppLanguageCombo.Items.Add('Russian');
  AppLanguageCombo.Items.Add('Korean');
  AppLanguageCombo.Items.Add('Japanese');
  AppLanguageCombo.Items.Add('Spanish');
  AppLanguageCombo.Items.Add('Arabic');
  AppLanguageCombo.Items.Add('Italian');
  AppLanguageCombo.Items.Add('Ukrainian');
  AppLanguageCombo.Items.Add('Turkish');
  AppLanguageCombo.Items.Add('Hindi');
  AppLanguageCombo.Items.Add('Portuguese');
  AppLanguageCombo.Items.Add('Polish');
  AppLanguageCombo.ItemIndex := 0;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    KillVeilClipProcesses();
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'VeilClip');
  end;

  if CurStep = ssPostInstall then
  begin
    SaveStringToFile(
      ExpandConstant('{app}\install_defaults.json'),
      BuildInstallDefaults(),
      False
    );
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    KillVeilClipProcesses();
    DeleteConfiguredDataArtifacts();
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'VeilClip');
  end;

  if CurUninstallStep = usPostUninstall then
  begin
    DelTree(ExpandConstant('{userappdata}\VeilClip'), True, True, True);
    DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;
