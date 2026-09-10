# Sincroniza el módulo Odoo 14 (fuente de verdad en este repo) con el staging local.
# Uso: powershell -File scripts/sync_odoo14_staging.ps1
$src = Join-Path $PSScriptRoot "..\odoo14\incoluz_invoice_ai_ocr"
$dst = Join-Path $PSScriptRoot "..\odoo14-staging\incoluz_invoice_ai_ocr"
robocopy $src $dst /MIR /XD __pycache__ .git | Out-Null
Write-Host "Sync OK -> $dst"
