# Genera el zip de handoff del módulo Odoo 14 en Temp (fuera del repo, sin binarios en git).
# Uso: powershell -File scripts/package_odoo14_module.ps1
$src = Join-Path $PSScriptRoot "..\odoo14\incoluz_invoice_ai_ocr"
$out = Join-Path $env:TEMP "incoluz_invoice_ai_ocr_14.0.1.0.0.zip"
if (Test-Path $out) { Remove-Item $out }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($src, $out)
Write-Host "ZIP OK -> $out"
