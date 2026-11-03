# Download only Microsoft's driver matching the WebView2 runtime used by the test app.
# https://learn.microsoft.com/microsoft-edge/webview2/how-to/webdriver
param([Parameter(Mandatory = $true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$roots = @(
    "${env:ProgramFiles(x86)}\Microsoft\EdgeWebView\Application",
    "$env:ProgramFiles\Microsoft\EdgeWebView\Application",
    "$env:LOCALAPPDATA\Microsoft\EdgeWebView\Application"
)
$runtimes = @($roots | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Get-ChildItem -LiteralPath $_ -Directory | Where-Object {
        $_.Name -match '^\d+\.\d+\.\d+\.\d+$' -and (Test-Path -LiteralPath (Join-Path $_.FullName 'msedgewebview2.exe'))
    }
} | Sort-Object { [version]$_.Name } -Descending)
if ($runtimes.Count -eq 0) { throw 'The Windows runner has no installed WebView2 runtime.' }
$runtime = $runtimes[0]
$version = $runtime.Name
$destinationPath = New-Item -ItemType Directory -Force -Path $Destination
$archive = Join-Path $destinationPath.FullName 'edgedriver.zip'
$downloadUrl = "https://msedgedriver.microsoft.com/$version/edgedriver_win64.zip"
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archive -TimeoutSec 90
} catch {
    # A runtime patch can share the same driver build. Microsoft requires the first three parts.
    if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
    $major = $version.Split('.')[0]
    $latestFile = Join-Path $destinationPath.FullName 'latest-driver-version.txt'
    Invoke-WebRequest -Uri "https://msedgedriver.microsoft.com/LATEST_RELEASE_$major" -OutFile $latestFile -TimeoutSec 30
    $driverVersion = (Get-Content -Raw -LiteralPath $latestFile).Trim([char]0xFEFF).Trim()
    if ($driverVersion -notmatch '^\d+\.\d+\.\d+\.\d+$' -or ($driverVersion.Split('.')[0..2] -join '.') -ne ($version.Split('.')[0..2] -join '.')) {
        throw "No matching WebView2 driver build: runtime=$version, driver=$driverVersion"
    }
    $downloadUrl = "https://msedgedriver.microsoft.com/$driverVersion/edgedriver_win64.zip"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archive -TimeoutSec 90
}
if ((Get-Item -LiteralPath $archive).Length -gt 100MB) { throw 'Driver archive exceeds 100 MiB.' }
Expand-Archive -LiteralPath $archive -DestinationPath $destinationPath.FullName -Force
$driver = Join-Path $destinationPath.FullName 'msedgedriver.exe'
$signature = Get-AuthenticodeSignature -FilePath $driver
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'Microsoft Edge WebDriver Authenticode verification failed.'
}
$driverVersionOutput = (& $driver --version)
if ($LASTEXITCODE -ne 0 -or $driverVersionOutput -notmatch '(\d+\.\d+\.\d+\.\d+)') { throw 'Cannot read Edge WebDriver version.' }
$installedVersion = $Matches[1]
if (($installedVersion.Split('.')[0..2] -join '.') -ne ($version.Split('.')[0..2] -join '.')) { throw 'Driver/runtime build mismatch.' }
@{
    runtime_version = $version
    driver_version = $installedVersion
    download_url = $downloadUrl
    archive_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash
    driver_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $driver).Hash
    authenticode = $signature.Status.ToString()
} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $destinationPath.FullName 'driver-provenance.json')
# Pin this run to the runtime we just matched, including if Evergreen updates during the job.
$env:WEBVIEW2_BROWSER_EXECUTABLE_FOLDER = $runtime.FullName
$env:GROWWISE_EDGE_WEBDRIVER = $driver
if ($env:GITHUB_ENV) {
    "WEBVIEW2_BROWSER_EXECUTABLE_FOLDER=$($runtime.FullName)" | Out-File -Append -Encoding utf8 $env:GITHUB_ENV
    "GROWWISE_EDGE_WEBDRIVER=$driver" | Out-File -Append -Encoding utf8 $env:GITHUB_ENV
}
