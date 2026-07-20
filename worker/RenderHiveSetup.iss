; RenderHive Worker Inno Setup Script
; This script packages the PyInstaller output and configures the host file.

[Setup]
AppName=RenderHive Worker
AppVersion=0.0.1
AppPublisher=RenderHive
DefaultDirName={autopf}\RenderHive\Worker
DefaultGroupName=RenderHive
UninstallDisplayIcon={app}\RenderHiveWorker.exe
Compression=lzma2
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=RenderHiveWorkerSetup
; Require admin rights to modify the hosts file
PrivilegesRequired=admin

[Files]
; Make sure you run build.bat (PyInstaller) before compiling this setup script
Source: "dist\RenderHiveWorker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\RenderHive Worker"; Filename: "{app}\RenderHiveWorker.exe"
Name: "{autodesktop}\RenderHive Worker"; Filename: "{app}\RenderHiveWorker.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Code]
var
  ServerIPPage: TInputQueryWizardPage;

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
        if Pos('api.renderhive.local', Line) > 0 then
        begin
          HostsLines[i] := IpAddress + ' api.renderhive.local';
          HasServerLocal := True;
        end;
        if Pos('renderhive.local', Line) > 0 then
        begin
          if Pos('api.renderhive.local', Line) = 0 then
          begin
            HostsLines[i] := IpAddress + ' renderhive.local';
            HasRenderLocal := True;
          end;
        end;
      end;
      
      // If they weren't found, append them
      if not HasServerLocal then
      begin
        SetArrayLength(HostsLines, GetArrayLength(HostsLines) + 1);
        HostsLines[GetArrayLength(HostsLines) - 1] := IpAddress + ' api.renderhive.local';
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
