# WebView2 >=150 ignores debugger environment overrides for elevated hosts.
# Run the actual E2E process tree with the logged-in user's limited token instead.
# https://learn.microsoft.com/microsoft-edge/webview2/concepts/security
param(
    [string]$Python,
    [string]$App,
    [string]$NativeDriver,
    [string]$Artifacts,
    [string]$Parameters,
    [switch]$Worker
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if ($Worker) {
    $payload = Get-Content -Raw -LiteralPath $Parameters | ConvertFrom-Json
    $result = 1
    try {
        Set-Location -LiteralPath $payload.cwd
        foreach ($entry in $payload.environment.psobject.Properties) {
            [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process')
        }
        $arguments = @($payload.arguments)
        & $payload.python @arguments > $payload.log 2>&1
        $result = $LASTEXITCODE
    } catch {
        $_ | Out-String | Set-Content -Encoding utf8 -LiteralPath $payload.log
    } finally {
        $pendingStatus = $payload.status + '.new'
        [string]$result | Set-Content -Encoding ascii -LiteralPath $pendingStatus
        Move-Item -LiteralPath $pendingStatus -Destination $payload.status
    }
    exit $result
}
foreach ($required in @($Python, $App, $NativeDriver, $Artifacts)) {
    if (-not $required) { throw 'Python, App, NativeDriver and Artifacts are required.' }
}
$artifactsPath = [IO.Path]::GetFullPath($Artifacts)
New-Item -ItemType Directory -Force -Path $artifactsPath | Out-Null
$environment = @{
    PATH = $env:PATH
    PYTHONUTF8 = '1'
    PYTHONIOENCODING = 'utf-8'
    MSEDGEDRIVER_TELEMETRY_OPTOUT = '1'
}
foreach ($key in @('WEBVIEW2_BROWSER_EXECUTABLE_FOLDER', 'GITHUB_SHA')) {
    $value = [Environment]::GetEnvironmentVariable($key)
    if ($value) { $environment[$key] = $value }
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('growwise-native-launch-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
$inputFile = Join-Path $temporary 'parameters.json'
$statusFile = Join-Path $temporary 'exit-code.txt'
$logFile = Join-Path $artifactsPath 'launcher.log'
@{
    python = [IO.Path]::GetFullPath($Python)
    cwd = $repoRoot
    arguments = @(
        (Join-Path $PSScriptRoot 'native_e2e.py'), '--app', [IO.Path]::GetFullPath($App),
        '--native-driver', [IO.Path]::GetFullPath($NativeDriver), '--artifacts', $artifactsPath
    )
    environment = $environment
    status = $statusFile
    log = $logFile
} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -LiteralPath $inputFile
$taskName = 'GrowWise-Native-E2E-' + [guid]::NewGuid().ToString('N')
try {
    if ($elevated) {
        # Grant this same account, not Everyone/Users, access under its filtered token.
        foreach ($directory in @($repoRoot, $temporary, (Split-Path $NativeDriver -Parent))) {
            & icacls.exe $directory /grant "*$($identity.User.Value):(OI)(CI)M" /Q
            if ($LASTEXITCODE -ne 0) { throw 'Cannot grant the current limited user E2E access.' }
        }
        $shell = (Get-Process -Id $PID).Path
        $argument = "-NoProfile -NonInteractive -File `"$PSCommandPath`" -Worker -Parameters `"$inputFile`""
        $action = New-ScheduledTaskAction -Execute $shell -Argument $argument -WorkingDirectory $repoRoot
        $taskPrincipal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 4)
        Register-ScheduledTask -TaskName $taskName -Action $action -Principal $taskPrincipal -Settings $settings | Out-Null
        Start-ScheduledTask -TaskName $taskName
        $deadline = [DateTime]::UtcNow.AddSeconds(230)
        while (-not (Test-Path -LiteralPath $statusFile)) {
            if ([DateTime]::UtcNow -ge $deadline) { throw 'Limited-token native E2E task timed out.' }
            $task = Get-ScheduledTask -TaskName $taskName
            $info = Get-ScheduledTaskInfo -TaskName $taskName
            if ($info.LastRunTime.Year -gt 2000 -and $task.State -notin @('Running', 'Queued') -and -not (Test-Path -LiteralPath $statusFile)) {
                throw "Limited-token native E2E task stopped without a result: $($info.LastTaskResult)"
            }
            Start-Sleep -Milliseconds 500
        }
    } else {
        & (Get-Process -Id $PID).Path -NoProfile -NonInteractive -File $PSCommandPath -Worker -Parameters $inputFile
    }
    if (Test-Path -LiteralPath $logFile) { Get-Content -Raw -LiteralPath $logFile | Write-Host }
    $resultText = (Get-Content -Raw -LiteralPath $statusFile).Trim()
    $result = 1
    if (-not [int]::TryParse($resultText, [ref]$result)) { throw 'Invalid native E2E exit status.' }
} finally {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    Remove-Item -LiteralPath $temporary -Recurse -Force
}
exit $result
