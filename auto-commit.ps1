# auto-commit.ps1 - watches the project folder and auto-commits + pushes on any change
$path = $PSScriptRoot
$branch = "main"   # change if your branch differs

$fsw = New-Object System.IO.FileSystemWatcher
$fsw.Path = $path
$fsw.IncludeSubdirectories = $true
$fsw.EnableRaisingEvents = $true

Write-Host "Watching $path for changes... (Ctrl+C to stop)"

# Debounce so a burst of saves = one commit
$lastRun = Get-Date

$action = {
    $now = Get-Date
    if (($now - $script:lastRun).TotalSeconds -lt 3) { return }
    $script:lastRun = $now

    Start-Sleep -Seconds 2   # let editors finish writing
    Set-Location $using:path
    $status = git status --porcelain
    if ($status) {
        git add -A
        git commit -m "auto: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-Null
        git push origin $using:branch
        Write-Host "Committed & pushed at $now"
    }
}

Register-ObjectEvent $fsw Changed -Action $action | Out-Null
Register-ObjectEvent $fsw Created -Action $action | Out-Null
Register-ObjectEvent $fsw Deleted -Action $action | Out-Null
Register-ObjectEvent $fsw Renamed -Action $action | Out-Null

while ($true) { Start-Sleep -Seconds 1 }
