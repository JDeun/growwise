# Keep the real updater-feature tests gating; add loader evidence when Windows exits before main.
$ErrorActionPreference = 'Stop'
$directory = 'desktop/artifacts/updater-loader'
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$arguments = @('test', '--locked', '--manifest-path', 'desktop/src-tauri/Cargo.toml', '--features', 'updater', '--lib', 'updater_commands::tests')
$build = & cargo @arguments --no-run --message-format=json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$artifacts = @($build | ForEach-Object {
    try { $_ | ConvertFrom-Json } catch { }
} | Where-Object { $_.reason -eq 'compiler-artifact' -and $_.target.name -eq 'growwise_desktop_lib' -and $_.executable })
if ($artifacts.Count -ne 1) { throw 'Expected one updater-feature Rust test executable.' }
$binary = $artifacts[0].executable
# Tauri embeds its Common Controls v6 manifest in the application, but Cargo's
# separate library-test executable has no .rsrc section. The updater feature
# retains rfd's TaskDialogIndirect import, which does not exist in comctl32 v5.
# Give only this generated test executable the same v6 activation dependency.
# Microsoft SDK post-link embedding: https://learn.microsoft.com/windows/win32/sbscs/mt-exe
$manifestTool = Get-ChildItem "${env:ProgramFiles(x86)}/Windows Kits/10/bin/*/x64/mt.exe" |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $manifestTool) { throw 'Windows SDK manifest tool is unavailable.' }
$testManifest = 'desktop/scripts/windows-rust-test.manifest'
& $manifestTool.FullName -nologo -manifest $testManifest "-outputresource:$binary;#1"
if ($LASTEXITCODE -ne 0) { throw 'Cannot embed the library-test activation manifest.' }
$embeddedManifest = "$directory/test-manifest.xml"
& $manifestTool.FullName -nologo "-inputresource:$binary;#1" "-out:$embeddedManifest"
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify the embedded library-test manifest.' }
[xml]$verifiedManifest = Get-Content -Raw $embeddedManifest
$commonControls = $verifiedManifest.SelectSingleNode("//*[local-name()='assemblyIdentity' and @name='Microsoft.Windows.Common-Controls' and @version='6.0.0.0']")
if (-not $commonControls) { throw 'The library-test executable is missing Common Controls v6.' }
# Cargo reruns Tauri's build script on a second invocation and relinks this test,
# discarding the post-link manifest. Run the exact no-run-produced Rust harness
# with the same module filter Cargo would pass; all test assertions still gate.
& $binary 'updater_commands::tests'
$testResult = $LASTEXITCODE
if ($testResult -eq 0) { exit 0 }
try {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    $installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $installation) { throw 'Cannot locate the compiler tool installation.' }
    $dumpbin = Get-ChildItem "$installation/VC/Tools/MSVC/*/bin/Hostx64/x64/dumpbin.exe" | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $dumpbin) { throw 'Microsoft dumpbin is unavailable.' }
    & $dumpbin.FullName /DEPENDENTS $binary | Set-Content -Encoding utf8 "$directory/dependents.txt"
    if ($LASTEXITCODE -ne 0) { throw 'dumpbin dependency inspection failed.' }
    & $dumpbin.FullName /IMPORTS $binary | Set-Content -Encoding utf8 "$directory/imports.txt"
    if ($LASTEXITCODE -ne 0) { throw 'dumpbin import inspection failed.' }
    $python = Join-Path $env:GITHUB_WORKSPACE '.venv/Scripts/python.exe'
    & $python desktop/scripts/probe_windows_imports.py --imports "$directory/imports.txt" --output "$directory/export-probe.json"
    if ($LASTEXITCODE -ne 0) { throw 'Windows export probe failed; original imports are preserved.' }
    Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-5)} -ErrorAction SilentlyContinue |
        Where-Object { $_.Id -in @(1000,1001,33) } |
        Select-Object TimeCreated,Id,ProviderName,Message |
        ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 "$directory/application-events.json"
} catch {
    $_ | Out-String | Set-Content -Encoding utf8 "$directory/diagnostic-error.txt"
}
# Never turn a failed/aborted security regression suite into a green package build.
exit $testResult
