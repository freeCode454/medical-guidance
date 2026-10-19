$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'AuthForm.vue'
$targets = @(
    (Join-Path $PSScriptRoot '..\patient_h5\src\components\AuthForm.vue'),
    (Join-Path $PSScriptRoot '..\doctor_web\src\components\AuthForm.vue'),
    (Join-Path $PSScriptRoot '..\admin_web\src\components\AuthForm.vue')
)
foreach ($target in $targets) {
    $dir = Split-Path $target
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Copy-Item $source $target -Force
    Write-Host "synced -> $target"
}
