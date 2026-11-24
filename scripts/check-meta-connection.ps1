[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('instagram', 'facebook')]
    [string]$Channel,
    [switch]$Save,
    [guid]$PublicationId,
    [int]$ConfirmDraft
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
$manage = Join-Path $repo 'bara_home\manage.py'
$folder = Join-Path $env:LOCALAPPDATA 'Bara\Credentials'
$credentialPath = Join-Path $folder "$Channel.dpapi"
$variable = if ($Channel -eq 'instagram') {
    'BARA_INSTAGRAM_ACCESS_TOKEN'
} else {
    'BARA_FACEBOOK_PAGE_ACCESS_TOKEN'
}

$publish = $PSBoundParameters.ContainsKey('PublicationId')
if ($publish -and ($PublicationId -eq [guid]::Empty -or $Save -or $ConfirmDraft -lt 1)) {
    throw 'Verify and save credentials first. Publishing requires the selected publication ID and confirmed draft ID.'
}

$credential = if ($Save) {
    Read-Host "Paste the $Channel access token (hidden)" -AsSecureString
} else {
    if (!(Test-Path -LiteralPath $credentialPath -PathType Leaf)) {
        throw 'No stored credential. Run again with -Save to add it.'
    }
    Get-Content -LiteralPath $credentialPath -Raw | ConvertTo-SecureString
}

if ($credential.Length -eq 0) {
    throw 'The access token is empty.'
}

$previousToken = [Environment]::GetEnvironmentVariable($variable, 'Process')
try {
    $token = [System.Net.NetworkCredential]::new('', $credential).Password.Trim()
    [Environment]::SetEnvironmentVariable($variable, $token, 'Process')
    if ($publish) {
        & $python $manage publish_meta_post $Channel $PublicationId --confirm-draft $ConfirmDraft
    } else {
        & $python $manage check_social_connection $Channel
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'The Meta command failed. The saved credential was not changed.'
    }
    if ($Save) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        ConvertFrom-SecureString -SecureString $credential |
            Set-Content -LiteralPath $credentialPath -Encoding ASCII
        Write-Output "Saved encrypted $Channel credential under $folder."
    }
} finally {
    [Environment]::SetEnvironmentVariable($variable, $previousToken, 'Process')
    $credential.Dispose()
    Remove-Variable token, previousToken -ErrorAction SilentlyContinue
}
