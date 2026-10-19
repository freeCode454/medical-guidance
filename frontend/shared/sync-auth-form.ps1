$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'AuthForm.vue'
$target = Join-Path $PSScriptRoot '..\patient_h5\src\components\AuthForm.vue'
$dir = Split-Path $target
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item $source $target -Force
Write-Host "synced -> $target"
