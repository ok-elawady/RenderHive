param (
    [Parameter(Mandatory=$false)]
    [string]$ServerIP = ""
)

# Check for Administrator privileges
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $IsAdmin) {
    Write-Warning "Administrator permissions are required to modify the hosts file."
    Write-Host "Restarting script with Administrator privileges..."
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" $ServerIP" -Verb RunAs
    exit
}

if ([string]::IsNullOrWhiteSpace($ServerIP)) {
    $InputIP = Read-Host "Enter the LAN IP address of the RenderHive server [default: 127.0.0.1]"
    if ([string]::IsNullOrWhiteSpace($InputIP)) {
        $ServerIP = "127.0.0.1"
    } else {
        $ServerIP = $InputIP.Trim()
    }
}

$HostsPath = "$env:windir\System32\drivers\etc\hosts"
$Entries = @(
    "$ServerIP`trenderhive.local",
    "$ServerIP`tserver.renderhive.local"
)

Write-Host "Updating hosts file at: $HostsPath"
$HostsContent = Get-Content $HostsPath -Raw

$Added = $false
foreach ($Entry in $Entries) {
    $Domain = $Entry.Split("`t")[1]
    
    # Check if the exact domain is already mapped to the requested IP
    if ($HostsContent -match "(?m)^[ \t]*$([regex]::Escape($ServerIP))[ \t]+$([regex]::Escape($Domain))[ \t]*$") {
        Write-Host " [SKIP] $Domain is already mapped to $ServerIP."
    } else {
        Add-Content -Path $HostsPath -Value $Entry
        Write-Host " [ADDED] $Entry"
        $Added = $true
    }
}

if ($Added) {
    Write-Host "Hosts file updated successfully!" -ForegroundColor Green
} else {
    Write-Host "No changes were needed." -ForegroundColor Yellow
}

Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
