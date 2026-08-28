; =============================================================================
;  RenderHive Server — Inno Setup 6 Script
;
;  Bundles the entire server stack into a single self-installing executable.
;  Run build.bat first to populate the staging\ directory, then compile this
;  script with Inno Setup 6 (https://jrsoftware.org/isdl.php).
;
;  Output: Output\RenderHiveServerSetup.exe
; =============================================================================

[Setup]
AppName=RenderHive Server
AppVersion=1.0.0
AppPublisher=RenderHive
DefaultDirName={autopf}\RenderHive\Server
DefaultGroupName=RenderHive
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\manager\RenderHiveServer.exe
Compression=lzma2/max
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=RenderHive Server Setup
; Admin required: we install services and modify the hosts file
PrivilegesRequired=admin
; Minimum OS: Windows 10
MinVersion=10.0.17763
SetupMutex=RenderHiveServerSetup
WizardStyle=modern
WizardSizePercent=120
DisableProgramGroupPage=yes
; Allow a progress page while post_install.ps1 runs
ShowComponentSizes=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "Create a &desktop icon";  GroupDescription: "Additional icons:"
Name: "startmanager"; Description: "Launch Server Manager after installation"; GroupDescription: "After install:"

; =============================================================================
;  Files — copied from the staging\ directory built by build.bat
; =============================================================================

[Files]
; Server Manager GUI
Source: "staging\manager\*"; DestDir: "{app}\manager"; Flags: ignoreversion recursesubdirs createallsubdirs

; Django API bundle
Source: "staging\api\*";     DestDir: "{app}\api";     Flags: ignoreversion recursesubdirs createallsubdirs

; Next.js static frontend
Source: "staging\frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs

; PostgreSQL binaries
Source: "staging\postgres\*"; DestDir: "{app}\postgres"; Flags: ignoreversion recursesubdirs createallsubdirs

; Redis
Source: "staging\redis\*"; DestDir: "{app}\redis"; Flags: ignoreversion recursesubdirs createallsubdirs

; nginx
Source: "staging\nginx\*"; DestDir: "{app}\nginx"; Flags: ignoreversion recursesubdirs createallsubdirs

; AI Service
Source: "staging\ai\*"; DestDir: "{app}\ai"; Flags: ignoreversion recursesubdirs createallsubdirs

; NSSM
Source: "staging\nssm\nssm.exe"; DestDir: "{app}\nssm"; Flags: ignoreversion

; Assets (icons used by the Manager app)
Source: "staging\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion

; Post-install script
Source: "staging\post_install.ps1"; DestDir: "{app}"; Flags: ignoreversion

; =============================================================================
;  Shortcuts
; =============================================================================

[Icons]
Name: "{group}\RenderHive Server Manager"; Filename: "{app}\manager\RenderHiveServer.exe"
Name: "{group}\Uninstall RenderHive Server"; Filename: "{uninstallexe}"
Name: "{autodesktop}\RenderHive Server Manager"; Filename: "{app}\manager\RenderHiveServer.exe"; Tasks: desktopicon

; =============================================================================
;  Run — launch the Server Manager after a successful install (optional task)
; =============================================================================

[Run]
Filename: "{app}\manager\RenderHiveServer.exe"; \
  Description: "Launch RenderHive Server Manager"; \
  Flags: postinstall nowait skipifsilent runascurrentuser; \
  Tasks: startmanager

; =============================================================================
;  Uninstall — gracefully stop and remove all services before removing files
;  NOTE: The PostgreSQL data directory (ProgramData\RenderHive\pgdata) is
;        intentionally NOT deleted so that database contents survive a
;        reinstall.  Users who want a clean slate should delete it manually.
; =============================================================================

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/f /im RenderHiveServer.exe"; Flags: runhidden; RunOnceId: "KillManager"
Filename: "sc.exe"; Parameters: "stop RenderHive-Nginx";    Flags: nowait runhidden; RunOnceId: "StopNginx"
Filename: "sc.exe"; Parameters: "stop RenderHive-API";      Flags: nowait runhidden; RunOnceId: "StopAPI"
Filename: "sc.exe"; Parameters: "stop RenderHive-AI";       Flags: nowait runhidden; RunOnceId: "StopAI"
Filename: "sc.exe"; Parameters: "stop RenderHive-Redis";    Flags: nowait runhidden; RunOnceId: "StopRedis"
Filename: "sc.exe"; Parameters: "stop RenderHive-Postgres"; Flags: nowait runhidden; RunOnceId: "StopPostgres"
Filename: "timeout.exe"; Parameters: "/t 10 /nobreak";      Flags: runhidden; RunOnceId: "TimeoutWait"
Filename: "{app}\nssm\nssm.exe"; Parameters: "remove RenderHive-Nginx    confirm"; Flags: runhidden; RunOnceId: "RemoveNginx"
Filename: "{app}\nssm\nssm.exe"; Parameters: "remove RenderHive-API      confirm"; Flags: runhidden; RunOnceId: "RemoveAPI"
Filename: "{app}\nssm\nssm.exe"; Parameters: "remove RenderHive-AI       confirm"; Flags: runhidden; RunOnceId: "RemoveAI"
Filename: "{app}\nssm\nssm.exe"; Parameters: "remove RenderHive-Redis    confirm"; Flags: runhidden; RunOnceId: "RemoveRedis"
Filename: "{app}\nssm\nssm.exe"; Parameters: "remove RenderHive-Postgres confirm"; Flags: runhidden; RunOnceId: "RemovePostgres"
; Clean up the hosts file entries added during install
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -Command ""$h = '{sys}\drivers\etc\hosts'; if (Test-Path $h) {{ $lines = Get-Content $h; $lines = $lines | Where-Object {{ $_ -notmatch 'renderhive\.local' }}; Set-Content -Path $h -Value $lines -Encoding ASCII }}"""; Flags: runhidden; RunOnceId: "CleanHosts"

; =============================================================================
;  Pascal code — custom wizard pages
; =============================================================================

[Code]

var
  ServerIPPage:       TInputQueryWizardPage;
  AdminPasswordPage:  TInputQueryWizardPage;
  GeneratedSecretKey: String;
  PostInstallLog:     String;

// ---- Utility: generate a random alphanumeric+symbols string ----------------

function RandomChar(Charset: String): Char;
var
  Idx: Integer;
begin
  Idx := Random(Length(Charset)) + 1;
  Result := Charset[Idx];
end;

function GenerateSecretKey(Length: Integer): String;
var
  Charset: String;
  I: Integer;
begin
  Charset := 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#%^&*(-_=+)';
  Result := '';
  for I := 1 to Length do
    Result := Result + RandomChar(Charset);
end;

// ---- IP address validation --------------------------------------------------

function IsValidIP(const S: String): Boolean;
var
  Parts: TStringList;
  I, N: Integer;
begin
  Result := False;
  Parts := TStringList.Create;
  try
    Parts.Delimiter := '.';
    Parts.StrictDelimiter := True;
    Parts.DelimitedText := S;
    if Parts.Count <> 4 then Exit;
    for I := 0 to 3 do
    begin
      if Parts[I] = '' then Exit;
      N := StrToIntDef(Parts[I], -1);
      if (N < 0) or (N > 255) then Exit;
    end;
    Result := True;
  finally
    Parts.Free;
  end;
end;

// ---- Auto-detect IP ---------------------------------------------------------

function GetLocalIP: String;
var
  ResultCode: Integer;
  Lines: TArrayOfString;
  PSCmd, TmpFile: String;
begin
  Result := '';
  TmpFile := ExpandConstant('{tmp}\ip.txt');
  PSCmd := '(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias ''*Wi-Fi*'',''*Ethernet*'' -ErrorAction SilentlyContinue | Where-Object { $_.PrefixOrigin -ne ''WellKnown'' } | Select-Object -First 1).IPAddress | Out-File -FilePath ''' + TmpFile + ''' -Encoding ascii';
  
  Exec('powershell.exe', '-ExecutionPolicy Bypass -WindowStyle Hidden -Command "' + PSCmd + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  if LoadStringsFromFile(TmpFile, Lines) then
  begin
    if GetArrayLength(Lines) > 0 then
      Result := Trim(Lines[0]);
  end;
  
  DeleteFile(TmpFile);
end;

// ---- Wizard initialisation -------------------------------------------------

procedure InitializeWizard;
begin
  GeneratedSecretKey := GenerateSecretKey(50);

  // Page 1 — Server IP
  ServerIPPage := CreateInputQueryPage(wpSelectDir,
    'Network Configuration', 'Server IP Address',
    'Enter the LAN IP address of this server machine.' + #13#10 +
    'This will be added to the hosts file on every client machine.' + #13#10 +
    'Example: 192.168.1.100');
  ServerIPPage.Add('Server IP Address:', False);
  ServerIPPage.Values[0] := GetLocalIP;

  // Page 2 — Admin Account
  AdminPasswordPage := CreateInputQueryPage(ServerIPPage.ID,
    'Administrator Account', 'Dashboard Login Password',
    'Set the password for the RenderHive dashboard administrator account.' + #13#10 +
    'The username will be "admin". You can change this later from the dashboard.');
  AdminPasswordPage.Add('Admin Password:', True);
  AdminPasswordPage.Values[0] := '';
end;

// ---- Validation on Next click ----------------------------------------------

function NextButtonClick(CurPageID: Integer): Boolean;
var
  IP:   String;
  Pass: String;
begin
  Result := True;

  if CurPageID = ServerIPPage.ID then
  begin
    IP := Trim(ServerIPPage.Values[0]);
    if IP = '' then
    begin
      MsgBox('Please enter the Server IP Address.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not IsValidIP(IP) then
    begin
      MsgBox('The IP address "' + IP + '" is not valid.' + #13#10 +
             'Please enter an address in the form 192.168.x.x', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;

  if CurPageID = AdminPasswordPage.ID then
  begin
    Pass := Trim(AdminPasswordPage.Values[0]);
    if Pass = '' then
    begin
      MsgBox('Please enter an Admin Password.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Length(Pass) < 8 then
    begin
      MsgBox('The Admin Password must be at least 8 characters long.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;

// ---- Post-install step — run post_install.ps1 via PowerShell ---------------

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir:        String;
  DataDir:       String;
  ServerIP:      String;
  AdminPassword: String;
  ScriptPath:    String;
  PSArgs:        String;
  ResultCode:    Integer;
begin
  if CurStep = ssPostInstall then
  begin
    AppDir        := ExpandConstant('{app}');
    DataDir       := ExpandConstant('{commonappdata}') + '\RenderHive\pgdata';
    ServerIP      := Trim(ServerIPPage.Values[0]);
    AdminPassword := Trim(AdminPasswordPage.Values[0]);
    ScriptPath    := AppDir + '\post_install.ps1';
    PostInstallLog := AppDir + '\logs\post_install.log';

    PSArgs :=
      '-ExecutionPolicy Bypass' +
      ' -File "' + ScriptPath + '"' +
      ' -InstallDir "' + AppDir + '"' +
      ' -DataDir "' + DataDir + '"' +
      ' -ServerIP "' + ServerIP + '"' +
      ' -AdminPassword "' + AdminPassword + '"' +
      ' -SecretKey "' + GeneratedSecretKey + '"';

    if not Exec(
      'powershell.exe',
      PSArgs,
      AppDir,
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    ) then
    begin
      MsgBox(
        'Failed to launch the post-installation script.' + #13#10 +
        'PowerShell may be blocked by Group Policy.' + #13#10 +
        SysErrorMessage(ResultCode),
        mbError, MB_OK
      );
      Exit;
    end;

    if ResultCode <> 0 then
    begin
      MsgBox(
        'The post-installation script encountered an error (exit code: ' +
        IntToStr(ResultCode) + ').' + #13#10 +
        'Check the log at: ' + PostInstallLog + #13#10 +
        'You may re-run post_install.ps1 manually to retry.',
        mbError, MB_OK
      );
    end;
  end;
end;
