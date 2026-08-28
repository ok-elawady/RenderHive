; RenderHive Worker Inno Setup Script
; This script packages the PyInstaller output and configures the host file.

[Setup]
AppName=RenderHive Worker
AppVersion=1.4.1
AppPublisher=RenderHive
DefaultDirName={autopf}\RenderHive\Worker
DefaultGroupName=RenderHive
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\RenderHive Worker.exe
Compression=lzma2
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=RenderHive Worker Setup
; Require admin rights to modify the hosts file
PrivilegesRequired=admin

[Files]
; Make sure you run build.bat (PyInstaller) before compiling this setup script
Source: "dist\RenderHive Worker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\RenderHive Worker"; Filename: "{app}\RenderHive Worker.exe"
Name: "{autodesktop}\RenderHive Worker"; Filename: "{app}\RenderHive Worker.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[UninstallRun]
; Clean up the hosts file entries added during install
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -Command ""$h = '{sys}\drivers\etc\hosts'; $lines = [System.IO.File]::ReadAllLines($h); $lines = $lines | Where-Object {{ $_ -notmatch 'renderhive\.local' }; [System.IO.File]::WriteAllLines($h, $lines)"""; Flags: runhidden; RunOnceId: "CleanHosts"

[Code]
var
  ServerIPPage: TInputQueryWizardPage;

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

// ---- Wizard initialisation --------------------------------------------------

procedure InitializeWizard;
begin
  // Create a custom page to ask for the Backend IP Address
  ServerIPPage := CreateInputQueryPage(wpSelectDir,
    'RenderHive Server Configuration', 'Network Settings',
    'Please enter the IP address of the RenderHive backend server. ' +
    'This will allow the worker and web browser to connect using renderhive.local.');
  
  ServerIPPage.Add('Server IP Address (e.g., 192.168.1.100):', False);
  
  // Default to empty
  ServerIPPage.Values[0] := '';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  if CurPageID = ServerIPPage.ID then
  begin
    if Trim(ServerIPPage.Values[0]) = '' then
    begin
      MsgBox('You must enter the Server IP Address to continue.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not IsValidIP(Trim(ServerIPPage.Values[0])) then
    begin
      MsgBox('The IP address "' + Trim(ServerIPPage.Values[0]) + '" is not valid.' + #13#10 +
             'Please enter an address in the form 192.168.x.x', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  HostsPath: string;
  HostsLines: TArrayOfString;
  i: Integer;
  Line: string;
  HasServerLocal, HasRenderLocal: Boolean;
  IpAddress: string;
begin
  if CurStep = ssPostInstall then
  begin
    IpAddress := Trim(ServerIPPage.Values[0]);
    HostsPath := ExpandConstant('{sys}\drivers\etc\hosts');
    
    HasServerLocal := False;
    HasRenderLocal := False;
    
    if LoadStringsFromFile(HostsPath, HostsLines) then
    begin
      // Look for existing renderhive entries and update them, or just flag if they exist
      for i := 0 to GetArrayLength(HostsLines) - 1 do
      begin
        Line := Trim(HostsLines[i]);
        if Pos('server.renderhive.local', Line) > 0 then
        begin
          HostsLines[i] := IpAddress + ' server.renderhive.local';
          HasServerLocal := True;
        end
        else if Pos('renderhive.local', Line) > 0 then
        begin
          // Since we already checked for server.renderhive.local above, this is strictly the root domain
          HostsLines[i] := IpAddress + ' renderhive.local';
          HasRenderLocal := True;
        end;
      end;
      
      // If they weren't found, append them
      if not HasServerLocal then
      begin
        SetArrayLength(HostsLines, GetArrayLength(HostsLines) + 1);
        HostsLines[GetArrayLength(HostsLines) - 1] := IpAddress + ' server.renderhive.local';
      end;
      
      if not HasRenderLocal then
      begin
        SetArrayLength(HostsLines, GetArrayLength(HostsLines) + 1);
        HostsLines[GetArrayLength(HostsLines) - 1] := IpAddress + ' renderhive.local';
      end;
      
      // Save back to the hosts file
      SaveStringsToFile(HostsPath, HostsLines, False);
    end;
  end;
end;
