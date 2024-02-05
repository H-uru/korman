#    This file is part of Korman.
#
#    Korman is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Korman is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Korman.  If not, see <http://www.gnu.org/licenses/>.

param(
    [Parameter()]
    [string]$GitHub = "https://api.github.com",

    [Parameter(Mandatory=$true)]
    [string]$Repository,

    [Parameter(Mandatory=$true)]
    [string]$Token,

    [Parameter()]
    [string]$UploadDir = "$PSScriptRoot/build/package",

    [Parameter()]
    [hashtable]$SubDirs = @{}
)

$ErrorActionPreference = "STOP"

$RequestHeaders = @{
    "Accept" = "application/vnd.github.v3+json"
    "Authorization" = "token $Token"
}

function Invoke-GitHubRequest($Method, $Uri, $Body, $ValidResults) {
    $Result = Invoke-WebRequest `
        -Uri "$Uri" `
        -Method "$Method" `
        -Headers $RequestHeaders `
        -ContentType "application/json" `
        -Body @(ConvertTo-JSON $Body) `
        -SkipHttpErrorCheck
    Test-GitHubResult `
        -Result $Result `
        -FailureMessage "GitHub API call failed" `
        -ValidResults $ValidResults
    try {
        $Content = ConvertFrom-JSON $Result.Content
    } catch {
        $Content = ""
    }
    return @{
        "StatusCode" = $Result.StatusCode
        "Content" = $Content
    }
}

$ContentTypeLUT = @{
    ".exe" =  "application/x-msdownload"
    ".sha256" = "text/plain"
    ".zip" = "application/zip"
}

function Invoke-GitHubUpload($Method, $Uri, $InFile, $ValidResults) {
    Write-Host "Uploading $InFile -> $Uri"

    # Can't use -InFile per my testing. Gah.
    $Body = [System.IO.File]::ReadAllBytes($InFile)
    if ($ContentTypeLUT.Contains($(Split-Path -Extension $InFile))) {
        $ContentType = $ContentTypeLUT[$(Split-Path -Extension $InFile)]
    } else {
        $ContentType = "application/octet-stream"
    }

    try {
        $Result = Invoke-WebRequest `
            -Uri "$Uri" `
            -Method "$Method" `
            -Headers $RequestHeaders `
            -ContentType $ContentType `
            -Body $Body `
            -SkipHttpErrorCheck
    } catch {
        throw "Uploading to GitHub failed. Check for (and delete any) junked files on the release!"
    }
    Test-GitHubResult `
        -Result $Result `
        -FailureMessage "GitHub API call failed" `
        -ValidResults $ValidResults
}

function Test-GitHubResult($Result, $FailureMessage, $ValidResults) {
    if (!($ValidResults.Contains($Result.StatusCode))) {
        Write-Host "bad result $Result"
        throw "$($FailureMessage): $($Result.StatusCode) $($Result.Content)"
    }
}

function Get-KormanRelease() {
    Write-Host -ForegroundColor Cyan "Finding a GitHub release for $Tag ($CommitSHA)..."

    $ExistingRelease = Invoke-GitHubRequest `
        -Uri "$GitHub/repos/$Repository/releases/tags/$Tag" `
        -Method GET `
        -ValidResults @(200, 404)

    if ($ExistingRelease.StatusCode -Eq 404) {
        # No matching release, so make a new one.
        Write-Host -ForegroundColor Cyan "Creating a new (pre-)release..."
        $NewRelease = Invoke-GitHubRequest `
            -Uri "$GitHub/repos/$Repository/releases" `
            -Method POST `
            -Body @{
                "name" = "Korman $Tag"
                "tag_name" = $Tag
                "target_commitish" = $CommitSHA
                "prerelease" = $true
            } `
            -ValidResults @(201)
        return $NewRelease.Content
    } elseif ($ExistingRelease.StatusCode -Eq 200) {
        Write-Host -ForegroundColor Yellow "Existing release found ($($ExistingRelease.Content.name)) - it will be forced to pre-release status and cleared!"
        if ($ExistingRelease.Content.prerelease -Ne $false) {
            Invoke-GitHubRequest `
                -Uri "$GitHub/repos/$Repository/releases/$($ExistingRelease.Content.id)" `
                -Method PATCH `
                -Body @{ "prerelease" = $true } `
                -ValidResults @(200)
        }
        foreach ($Asset in $ExistingRelease.Content.assets) {
            Write-Host -ForegroundColor Red "Deleting release asset $($Asset.name))"
            Invoke-GitHubRequest `
                -Uri $Asset.url `
                -Method DELETE `
                -ValidResults @(204)
        }
        return $ExistingRelease.Content
    }
    throw "???"
}

function Publish-KormanReleaseAssets($Release) {
    Write-Host -ForegroundColor Cyan "Finding assets to upload"
    $Assets = @{}
    foreach ($Iter in $SubDirs.GetEnumerator()) {
        foreach ($Item in (Get-ChildItem -File "$UploadDir/$($Iter.Key)")) {
            $Assets.Add("$($Iter.Value)_$($Item.Name)", $Item.FullName);
        }
    }
    foreach ($Item in (Get-ChildItem -File $UploadDir)) {
        $Assets.Add($Item.Name, $Item.FullName);
    }

    # Sigh, stupid GitHub...
    Write-Host -ForegroundColor Cyan "Uploading $($Assets.Count) asset(s) to GitHub release $($Release.id)"
    $ss = Select-String -InputObject $Release.upload_url "^(https:\/\/.+){"
    $UploadURL = $ss.Matches[0].Groups[1]
    Write-Host "URL: $UploadURL"

    foreach ($Asset in $Assets.GetEnumerator()) {
        Invoke-GitHubUpload `
            -Uri "$($UploadURL)?name=$($Asset.Key)" `
            -Method POST `
            -InFile $Asset.Value `
            -ValidResults @(201)
    }
}

# Try to determine what the current tag is.
Push-Location $PSScriptRoot
try {
    $Tag = git describe --tags --exact
    if ($LASTEXITCODE -Ne 0) {
        Write-Host -ForegroundColor Yellow "This will only work for tagged releases, my friend." | Out-Null
        Exit 0
    }
    $CommitSHA = git rev-parse HEAD
} finally {
    Pop-Location
}

$Release = Get-KormanRelease
Publish-KormanReleaseAssets $Release
