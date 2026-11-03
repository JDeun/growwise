# WebView2 >=150 ignores debugger environment overrides for elevated hosts.
# Run the actual E2E process tree with the logged-in user's limited token instead.
# https://learn.microsoft.com/microsoft-edge/webview2/concepts/security
param(
    [string]$Python,
    [string]$App,
    [string]$NativeDriver,
    [string]$Artifacts,
    [string]$Parameters,
    [switch]$Worker,
    [switch]$FilteredWorker,
    [switch]$ProbeOnly
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
function Invoke-OwnedPythonProcess {
    param([string]$Executable, [string[]]$CommandArguments, [string]$LogPath)
    # PowerShell's optimized native file redirection fails in a console-less filtered worker.
    # Explicitly redirect both pipes before assigning their UTF-8 encodings.
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    $start.WorkingDirectory = (Get-Location).Path
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = [Text.Encoding]::UTF8
    $start.StandardErrorEncoding = [Text.Encoding]::UTF8
    foreach ($argument in $CommandArguments) { $start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    try {
        $process.StartInfo = $start
        if (-not $process.Start()) { throw 'Cannot start the owned native test process.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $text = $stdout.GetAwaiter().GetResult() + $stderr.GetAwaiter().GetResult()
        [IO.File]::WriteAllText($LogPath, $text, [Text.UTF8Encoding]::new($false))
        return $process.ExitCode
    } finally { $process.Dispose() }
}
if ($Worker) {
    $payload = Get-Content -Raw -LiteralPath $Parameters | ConvertFrom-Json
    $result = 1
    $ownsResult = $true
    $launched = $null
    try {
        Add-Type -Path (Join-Path $PSScriptRoot 'windows_filtered_process.cs')
        $token = [GrowWiseNativeToken.FilteredProcess]::InspectCurrent()
        $standard = -not $token.IsElevated -and -not $token.AdministratorsEnabled -and $token.IntegrityRid -ge 8192 -and $token.IntegrityRid -lt 12288
        if (-not $standard) {
            if ($FilteredWorker) { throw 'Filtered worker did not receive a standard Medium token.' }
            # Task Scheduler supplies the interactive desktop; this bootstrap obtains a genuinely
            # filtered token. Changing its integrity label alone leaves Administrators enabled.
            $shell = (Get-Process -Id $PID).Path
            $command = '"{0}" -NoProfile -NonInteractive -File "{1}" -Worker -FilteredWorker -Parameters "{2}"' -f $shell, $PSCommandPath, $Parameters
            $launched = [GrowWiseNativeToken.FilteredProcess]::LaunchFiltered($shell, $command, $payload.cwd)
            @{
                initial_integrity_sid = $token.IntegritySid
                initial_token_is_elevated = $token.IsElevated
                initial_administrators_enabled = $token.AdministratorsEnabled
                source = $launched.Source
                filtered_integrity_sid = $launched.Token.IntegritySid
                filtered_token_is_elevated = $launched.Token.IsElevated
                filtered_administrators_enabled = $launched.Token.AdministratorsEnabled
            } | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath ($payload.log + '.token-launch.json')
            $ownsResult = $false
            $result = $launched.WaitForExit()
        } else {
            # Diagnostics must not replace the original process-start failure.
            try { $nativeExecutionFacts = [GrowWiseNativeToken.FilteredProcess]::InspectExecutionContext() }
            catch { $nativeExecutionFacts = @{ inspection_error = $_.Exception.Message } }
            @{
                final_integrity_sid = $token.IntegritySid
                token_is_elevated = $token.IsElevated
                administrators_enabled = $token.AdministratorsEnabled
                elevation_type = $token.ElevationType
                filtered_worker = [bool]$FilteredWorker
                requested_task_runlevel = 'Limited'
                execution_context = $nativeExecutionFacts
            } | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath ($payload.log + '.integrity.json')
            Set-Location -LiteralPath $payload.cwd
            foreach ($entry in $payload.environment.psobject.Properties) {
                [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process')
            }
            if ($payload.probe_only) {
                $result = Invoke-OwnedPythonProcess -Executable (Get-Process -Id $PID).Path -CommandArguments @(
                    '-NoProfile', '-NonInteractive', '-Command',
                    "[Console]::Out.WriteLine('Verified filtered worker native UTF-8 stdout.'); [Console]::Error.WriteLine('Native stderr 확인.'); exit 0"
                ) -LogPath $payload.log
                $captured = Get-Content -Raw -Encoding utf8 -LiteralPath $payload.log
                if ($result -ne 0 -or -not $captured.Contains('Verified filtered worker native UTF-8 stdout.') -or -not $captured.Contains('Native stderr 확인.')) {
                    throw 'Filtered worker native UTF-8 stdout/stderr capture failed.'
                }
            } else {
                $result = Invoke-OwnedPythonProcess -Executable $payload.python -CommandArguments @($payload.arguments) -LogPath $payload.log
            }
        }
    } catch {
        $ownsResult = $true
        if (('GrowWiseNativeToken.FilteredProcess' -as [type]) -and $null -ne [GrowWiseNativeToken.FilteredProcess]::LastLaunchDiagnostics) {
            [GrowWiseNativeToken.FilteredProcess]::LastLaunchDiagnostics | ConvertTo-Json -Depth 4 |
                Set-Content -Encoding utf8 -LiteralPath ($payload.log + '.launch-failure.json')
        }
        # Preserve the inner Win32 stack: formatted PowerShell records hide whether
        # access was denied creating a pipe, inheriting handles, or starting the image.
        $_.Exception.ToString() | Set-Content -Encoding utf8 -LiteralPath $payload.log
    } finally {
        if ($null -ne $launched) { $launched.Dispose() }
        if ($ownsResult) {
            $pendingStatus = $payload.status + '.new'
            [string]$result | Set-Content -Encoding ascii -LiteralPath $pendingStatus
            Move-Item -Force -LiteralPath $pendingStatus -Destination $payload.status
        }
    }
    exit $result
}
foreach ($required in $(if ($ProbeOnly) { @($Artifacts) } else { @($Python, $App, $NativeDriver, $Artifacts) })) {
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
    python = $(if ($ProbeOnly) { '' } else { [IO.Path]::GetFullPath($Python) })
    cwd = $repoRoot
    arguments = $(if ($ProbeOnly) { @() } else { @(
        (Join-Path $PSScriptRoot 'native_e2e.py'), '--app', [IO.Path]::GetFullPath($App),
        '--native-driver', [IO.Path]::GetFullPath($NativeDriver), '--artifacts', $artifactsPath
    ) })
    probe_only = [bool]$ProbeOnly
    environment = $environment
    status = $statusFile
    log = $logFile
} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -LiteralPath $inputFile
$taskName = 'GrowWise-Native-E2E-' + [guid]::NewGuid().ToString('N')
try {
    if ($elevated) {
        # Grant this same account, not Everyone/Users, access under its filtered token.
        $accessDirectories = @($repoRoot, $temporary)
        if ($NativeDriver) { $accessDirectories += Split-Path $NativeDriver -Parent }
        foreach ($directory in $accessDirectories) {
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
