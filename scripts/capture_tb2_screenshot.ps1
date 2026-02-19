param(
    [string]$OutputDir = "docs/images",
    [string]$Prefix = "tb2-run",
    [int]$DelaySec = 3,
    [int]$Count = 1,
    [int]$IntervalSec = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

if ($DelaySec -gt 0) {
    Start-Sleep -Seconds $DelaySec
}

for ($i = 1; $i -le $Count; $i++) {
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $name = "{0}-{1:D2}-{2}.png" -f $Prefix, $i, $stamp
    $path = Join-Path $OutputDir $name
    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)

    $graphics.Dispose()
    $bitmap.Dispose()

    Write-Output $path

    if ($i -lt $Count -and $IntervalSec -gt 0) {
        Start-Sleep -Seconds $IntervalSec
    }
}
