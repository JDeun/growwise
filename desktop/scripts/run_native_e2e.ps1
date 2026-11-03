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
        # Some hosted runner accounts keep a High label even with RunLevel Limited.
        # Lower only this owned worker's token; do not change machine/WebView policies.
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class GrowWiseWorkerIntegrity {
    [StructLayout(LayoutKind.Sequential)] struct Label { public IntPtr Sid; public uint Attributes; }
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr value);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr value);
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool GetTokenInformation(IntPtr token, int kind, IntPtr data, uint size, out uint needed);
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool SetTokenInformation(IntPtr token, int kind, ref Label data, uint size);
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern bool ConvertStringSidToSid(string text, out IntPtr sid);
    [DllImport("advapi32.dll")] static extern uint GetLengthSid(IntPtr sid);
    [DllImport("advapi32.dll")] static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);
    [DllImport("advapi32.dll")] static extern IntPtr GetSidSubAuthority(IntPtr sid, uint index);
    static IntPtr Open(uint access) {
        IntPtr token;
        if(!OpenProcessToken(GetCurrentProcess(), access, out token)) throw new Win32Exception();
        return token;
    }
    public static uint Current() {
        IntPtr token=Open(8), data=IntPtr.Zero;
        try {
            uint size;
            GetTokenInformation(token,25,IntPtr.Zero,0,out size);
            if(size==0) throw new Win32Exception();
            data=Marshal.AllocHGlobal((int)size);
            if(!GetTokenInformation(token,25,data,size,out size)) throw new Win32Exception();
            Label label=Marshal.PtrToStructure<Label>(data);
            byte count=Marshal.ReadByte(GetSidSubAuthorityCount(label.Sid));
            if(count==0) throw new InvalidOperationException("Integrity SID has no RID");
            return (uint)Marshal.ReadInt32(GetSidSubAuthority(label.Sid,(uint)(count-1)));
        } finally { if(data!=IntPtr.Zero) Marshal.FreeHGlobal(data); CloseHandle(token); }
    }
    public static void LowerToMedium() {
        IntPtr token=Open(0x88), sid=IntPtr.Zero;
        try {
            if(!ConvertStringSidToSid("S-1-16-8192",out sid)) throw new Win32Exception();
            Label label=new Label { Sid=sid, Attributes=0x20 };
            if(!SetTokenInformation(token,25,ref label,(uint)Marshal.SizeOf<Label>()+GetLengthSid(sid))) throw new Win32Exception();
        } finally { if(sid!=IntPtr.Zero) LocalFree(sid); CloseHandle(token); }
    }
}
'@
        $initialIntegrity = [GrowWiseWorkerIntegrity]::Current()
        if ($initialIntegrity -ge 12288) { [GrowWiseWorkerIntegrity]::LowerToMedium() }
        $finalIntegrity = [GrowWiseWorkerIntegrity]::Current()
        @{
            initial_integrity_sid = "S-1-16-$initialIntegrity"
            final_integrity_sid = "S-1-16-$finalIntegrity"
            requested_task_runlevel = 'Limited'
        } | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath ($payload.log + '.integrity.json')
        if ($finalIntegrity -lt 8192 -or $finalIntegrity -ge 12288) { throw "Worker must use Medium integrity; actual RID=$finalIntegrity" }
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
