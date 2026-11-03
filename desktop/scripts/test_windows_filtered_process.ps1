# Pure token-policy regressions, independent of whether the runner is elevated.
$ErrorActionPreference = 'Stop'
Add-Type -Path (Join-Path $PSScriptRoot 'windows_filtered_process.cs')
$guard = [GrowWiseNativeToken.FilteredProcess].GetMethod('Validate', [Reflection.BindingFlags]'NonPublic,Static')
if (-not $guard) { throw 'Filtered-token guard is unavailable.' }
$cases = @(
    @{rid=8192; elevated=$false; admin=$false; same=$true; accept=$true},
    @{rid=8448; elevated=$false; admin=$false; same=$true; accept=$true},
    @{rid=4096; elevated=$false; admin=$false; same=$true; accept=$false},
    @{rid=12288; elevated=$false; admin=$false; same=$true; accept=$false},
    @{rid=16384; elevated=$false; admin=$false; same=$true; accept=$false},
    @{rid=8192; elevated=$true; admin=$false; same=$true; accept=$false},
    @{rid=8192; elevated=$false; admin=$true; same=$true; accept=$false},
    @{rid=8192; elevated=$false; admin=$false; same=$false; accept=$false}
)
foreach ($case in $cases) {
    $info = [GrowWiseNativeToken.TokenInfo]::new()
    $info.UserSid = if ($case.same) { 'test-user' } else { 'other-user' }
    $info.IntegrityRid = [uint32]$case.rid
    $info.IntegritySid = "S-1-16-$($case.rid)"
    $info.IsElevated = $case.elevated
    $info.AdministratorsEnabled = $case.admin
    $accepted = $false
    try { $guard.Invoke($null, @($info, 'test-user')); $accepted = $true }
    catch {
        if ($_.Exception.GetBaseException() -isnot [InvalidOperationException]) { throw }
    }
    if ($accepted -ne $case.accept) { throw "Incorrect filtered-token decision for RID=$($case.rid)." }
}
Write-Host 'Eight filtered-token policy regressions passed.'
