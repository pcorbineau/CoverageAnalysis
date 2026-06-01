param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ArgsList
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location (Split-Path $PSScriptRoot -Parent)
python scripts/run_microsoft_coverage.py @ArgsList
