# Exercise the real process helper without launching a native app or a filtered token.
$ErrorActionPreference = 'Stop'
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $PSScriptRoot 'run_native_e2e.ps1'), [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count -ne 0) { throw ($parseErrors | Out-String) }
$definition = $ast.Find({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Invoke-OwnedPythonProcess'
}, $true)
if ($null -eq $definition) { throw 'Owned native process helper is missing.' }
# Load only the production helper; the enclosing Windows task launcher must not run here.
Set-Item -Path function:Invoke-OwnedPythonProcess -Value $definition.Body.GetScriptBlock()
$directory = Join-Path ([IO.Path]::GetTempPath()) ('growwise-process-io-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $directory | Out-Null
try {
    $child = Join-Path $directory 'actual child.ps1'
    $text = @'
param([string]$Payload, [int]$Result)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::Out.Write("OUT:한글 α $Payload`n" + ('x' * 131072))
[Console]::Error.Write("ERR:한글 β`n" + ('y' * 131072))
exit $Result
'@
    [IO.File]::WriteAllText($child, $text, [Text.UTF8Encoding]::new($false))
    $argument = 'spaces "quotes" and 한글'
    foreach ($expectedExit in @(0, 7)) {
        $log = Join-Path $directory "exit-$expectedExit.log"
        $actualExit = Invoke-OwnedPythonProcess -Executable (Get-Process -Id $PID).Path -CommandArguments @(
            '-NoProfile', '-NonInteractive', '-File', $child, '-Payload', $argument, '-Result', [string]$expectedExit
        ) -LogPath $log
        if ($actualExit -ne $expectedExit) { throw 'The native child exit code was not preserved.' }
        $expected = "OUT:한글 α $argument`n" + ('x' * 131072) + "ERR:한글 β`n" + ('y' * 131072)
        if ([IO.File]::ReadAllText($log, [Text.Encoding]::UTF8) -cne $expected) {
            throw 'Native argument boundaries, UTF-8 output, or output beyond pipe capacity were lost.'
        }
    }
} finally { Remove-Item -LiteralPath $directory -Recurse -Force }
Write-Host 'Real child UTF-8 stdout/stderr, large pipes, quoted arguments and exit codes passed.'
