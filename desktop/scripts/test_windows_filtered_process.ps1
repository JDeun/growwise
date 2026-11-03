# Pure token-policy regressions, independent of whether the runner is elevated.
$ErrorActionPreference = 'Stop'
foreach ($script in @('run_native_e2e.ps1', 'test_windows_updater.ps1')) {
    $tokens = $null
    $parseErrors = $null
    [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $script), [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count -ne 0) { throw ($parseErrors | Out-String) }
}
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
$defaultAcl = [GrowWiseNativeToken.FilteredProcess].GetMethod('AddSameUserDefaultDacl', [Reflection.BindingFlags]'NonPublic,Static')
if (-not $defaultAcl) { throw 'Owned-object ACL builder is unavailable.' }
# S-1-5-1000 is a synthetic user; the existing deny ACE for S-1-5-18 must survive.
[byte[]]$sameUserSid = @(1, 1, 0, 0, 0, 0, 0, 5, 232, 3, 0, 0)
[byte[]]$existingAcl = @(
    2, 0, 28, 0, 1, 0, 0, 0,
    1, 0, 20, 0, 0, 0, 0, 16,
    1, 1, 0, 0, 0, 0, 0, 5, 18, 0, 0, 0
)
[byte[]]$before = $existingAcl.Clone()
[byte[]]$updated = $defaultAcl.Invoke($null, @($existingAcl, $sameUserSid))
if ([Convert]::ToHexString($existingAcl) -cne [Convert]::ToHexString($before)) {
    throw 'The existing default ACL was mutated.'
}
if ($updated.Length -ne 48 -or [BitConverter]::ToUInt16($updated, 2) -ne 48 -or
    [BitConverter]::ToUInt16($updated, 4) -ne 2 -or
    [Convert]::ToHexString($updated[8..27]) -cne [Convert]::ToHexString($before[8..27])) {
    throw 'An existing ACE was removed or changed.'
}
if ($updated[28] -ne 0 -or $updated[29] -ne 0 -or
    [BitConverter]::ToUInt16($updated, 30) -ne 20 -or
    [BitConverter]::ToUInt32($updated, 32) -ne 0x10000000 -or
    [Convert]::ToHexString($updated[36..47]) -cne [Convert]::ToHexString($sameUserSid)) {
    throw 'The added ACE must grant only the same user access to future owned objects.'
}
foreach ($invalid in @(
    [byte[]]@(2, 0, 8, 0, 1, 0, 0, 0), # count overflows actual ACL
    [byte[]]@(2, 0, 7, 0, 0, 0, 0, 0), # incorrect ACL size
    [byte[]]@(2, 0, 12, 0, 1, 0, 0, 0, 0, 0, 40, 0) # truncated ACE
)) {
    $rejected = $false
    try { $null = $defaultAcl.Invoke($null, @($invalid, $sameUserSid)) }
    catch {
        if ($_.Exception.GetBaseException() -isnot [ArgumentException]) { throw }
        $rejected = $true
    }
    if (-not $rejected) { throw 'Malformed ACL was accepted.' }
}
Write-Host 'Same-user default ACL grant preserves existing denies and rejects malformed ACLs.'
